"""wiki/index.md 节标题与 FORMATS.md 对齐（中文展示标题）。"""
from __future__ import annotations

from storage.db import WikiStorage
from wiki_engine.constants import (
    INDEX_SECTION_ENTITIES,
    INDEX_SECTION_SYNTHESIS,
    EMPTY_INDEX_CONTENT,
    normalize_index_section_headers,
    resolve_index_section,
)
from wiki_engine.helpers import update_index


def test_resolve_aliases_to_formats():
    assert resolve_index_section("Comprehensive") == "综合页"
    assert resolve_index_section("综合") == "综合页"
    assert resolve_index_section("Synthesis") == "综合页"
    assert resolve_index_section("综合页") == INDEX_SECTION_SYNTHESIS
    assert resolve_index_section("Entities") == INDEX_SECTION_ENTITIES
    assert resolve_index_section("实体页") == INDEX_SECTION_ENTITIES
    assert resolve_index_section("Sources") == "来源文档"


def test_normalize_legacy_headers():
    legacy = (
        "# Wiki Index\n\n"
        "## Overview\n- [Overview](overview.md)\n\n"
        "## Sources\n\n## Entities\n\n## Concepts\n\n## Comprehensive\n"
    )
    normalized = normalize_index_section_headers(legacy)
    assert "## 全局概览" in normalized
    assert "## 来源文档" in normalized
    assert "## 实体页" in normalized
    assert "## 概念页" in normalized
    assert "## 综合页" in normalized
    assert "## Comprehensive" not in normalized
    assert "## Synthesis" not in normalized
    assert "## Sources" not in normalized


def test_update_index_writes_under_synthesis_for_legacy_comprehensive(tmp_path):
    db = WikiStorage(tmp_path / "wiki.db")
    kb_id = db.create_kb("_idx", "test")
    legacy = (
        "# Wiki Index\n\n"
        "## Overview\n- [Overview](overview.md)\n\n"
        "## Sources\n\n## Entities\n\n## Concepts\n\n## Comprehensive\n"
    )
    db.add_file(kb_id, "wiki/index.md", legacy)

    entry = "- [q](syntheses/q.md) — 综合回答"
    update_index(db, kb_id, entry, section=INDEX_SECTION_SYNTHESIS)

    content = db.get_file_text_by_path(kb_id, "wiki/index.md")
    assert "## 综合页" in content
    assert entry in content
    synth_pos = content.index("## 综合页")
    assert content.index(entry) > synth_pos
    assert "## Comprehensive" not in content
    assert "## Synthesis" not in content


def test_normalize_does_not_double_suffix():
    """短别名「综合」不得把「综合页」改成「综合页页」，且不吞换行。"""
    already = "# Wiki Index\n\n## 综合页\n- [a](syntheses/a.md)\n"
    assert normalize_index_section_headers(already) == already

    short = "# Wiki Index\n\n## 综合\n"
    assert normalize_index_section_headers(short) == "# Wiki Index\n\n## 综合页\n"

    spaced = (
        "# Wiki Index\n\n"
        "## Sources\n\n## Entities\n\n## Concepts\n\n## Comprehensive\n"
    )
    out = normalize_index_section_headers(spaced)
    assert "## 来源文档\n\n## 实体页\n\n## 概念页\n\n## 综合页\n" in out


def test_empty_index_matches_formats_template():
    assert "## 全局概览" in EMPTY_INDEX_CONTENT
    assert "## 来源文档" in EMPTY_INDEX_CONTENT
    assert "## 实体页" in EMPTY_INDEX_CONTENT
    assert "## 概念页" in EMPTY_INDEX_CONTENT
    assert "## 综合页" in EMPTY_INDEX_CONTENT
    assert "## Synthesis" not in EMPTY_INDEX_CONTENT
    assert "## Comprehensive" not in EMPTY_INDEX_CONTENT
