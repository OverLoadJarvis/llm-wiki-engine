"""辅助方法模块

提供引擎内部使用的辅助功能，包括：
- Wiki 上下文构建
- 索引更新
- 日志追加
- 摄入后验证
- 标题提取
- 已摄入 slug / ingest manifest 查询
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from storage.db import WikiStorage
from tools.utils import extract_wikilinks, strip_frontmatter, sha256
from tools.logger import get_logger

logger = get_logger(__name__)

INGEST_MANIFEST_PATH = "wiki/_ingest_manifest.json"


def empty_ingest_manifest() -> dict[str, Any]:
    """返回空的 ingest manifest 结构。"""
    return {"version": 1, "entries": {}}


def load_ingest_manifest(db: WikiStorage, kb_id: int) -> dict[str, Any]:
    """从 wiki/_ingest_manifest.json 加载摄入清单。"""
    raw = db.get_file_text_by_path(kb_id, INGEST_MANIFEST_PATH)
    if not raw or not raw.strip():
        return empty_ingest_manifest()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Invalid ingest manifest JSON for kb_id=%s, resetting", kb_id)
        return empty_ingest_manifest()
    if not isinstance(data, dict):
        return empty_ingest_manifest()
    entries = data.get("entries")
    if not isinstance(entries, dict):
        entries = {}
    return {"version": int(data.get("version", 1)), "entries": entries}


def save_ingest_manifest(db: WikiStorage, kb_id: int, manifest: dict[str, Any]) -> None:
    """将摄入清单写入 wiki/_ingest_manifest.json。"""
    payload = {
        "version": int(manifest.get("version", 1)),
        "entries": manifest.get("entries") or {},
    }
    content = json.dumps(payload, ensure_ascii=False, indent=2)
    db.add_file(kb_id, INGEST_MANIFEST_PATH, content)
    logger.info(
        "Saved ingest manifest: kb_id=%s, entries=%d",
        kb_id,
        len(payload["entries"]),
    )


def is_raw_ingested(
    manifest: dict[str, Any], relative_path: str, content_hash: str
) -> bool:
    """判断 raw 路径在当前内容 hash 下是否已记录为已摄入。"""
    entry = (manifest.get("entries") or {}).get(relative_path)
    if not entry or not isinstance(entry, dict):
        return False
    return entry.get("content_hash") == content_hash


def record_ingest(
    manifest: dict[str, Any],
    relative_path: str,
    content_hash: str,
    source_slug: str,
    pages: list[str] | None = None,
) -> dict[str, Any]:
    """向 manifest 写入或更新一条摄入记录（原地修改并返回 manifest）。"""
    entries = manifest.setdefault("entries", {})
    entries[relative_path] = {
        "content_hash": content_hash,
        "source_slug": source_slug,
        "ingested_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pages": list(pages or []),
    }
    manifest.setdefault("version", 1)
    return manifest


def _normalize_raw_ref(value: str) -> str | None:
    """将 frontmatter 中的 raw 引用规范为 relative_path（如 raw/foo.md）。"""
    value = value.strip().strip('"').strip("'")
    if not value:
        return None
    value = value.replace("\\", "/")
    # sources: [raw/...] YAML list item without brackets sometimes arrives as raw/...
    if value.startswith("- "):
        value = value[2:].strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1].strip().strip('"').strip("'")
    if not value:
        return None
    if not value.startswith("raw/"):
        if "/" not in value:
            value = f"raw/{value}"
        else:
            return None
    return value


def extract_raw_path_from_source_page(content: str) -> str | None:
    """从 wiki/sources 页面 frontmatter 提取 raw 路径（source_file / sources）。"""
    m = re.search(r"^source_file:\s*(.+)$", content, re.MULTILINE)
    if m:
        return _normalize_raw_ref(m.group(1))

    m = re.search(r"^sources:\s*(.+)$", content, re.MULTILINE)
    if not m:
        return None
    raw_val = m.group(1).strip()
    if raw_val.startswith("[") and not raw_val.endswith("]"):
        # multi-line list; collect following "- raw/..." lines only naively from first line
        return None
    if raw_val.startswith("[") and raw_val.endswith("]"):
        inner = raw_val[1:-1].strip()
        if not inner:
            return None
        # take first item
        first = inner.split(",")[0].strip()
        return _normalize_raw_ref(first)
    return _normalize_raw_ref(raw_val)


def bootstrap_ingest_manifest(
    db: WikiStorage, kb_id: int, manifest: dict[str, Any] | None = None
) -> dict[str, Any]:
    """manifest 为空时，从 wiki/sources frontmatter 尝试填充 path→当前 raw hash。

    仅当 frontmatter 明确指向某个现有 raw 路径时写入，避免误跳过。
    """
    if manifest is None:
        manifest = load_ingest_manifest(db, kb_id)
    if manifest.get("entries"):
        return manifest

    source_files = db.list_files(kb_id, "wiki/sources/")
    if not source_files:
        return manifest

    filled = 0
    for sf in source_files:
        content = db.get_file_text_by_path(kb_id, sf["relative_path"])
        if not content:
            continue
        raw_path = extract_raw_path_from_source_page(content)
        if not raw_path:
            continue
        raw_text = db.get_file_text_by_path(kb_id, raw_path)
        if raw_text is None:
            continue
        slug = Path(sf["relative_path"]).stem
        record_ingest(
            manifest,
            raw_path,
            sha256(raw_text),
            source_slug=slug,
            pages=[sf["relative_path"]],
        )
        filled += 1

    if filled:
        save_ingest_manifest(db, kb_id, manifest)
        logger.info(
            "Bootstrapped ingest manifest: kb_id=%s, entries=%d", kb_id, filled
        )
    return manifest


def get_ingested_slugs(db: WikiStorage, kb_id: int) -> set[str]:
    """获取项目中已摄入的源文档 slug 集合。

    Deprecated for Build/Update skip logic: prefer ingest manifest (path + hash).
    Kept for health checks and other callers.

    通过扫描 wiki/sources/ 目录下的文件名来推断哪些源文档已被处理。
    """
    source_files = db.list_files(kb_id, "wiki/sources/")
    return {Path(f["relative_path"]).stem.lower() for f in source_files}


def build_wiki_context(db: WikiStorage, kb_id: int) -> str:
    """构建 Wiki 上下文字符串，供 LLM 摄入时参考。

    从 SQLite 读取 index.md、overview.md 和最近 5 个源页面，
    拼接为一段上下文文本，帮助 LLM 理解当前 Wiki 状态。

    Args:
        db: WikiStorage 数据库实例
        kb_id: 项目 ID

    Returns:
        拼接后的上下文字符串，各部分用 ``---`` 分隔；
        若 Wiki 为空则返回空字符串。
    """
    parts = []

    index_content = db.get_file_text_by_path(kb_id, "wiki/index.md")
    if index_content:
        parts.append(f"## wiki/index.md\n{index_content}")

    overview_content = db.get_file_text_by_path(kb_id, "wiki/overview.md")
    if overview_content:
        parts.append(f"## wiki/overview.md\n{overview_content}")

    source_files = db.list_files(kb_id, "wiki/sources/")
    source_files.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    for f in source_files[:5]:
        content = db.get_file_text_by_path(kb_id, f["relative_path"])
        if content:
            parts.append(f"## {f['relative_path']}\n{content}")

    return "\n\n---\n\n".join(parts)


def all_wiki_page_stems(db: WikiStorage, kb_id: int) -> set[str]:
    """获取项目中所有 wiki 页面的 stem 集合（小写）。

    排除 index.md、log.md、lint-report.md 等元数据页面。

    Args:
        db: WikiStorage 数据库实例
        kb_id: 项目 ID

    Returns:
        页面 stem 的小写集合，例如 ``{"my-page", "openai"}``
    """
    wiki_files = db.list_files(kb_id, "wiki/")
    return {
        Path(f["relative_path"]).stem.lower()
        for f in wiki_files
        if Path(f["relative_path"]).name not in ("index.md", "log.md", "lint-report.md")
    }


def extract_title_from_content(content: str) -> str:
    """从 Markdown 内容中提取标题。

    依次尝试从 YAML frontmatter 的 ``title`` 字段和首个 ``# 标题`` 行提取。
    若均未找到，返回 ``"未知"``。

    Args:
        content: Markdown 文本内容

    Returns:
        提取到的标题字符串
    """
    m = re.search(r"title:\s*[\"']([^\"']+)[\"']", content)
    if m:
        return m.group(1)
    m = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return "未知"


def update_index(db, kb_id: int, new_entry: str, section: str = "源文档") -> None:
    """向 wiki/index.md 的指定节追加一条索引条目。

    若 index.md 不存在，则创建包含标准节的初始索引。
    若指定节不存在，则在末尾追加该节。

    Args:
        db: WikiStorage 数据库实例
        kb_id: 项目 ID
        new_entry: 要追加的索引行，例如 ``"- [标题](sources/slug.md) — 摘要"``
        section: 目标节名称，默认 ``"源文档"``
    """
    content = db.get_file_text_by_path(kb_id, "wiki/index.md") or ""
    if not content:
        content = (
            "# Wiki Index\n\n"
            "## Overview\n- [Overview](overview.md)\n\n"
            "## Sources\n\n## Entities\n\n## Concepts\n\n## Comprehensive\n"
        )

    section_header = f"## {section}"
    if section_header in content:
        content = content.replace(section_header + "\n", section_header + "\n" + new_entry + "\n")
    else:
        content += f"\n{section_header}\n{new_entry}\n"

    db.add_file(kb_id, "wiki/index.md", content)


def append_log(db: WikiStorage, kb_id: int, entry: str) -> None:
    """向 wiki/log.md 追加一条日志条目。

    新条目插入到日志顶部（时间倒序），条目之间用空行分隔。

    Args:
        db: WikiStorage 数据库实例
        kb_id: 项目 ID
        entry: 日志条目文本，通常以 ``## [YYYY-MM-DD] 操作 | 标题`` 开头
    """
    existing = db.get_file_text_by_path(kb_id, "wiki/log.md") or ""
    db.add_file(kb_id, "wiki/log.md", entry.strip() + "\n\n" + existing)


def validate_ingest(db, kb_id: int, changed_paths: list[str]) -> dict[str, Any]:
    """摄入后验证：检查损坏的 wikilink 和未索引页面。

    在每次摄入操作后调用，确保新创建的页面没有指向不存在页面的链接，
    并且所有新页面都已出现在 index.md 中。

    Args:
        db: WikiStorage 数据库实例
        kb_id: 项目 ID
        changed_paths: 本次摄入中新增或修改的页面路径列表

    Returns:
        包含两个键的字典：
        - ``broken_links``: ``list[tuple[str, str]]`` — (页面路径, 链接目标) 对
        - ``unindexed``: ``list[str]`` — 未出现在 index.md 中的页面路径
    """
    existing_stems = all_wiki_page_stems(db, kb_id)
    index_content = (db.get_file_text_by_path(kb_id, "wiki/index.md") or "").lower()

    broken_links = []
    for rel_path in changed_paths:
        content = db.get_file_text_by_path(kb_id, rel_path)
        if not content:
            continue
        for link in extract_wikilinks(content):
            link_stem = Path(link).stem.lower() if "/" in link else link.lower()
            if link_stem not in existing_stems:
                logger.warning("Broken link: %s -> %s", rel_path, link)
                logger.debug("Existing stems: %s", existing_stems)
                broken_links.append((rel_path, link))

    unindexed = []
    for rel_path in changed_paths:
        stem = Path(rel_path).stem.lower()
        if stem not in index_content and Path(rel_path).name not in ("log.md", "overview.md"):
            logger.warning("Unindexed page: %s", rel_path)
            logger.debug("Index content: %s", index_content)
            unindexed.append(rel_path)

    return {"broken_links": broken_links, "unindexed": unindexed}
