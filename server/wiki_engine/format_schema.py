"""FORMATS.md 章节拆分与按需组装。

将 wiki 格式规范按 ## / ### 标题切分为稳定 ID 的块，供 ingest 前
格式预判与按需注入使用。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable

from wiki_engine.constants import SCHEMA_FILE
from tools.logger import get_logger

logger = get_logger(__name__)

# 每次 ingest 固定注入的核心块
CORE_FORMAT_IDS: tuple[str, ...] = ("1", "2", "5", "7", "8")

# 可预判的来源页模板（3=通用；4x=领域）
SELECTABLE_FORMAT_IDS: frozenset[str] = frozenset({"3", "4a", "4b", "4c", "4d"})
DOMAIN_FORMAT_IDS: frozenset[str] = frozenset({"4a", "4b", "4c", "4d"})
DEFAULT_SOURCE_FORMAT_ID = "3"

_HEADING_RE = re.compile(
    r"^(#{2,3})\s+(\d+[a-z]?)\.\s+(.+?)\s*$",
    re.MULTILINE,
)
_APPLICABILITY_RE = re.compile(
    r"\*\*(?:适用文件|适用场景|用途)：\*\*\s*(.+)",
)


@dataclass(frozen=True)
class FormatSection:
    """FORMATS.md 中的一个章节块。"""

    id: str
    title: str
    level: int
    body: str

    @property
    def full_text(self) -> str:
        hashes = "#" * self.level
        return f"{hashes} {self.id}. {self.title}\n{self.body}".rstrip() + "\n"

    @property
    def summary(self) -> str:
        """从正文提取适用/用途描述，供预判目录使用。"""
        lines: list[str] = []
        for match in _APPLICABILITY_RE.finditer(self.body):
            lines.append(match.group(1).strip())
        if lines:
            return " ".join(lines)
        # 回退：取首段非空、非代码围栏行
        for line in self.body.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("```") or stripped.startswith("---"):
                continue
            if stripped.startswith("**") or stripped.startswith("|"):
                continue
            return stripped[:200]
        return self.title


@lru_cache(maxsize=1)
def _load_sections() -> dict[str, FormatSection]:
    """解析 FORMATS.md，按章节 ID 缓存。"""
    path = SCHEMA_FILE
    if not path.exists():
        logger.error("FORMATS.md not found: %s", path)
        return {}

    text = path.read_text(encoding="utf-8")
    matches = list(_HEADING_RE.finditer(text))
    sections: dict[str, FormatSection] = {}

    for i, match in enumerate(matches):
        hashes, section_id, title = match.group(1), match.group(2), match.group(3)
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip("\n")
        # 去掉章节之间的 --- 分隔线尾部
        body = re.sub(r"\n---\s*$", "", body).rstrip() + "\n"
        sections[section_id] = FormatSection(
            id=section_id,
            title=title.strip(),
            level=len(hashes),
            body=body,
        )

    logger.info(
        "Parsed FORMATS.md: %d sections (%s)",
        len(sections),
        ",".join(sorted(sections.keys(), key=_section_sort_key)),
    )
    return sections


def _section_sort_key(section_id: str) -> tuple:
    m = re.match(r"^(\d+)([a-z]?)$", section_id)
    if not m:
        return (999, section_id)
    return (int(m.group(1)), m.group(2) or "")


def get_sections() -> dict[str, FormatSection]:
    """返回全部已解析章节（只读缓存副本语义：勿修改返回值）。"""
    return _load_sections()


def list_selectable_formats() -> list[dict[str, str]]:
    """可预判格式目录：id / title / summary。"""
    sections = _load_sections()
    result: list[dict[str, str]] = []
    for section_id in sorted(SELECTABLE_FORMAT_IDS, key=_section_sort_key):
        section = sections.get(section_id)
        if not section:
            logger.warning("Selectable format section missing in FORMATS.md: %s", section_id)
            continue
        result.append(
            {
                "id": section.id,
                "title": section.title,
                "summary": section.summary,
            }
        )
    return result


def resolve_source_format_ids(selected_ids: Iterable[str] | None) -> list[str]:
    """根据预判结果解析应注入的来源模板 ID。

    - 命中任一 4x → 只保留合法的领域模板（可多个）
    - 否则 → ``3``
    - 非法 / 空 → ``3``
    """
    sections = _load_sections()
    if not selected_ids:
        return [DEFAULT_SOURCE_FORMAT_ID]

    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in selected_ids:
        sid = str(raw).strip().lower()
        if sid not in SELECTABLE_FORMAT_IDS or sid not in sections:
            continue
        if sid not in seen:
            seen.add(sid)
            cleaned.append(sid)

    if not cleaned:
        return [DEFAULT_SOURCE_FORMAT_ID]

    domain = [sid for sid in cleaned if sid in DOMAIN_FORMAT_IDS]
    if domain:
        return domain
    return [DEFAULT_SOURCE_FORMAT_ID]


def build_ingest_schema(selected_ids: Iterable[str] | None = None) -> str:
    """组装 ingest 用的格式规范：核心块 + 解析后的来源模板。"""
    sections = _load_sections()
    source_ids = resolve_source_format_ids(selected_ids)
    ordered_ids = list(CORE_FORMAT_IDS) + source_ids

    parts: list[str] = ["# Wiki 格式规范（按需注入）\n"]
    missing: list[str] = []
    for section_id in ordered_ids:
        section = sections.get(section_id)
        if not section:
            missing.append(section_id)
            continue
        parts.append(section.full_text)
        parts.append("\n---\n")

    if missing:
        logger.warning("Missing FORMATS.md sections while building schema: %s", missing)

    return "\n".join(parts).rstrip() + "\n"


def format_catalog_for_prompt() -> str:
    """将可预判目录格式化为 prompt 文本。"""
    lines: list[str] = []
    for item in list_selectable_formats():
        lines.append(f"- id=`{item['id']}` | {item['title']} — {item['summary']}")
    return "\n".join(lines)
