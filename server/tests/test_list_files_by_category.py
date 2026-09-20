"""list_files_by_category must include nested paths under top-level roots."""
from __future__ import annotations

from storage.db import WikiStorage


def test_list_raw_includes_nested_subdir(tmp_path):
    db = WikiStorage(tmp_path / "test.db")
    try:
        kid = db.create_kb("_cat_prefix")
        db.add_file(kid, "raw/top.md", "# top")
        db.add_file(kid, "raw/a/nested.md", "# nested")
        db.add_file(kid, "raw/a/b/deep.md", "# deep")
        db.add_file(kid, "wiki/index.md", "# wiki")

        raw_paths = [f["relative_path"] for f in db.list_files_by_category(kid, "raw")]
        assert raw_paths == [
            "raw/a/b/deep.md",
            "raw/a/nested.md",
            "raw/top.md",
        ]

        wiki_paths = [f["relative_path"] for f in db.list_files_by_category(kid, "wiki")]
        assert wiki_paths == ["wiki/index.md"]
    finally:
        db.close()
