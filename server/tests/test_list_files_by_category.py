"""Canonical category mapping and list_files_by_category behaviour."""
from __future__ import annotations

from storage.db import WikiStorage


def test_extract_category_canonical(tmp_path):
    db = WikiStorage(tmp_path / "test.db")
    try:
        cases = [
            ("raw/top.md", "raw"),
            ("raw/a/nested.md", "raw"),
            ("raw/a/b/deep.md", "raw"),
            ("graph/graph.json", "graph"),
            ("graph/subdir/x.json", "graph"),
            ("wiki/index.md", "wiki"),
            ("wiki/log.md", "wiki"),
            ("wiki/overview.md", "wiki"),
            ("wiki/syntheses/q.md", "wiki"),
            ("wiki/sources/doc.md", "wiki/sources"),
            ("wiki/concepts/idea.md", "wiki/concepts"),
            ("wiki/entities/Person.md", "wiki/entities"),
        ]
        kid = db.create_kb("_cat_canon")
        for path, want in cases:
            db.add_file(kid, path, f"# {path}")
            row = db.get_file_by_path(kid, path)
            assert row["category"] == want, (path, row["category"], want)

        raw_paths = [f["relative_path"] for f in db.list_files_by_category(kid, "raw")]
        assert raw_paths == [
            "raw/a/b/deep.md",
            "raw/a/nested.md",
            "raw/top.md",
        ]

        wiki_only = [f["relative_path"] for f in db.list_files_by_category(kid, "wiki")]
        assert wiki_only == [
            "wiki/index.md",
            "wiki/log.md",
            "wiki/overview.md",
            "wiki/syntheses/q.md",
        ]

        sources = [f["relative_path"] for f in db.list_files_by_category(kid, "wiki/sources")]
        assert sources == ["wiki/sources/doc.md"]
    finally:
        db.close()


def test_migrate_legacy_nested_raw_category(tmp_path):
    db = WikiStorage(tmp_path / "legacy.db")
    try:
        kid = db.create_kb("_legacy")
        db.conn.execute(
            """INSERT INTO files (kb_id, category, relative_path, file_name, content, file_size)
               VALUES (?, 'raw/a', 'raw/a/old.md', 'old.md', ?, 1)""",
            (kid, b"x"),
        )
        db.conn.commit()
        db.close()

        db2 = WikiStorage(tmp_path / "legacy.db")
        row = db2.get_file_by_path(kid, "raw/a/old.md")
        assert row["category"] == "raw"
        paths = [f["relative_path"] for f in db2.list_files_by_category(kid, "raw")]
        assert paths == ["raw/a/old.md"]
        db2.close()
    finally:
        pass
