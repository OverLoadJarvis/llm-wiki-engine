"""辅助方法模块

提供引擎内部使用的辅助功能，包括：
- Wiki 上下文构建
- 索引更新
- 日志追加
- 摄入后验证
- 标题提取
- 已摄入 slug 查询
"""

import re
from pathlib import Path
from typing import Any

from storage.db import WikiStorage
from tools.utils import extract_wikilinks, strip_frontmatter
from tools.logger import get_logger

logger = get_logger(__name__)


def build_wiki_context(db: WikiStorage, project_id: int) -> str:
    """构建 Wiki 上下文字符串，供 LLM 摄入时参考。

    从 SQLite 读取 index.md、overview.md 和最近 5 个源页面，
    拼接为一段上下文文本，帮助 LLM 理解当前 Wiki 状态。

    Args:
        db: WikiStorage 数据库实例
        project_id: 项目 ID

    Returns:
        拼接后的上下文字符串，各部分用 ``---`` 分隔；
        若 Wiki 为空则返回空字符串。
    """
    parts = []

    index_content = db.get_file_text_by_path(project_id, "wiki/index.md")
    if index_content:
        parts.append(f"## wiki/index.md\n{index_content}")

    overview_content = db.get_file_text_by_path(project_id, "wiki/overview.md")
    if overview_content:
        parts.append(f"## wiki/overview.md\n{overview_content}")

    source_files = db.list_files(project_id, "wiki/sources/")
    source_files.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    for f in source_files[:5]:
        content = db.get_file_text_by_path(project_id, f["relative_path"])
        if content:
            parts.append(f"## {f['relative_path']}\n{content}")

    return "\n\n---\n\n".join(parts)


def all_wiki_page_stems(db: WikiStorage, project_id: int) -> set[str]:
    """获取项目中所有 wiki 页面的 stem 集合（小写）。

    排除 index.md、log.md、lint-report.md 等元数据页面。

    Args:
        db: WikiStorage 数据库实例
        project_id: 项目 ID

    Returns:
        页面 stem 的小写集合，例如 ``{"my-page", "openai"}``
    """
    wiki_files = db.list_files(project_id, "wiki/")
    return {
        Path(f["relative_path"]).stem.lower()
        for f in wiki_files
        if Path(f["relative_path"]).name not in ("index.md", "log.md", "lint-report.md")
    }


def get_ingested_slugs(db: WikiStorage, project_id: int) -> set[str]:
    """获取项目中已摄入的源文档 slug 集合。

    通过扫描 wiki/sources/ 目录下的文件名来推断哪些源文档已被处理。

    Args:
        db: WikiStorage 数据库实例
        project_id: 项目 ID

    Returns:
        已摄入 slug 的小写集合
    """
    source_files = db.list_files(project_id, "wiki/sources/")
    return {Path(f["relative_path"]).stem.lower() for f in source_files}


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


def update_index(db, project_id: int, new_entry: str, section: str = "源文档") -> None:
    """向 wiki/index.md 的指定节追加一条索引条目。

    若 index.md 不存在，则创建包含标准节的初始索引。
    若指定节不存在，则在末尾追加该节。

    Args:
        db: WikiStorage 数据库实例
        project_id: 项目 ID
        new_entry: 要追加的索引行，例如 ``"- [标题](sources/slug.md) — 摘要"``
        section: 目标节名称，默认 ``"源文档"``
    """
    content = db.get_file_text_by_path(project_id, "wiki/index.md") or ""
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

    db.add_file(project_id, "wiki/index.md", content)


def append_log(db: WikiStorage, project_id: int, entry: str) -> None:
    """向 wiki/log.md 追加一条日志条目。

    新条目插入到日志顶部（时间倒序），条目之间用空行分隔。

    Args:
        db: WikiStorage 数据库实例
        project_id: 项目 ID
        entry: 日志条目文本，通常以 ``## [YYYY-MM-DD] 操作 | 标题`` 开头
    """
    existing = db.get_file_text_by_path(project_id, "wiki/log.md") or ""
    db.add_file(project_id, "wiki/log.md", entry.strip() + "\n\n" + existing)


def validate_ingest(db, project_id: int, changed_paths: list[str]) -> dict[str, Any]:
    """摄入后验证：检查损坏的 wikilink 和未索引页面。

    在每次摄入操作后调用，确保新创建的页面没有指向不存在页面的链接，
    并且所有新页面都已出现在 index.md 中。

    Args:
        db: WikiStorage 数据库实例
        project_id: 项目 ID
        changed_paths: 本次摄入中新增或修改的页面路径列表

    Returns:
        包含两个键的字典：
        - ``broken_links``: ``list[tuple[str, str]]`` — (页面路径, 链接目标) 对
        - ``unindexed``: ``list[str]`` — 未出现在 index.md 中的页面路径
    """
    existing_stems = all_wiki_page_stems(db, project_id)
    index_content = (db.get_file_text_by_path(project_id, "wiki/index.md") or "").lower()

    broken_links = []
    for rel_path in changed_paths:
        content = db.get_file_text_by_path(project_id, rel_path)
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
