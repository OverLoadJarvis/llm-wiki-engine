#!/usr/bin/env python3
from __future__ import annotations

"""
SQLite-backed storage for graph / raw / wiki file trees.

Each "kb" captures a full snapshot of the graph/, raw/, and wiki/ directories
with per-file relative paths preserved.  The database supports full CRUD, full‑text
search, directory‑tree reconstruction, and disk import/export.

Usage:
    from storage.db import WikiStorage

    db = WikiStorage("storage/wiki.db")
    kid = db.create_kb("my-kb")
    db.import_directory(kid, "graph")
    db.import_directory(kid, "raw")
    db.import_directory(kid, "wiki")
    db.export_kb(kid, "/tmp/restored-kb")
    db.close()
"""

import hashlib
import os
import sqlite3
import time
from pathlib import Path
from typing import Any

from tools.logger import get_logger

logger = get_logger(__name__)

REPO_ROOT = Path(__file__).parent.parent
SCHEMA_PATH = Path(__file__).parent / "schema.sql"

_TEXT_EXTENSIONS = {
    ".md", ".json", ".jsonl", ".html", ".txt", ".csv", ".xml",
    ".yaml", ".yml", ".toml", ".py", ".js", ".ts", ".css", ".rst",
}


def _is_text_file(filepath: str | Path) -> bool:
    return Path(filepath).suffix.lower() in _TEXT_EXTENSIONS


class WikiStorage:
    """High-level CRUD wrapper around the SQLite database."""

    def __init__(self, db_path: str | Path = "storage/wiki.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self) -> None:
        if SCHEMA_PATH.exists():
            self.conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
            self.conn.commit()
        self._migrate()

    def _migrate(self) -> None:
        """按需执行 schema 迁移，确保向后兼容旧数据库文件。"""
        cols = {row["name"] for row in self.conn.execute("PRAGMA table_info(kbs)").fetchall()}
        if "state" not in cols:
            self.conn.execute("ALTER TABLE kbs ADD COLUMN state TEXT NOT NULL DEFAULT 'unbuilt'")
            self.conn.commit()
        if "ingest_instruction" not in cols:
            self.conn.execute("ALTER TABLE kbs ADD COLUMN ingest_instruction TEXT NOT NULL DEFAULT ''")
            self.conn.commit()
        # 兼容旧库：schema.sql 中的 CREATE 对已有 DB 可能已执行；此处再保底一次
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS llm_settings (
                id         INTEGER PRIMARY KEY CHECK (id = 1),
                base_url   TEXT NOT NULL DEFAULT '',
                api_key    TEXT NOT NULL DEFAULT '',
                model      TEXT NOT NULL DEFAULT '',
                model_fast TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # ── Global LLM settings ────────────────────────────────────────

    def get_llm_settings(self) -> dict[str, Any]:
        """Return stored LLM settings (empty strings if unset)."""
        row = self.conn.execute(
            "SELECT base_url, api_key, model, model_fast, updated_at FROM llm_settings WHERE id = 1"
        ).fetchone()
        if not row:
            return {
                "base_url": "",
                "api_key": "",
                "model": "",
                "model_fast": "",
                "updated_at": None,
            }
        return dict(row)

    def set_llm_settings(
        self,
        base_url: str,
        api_key: str,
        model: str,
        model_fast: str,
    ) -> dict[str, Any]:
        """Upsert global LLM settings (single row id=1)."""
        self.conn.execute(
            """
            INSERT INTO llm_settings (id, base_url, api_key, model, model_fast, updated_at)
            VALUES (1, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(id) DO UPDATE SET
                base_url = excluded.base_url,
                api_key = excluded.api_key,
                model = excluded.model,
                model_fast = excluded.model_fast,
                updated_at = datetime('now')
            """,
            (base_url or "", api_key or "", model or "", model_fast or ""),
        )
        self.conn.commit()
        logger.info(
            "LLM settings saved: base_url=%s, model=%s, model_fast=%s, api_key_set=%s",
            base_url or "",
            model or "",
            model_fast or "",
            bool(api_key),
        )
        return self.get_llm_settings()

    # ── KB CRUD ────────────────────────────────────────────────────

    def create_kb(self, name: str, description: str = "") -> int:
        """Create a new kb. Returns the kb id."""
        cur = self.conn.execute(
            "INSERT INTO kbs (name, description) VALUES (?, ?)",
            (name, description),
        )
        self.conn.commit()
        return cur.lastrowid

    def delete_kb(self, kb_id: int) -> bool:
        """Delete a kb and all its files. Returns True if deleted."""
        # 先删除关联的文件记录
        self.conn.execute("DELETE FROM files WHERE kb_id = ?", (kb_id,))
        # 然后删除知识库
        cur = self.conn.execute("DELETE FROM kbs WHERE id = ?", (kb_id,))
        self.conn.commit()
        return cur.rowcount > 0

    def get_kb(self, kb_id: int) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM kbs WHERE id = ?", (kb_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_kb_by_name(self, name: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM kbs WHERE name = ?", (name,)
        ).fetchone()
        return dict(row) if row else None

    def list_kbs(self) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM kbs ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def rename_kb(self, kb_id: int, new_name: str) -> bool:
        cur = self.conn.execute(
            "UPDATE kbs SET name = ?, updated_at = datetime('now') WHERE id = ?",
            (new_name, kb_id),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def touch_kb(self, kb_id: int) -> None:
        """Update the kb's updated_at timestamp."""
        self.conn.execute(
            "UPDATE kbs SET updated_at = datetime('now') WHERE id = ?",
            (kb_id,),
        )
        self.conn.commit()

    def set_kb_state(self, kb_id: int, state: str) -> bool:
        """Set the kb's state. Valid states: 'unbuilt', 'building', 'completed'."""
        cur = self.conn.execute(
            "UPDATE kbs SET state = ?, updated_at = datetime('now') WHERE id = ?",
            (state, kb_id),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def get_ingest_instruction(self, kb_id: int) -> str:
        """获取知识库的构建指令，可能为空字符串。"""
        row = self.conn.execute(
            "SELECT ingest_instruction FROM kbs WHERE id = ?", (kb_id,)
        ).fetchone()
        return row["ingest_instruction"] if row else ""

    def set_ingest_instruction(self, kb_id: int, instruction: str) -> bool:
        """设置知识库的构建指令。"""
        cur = self.conn.execute(
            "UPDATE kbs SET ingest_instruction = ?, updated_at = datetime('now') WHERE id = ?",
            (instruction, kb_id),
        )
        self.conn.commit()
        return cur.rowcount > 0

    # ── File CRUD ─────────────────────────────────────────────────────

    @staticmethod
    def _extract_category(relative_path: str) -> str:
        return relative_path.rsplit("/", 1)[0]

    def add_file(
        self,
        kb_id: int,
        relative_path: str,
        content: bytes | str,
    ) -> int:
        """Add or replace a file.  Returns the file id."""
        relative_path = relative_path.replace("\\", "/")
        if isinstance(content, str):
            content_bytes = content.encode("utf-8")
        else:
            content_bytes = content

        file_name = Path(relative_path).name
        category = self._extract_category(relative_path)
        file_size = len(content_bytes)
        checksum = hashlib.sha256(content_bytes).hexdigest()

        content_text: str | None = None
        if _is_text_file(relative_path):
            content_text = content if isinstance(content, str) else content_bytes.decode("utf-8", errors="replace")

        cur = self.conn.execute(
            """INSERT INTO files (kb_id, category, relative_path, file_name,
                                  content, content_text, file_size, checksum)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(kb_id, relative_path) DO UPDATE SET
                 category     = excluded.category,
                 content      = excluded.content,
                 content_text = excluded.content_text,
                 file_size    = excluded.file_size,
                 checksum     = excluded.checksum,
                 updated_at   = datetime('now')""",
            (kb_id, category, relative_path, file_name, content_bytes, content_text, file_size, checksum),
        )
        self.touch_kb(kb_id)
        self.conn.commit()
        return cur.lastrowid

    def add_file_from_disk(self, kb_id: int, filepath: str | Path) -> int:
        """Read a file from disk and store it under its relative path."""
        filepath = Path(filepath)
        content = filepath.read_bytes()
        return self.add_file(kb_id, str(filepath), content)

    def get_file(self, file_id: int) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT id, kb_id, category, relative_path, file_name, content, "
            "content_text, file_size, checksum, created_at, updated_at "
            "FROM files WHERE id = ?",
            (file_id,),
        ).fetchone()
        return dict(row) if row else None

    def get_file_by_path(self, kb_id: int, relative_path: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT id, kb_id, category, relative_path, file_name, content, "
            "content_text, file_size, checksum, created_at, updated_at "
            "FROM files WHERE kb_id = ? AND relative_path = ?",
            (kb_id, relative_path),
        ).fetchone()
        return dict(row) if row else None

    def get_file_content(self, file_id: int) -> bytes | None:
        row = self.conn.execute(
            "SELECT content FROM files WHERE id = ?", (file_id,)
        ).fetchone()
        return row["content"] if row else None

    def get_file_content_by_path(self, kb_id: int, relative_path: str) -> bytes | None:
        row = self.conn.execute(
            "SELECT content FROM files WHERE kb_id = ? AND relative_path = ?",
            (kb_id, relative_path),
        ).fetchone()
        return row["content"] if row else None

    def get_file_text_by_path(self, kb_id: int, relative_path: str) -> str | None:
        row = self.conn.execute(
            "SELECT content_text FROM files WHERE kb_id = ? AND relative_path = ?",
            (kb_id, relative_path),
        ).fetchone()
        if row and row["content_text"] is not None:
            return row["content_text"]
        if row:
            return row["content"].decode("utf-8", errors="replace") if row["content"] else None
        return None

    def update_file(self, file_id: int, content: bytes | str) -> bool:
        if isinstance(content, str):
            content_bytes = content.encode("utf-8")
        else:
            content_bytes = content

        existing = self.get_file(file_id)
        if not existing:
            return False

        content_text = None
        if _is_text_file(existing["relative_path"]):
            content_text = content if isinstance(content, str) else content_bytes.decode("utf-8", errors="replace")

        checksum = hashlib.sha256(content_bytes).hexdigest()
        cur = self.conn.execute(
            """UPDATE files SET content = ?, content_text = ?, file_size = ?,
               checksum = ?, updated_at = datetime('now') WHERE id = ?""",
            (content_bytes, content_text, len(content_bytes), checksum, file_id),
        )
        self.touch_kb(existing["kb_id"])
        self.conn.commit()
        return cur.rowcount > 0

    def update_file_by_path(self, kb_id: int, relative_path: str, content: bytes | str) -> bool:
        existing = self.get_file_by_path(kb_id, relative_path)
        if not existing:
            return False
        return self.update_file(existing["id"], content)

    def delete_file(self, file_id: int) -> bool:
        row = self.conn.execute("SELECT kb_id FROM files WHERE id = ?", (file_id,)).fetchone()
        if not row:
            return False
        pid = row["kb_id"]
        cur = self.conn.execute("DELETE FROM files WHERE id = ?", (file_id,))
        self.touch_kb(pid)
        self.conn.commit()
        return cur.rowcount > 0

    def delete_file_by_path(self, kb_id: int, relative_path: str) -> bool:
        cur = self.conn.execute(
            "DELETE FROM files WHERE kb_id = ? AND relative_path = ?",
            (kb_id, relative_path),
        )
        self.touch_kb(kb_id)
        self.conn.commit()
        return cur.rowcount > 0

    # ── List / Query ──────────────────────────────────────────────────

    def list_files(
        self,
        kb_id: int,
        prefix: str = "",
    ) -> list[dict[str, Any]]:
        """List files under a directory prefix (e.g. 'wiki/' or 'wiki/concepts/')."""
        cols = ("id, kb_id, category, relative_path, file_name, "
                "file_size, checksum, created_at, updated_at")
        if prefix:
            rows = self.conn.execute(
                f"SELECT {cols} FROM files WHERE kb_id = ? AND relative_path LIKE ? "
                "ORDER BY relative_path",
                (kb_id, f"{prefix}%"),
            ).fetchall()
        else:
            rows = self.conn.execute(
                f"SELECT {cols} FROM files WHERE kb_id = ? ORDER BY relative_path",
                (kb_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def list_files_by_category(
        self,
        kb_id: int,
        category: str,
    ) -> list[dict[str, Any]]:
        """List all files belonging to a top-level category ('graph' / 'raw' / 'wiki')."""
        rows = self.conn.execute(
            "SELECT id, kb_id, category, relative_path, file_name, "
            "file_size, checksum, created_at, updated_at "
            "FROM files WHERE kb_id = ? AND category = ? "
            "ORDER BY relative_path",
            (kb_id, category),
        ).fetchall()
        return [dict(r) for r in rows]

    def list_all_file_paths(self, kb_id: int) -> list[str]:
        rows = self.conn.execute(
            "SELECT relative_path FROM files WHERE kb_id = ? ORDER BY relative_path",
            (kb_id,),
        ).fetchall()
        return [r["relative_path"] for r in rows]

    def count_files(self, kb_id: int) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) AS cnt FROM files WHERE kb_id = ?", (kb_id,)
        ).fetchone()
        return row["cnt"] if row else 0

    def total_size(self, kb_id: int) -> int:
        row = self.conn.execute(
            "SELECT COALESCE(SUM(file_size), 0) AS total FROM files WHERE kb_id = ?",
            (kb_id,),
        ).fetchone()
        return row["total"] if row else 0

    # ── Full-text search ──────────────────────────────────────────────

    def search(self, kb_id: int, keyword: str) -> list[dict[str, Any]]:
        """Full-text search across file paths and text content."""
        rows = self.conn.execute(
            """SELECT f.id, f.kb_id, f.category, f.relative_path, f.file_name,
                      f.file_size, f.checksum, f.created_at, f.updated_at,
                      snippet(files_fts, 1, '<mark>', '</mark>', '…', 60) AS snippet
               FROM files_fts
               JOIN files f ON f.id = files_fts.rowid
               WHERE f.kb_id = ? AND files_fts MATCH ?
               ORDER BY rank""",
            (kb_id, keyword),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Directory tree ────────────────────────────────────────────────

    def get_directory_tree(self, kb_id: int) -> dict[str, Any]:
        """Return a nested dict representing the file tree of a kb.

        Example:
            {
              "graph": {
                "graph.json": 123,
                "graph.html": 124,
                ...
              },
              "raw": { ... },
              "wiki": {
                "concepts": { "全面从严治党.md": 125, ... },
                "index.md": 126,
                ...
              }
            }

        Leaf values are file_id integers.
        """
        tree: dict[str, Any] = {}
        rows = self.conn.execute(
            "SELECT id, relative_path FROM files WHERE kb_id = ? ORDER BY relative_path",
            (kb_id,),
        ).fetchall()

        for row in rows:
            parts = Path(row["relative_path"]).parts
            node = tree
            for part in parts[:-1]:
                node = node.setdefault(part, {})
            node[parts[-1]] = row["id"]

        return tree

    def _write_tree(self, kb_id: int, output_dir: Path, tree: dict[str, Any]) -> None:
        for name, value in tree.items():
            target = output_dir / name
            if isinstance(value, dict):
                target.mkdir(parents=True, exist_ok=True)
                self._write_tree(kb_id, target, value)
            else:
                row = self.conn.execute(
                    "SELECT content FROM files WHERE id = ?", (value,)
                ).fetchone()
                if row and row["content"] is not None:
                    target.write_bytes(row["content"])

    def export_kb(self, kb_id: int, output_dir: str | Path) -> int:
        """Reconstruct directory structure to disk. Returns number of files written."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        tree = self.get_directory_tree(kb_id)
        self._write_tree(kb_id, output_dir, tree)
        return self.count_files(kb_id)

    # ── Import from disk ──────────────────────────────────────────────

    def import_directory(self, kb_id: int, dir_path: str | Path, strip_prefix: bool = True) -> int:
        """Import all files under dir_path into the kb.

        If strip_prefix is True, the top-level directory name is kept (e.g.
        importing 'wiki/' preserves paths like 'wiki/index.md').  If False,
        the full absolute/relative path is stored.
        """
        dir_path = Path(dir_path)
        if not dir_path.is_dir():
            raise FileNotFoundError(f"Directory not found: {dir_path}")

        count = 0
        for filepath in dir_path.rglob("*"):
            if filepath.is_file():
                if strip_prefix and dir_path.parent != Path("."):
                    rel = str(filepath.relative_to(dir_path.parent))
                else:
                    rel = str(filepath)
                self.add_file_from_disk(kb_id, rel)
                count += 1
        return count

    def import_kb_from_disk(self, kb_name: str, root: str | Path | None = None) -> int:
        """Create a kb and import graph/, raw/, wiki/ from the given root.

        If root is None, REPO_ROOT is used.
        """
        root = Path(root) if root else REPO_ROOT
        kid = self.create_kb(kb_name, f"Imported from {root}")

        for subdir in ("graph", "raw", "wiki"):
            d = root / subdir
            if d.is_dir():
                self.import_directory(kid, d)

        return kid

    # ── Diff helpers ──────────────────────────────────────────────────

    def diff_checksums(self, kb_id: int) -> list[dict[str, Any]]:
        """Compare stored checksums against files currently on disk (relative to REPO_ROOT)."""
        changed: list[dict[str, Any]] = []
        rows = self.conn.execute(
            "SELECT id, relative_path, checksum FROM files WHERE kb_id = ?",
            (kb_id,),
        ).fetchall()

        for row in rows:
            disk_path = REPO_ROOT / row["relative_path"]
            if disk_path.is_file():
                disk_checksum = hashlib.sha256(disk_path.read_bytes()).hexdigest()
                if disk_checksum != row["checksum"]:
                    changed.append({
                        "file_id": row["id"],
                        "relative_path": row["relative_path"],
                        "db_checksum": row["checksum"],
                        "disk_checksum": disk_checksum,
                    })
            else:
                changed.append({
                    "file_id": row["id"],
                    "relative_path": row["relative_path"],
                    "db_checksum": row["checksum"],
                    "disk_checksum": None,
                    "missing_on_disk": True,
                })
        return changed

    # ── Stats ─────────────────────────────────────────────────────────

    def kb_stats(self, kb_id: int) -> dict[str, Any]:
        """Return summary stats for a kb."""
        kb = self.get_kb(kb_id)
        file_count = self.count_files(kb_id)
        total_bytes = self.total_size(kb_id)

        rows = self.conn.execute(
            "SELECT category, COUNT(*) AS cnt FROM files WHERE kb_id = ? "
            "GROUP BY category ORDER BY category",
            (kb_id,),
        ).fetchall()
        by_category = {r["category"]: r["cnt"] for r in rows}

        return {
            "kb": kb,
            "file_count": file_count,
            "total_bytes": total_bytes,
            "by_category": by_category,
        }


def main() -> None:
    """Quick smoke-test / demo."""
    db_path = REPO_ROOT / "storage" / "wiki.db"
    if db_path.exists():
        db_path.unlink()

    db = WikiStorage(db_path)

    kid = db.import_kb_from_disk("test-kb")
    logger.info("Created kb #%d", kid)

    stats = db.kb_stats(kid)
    logger.info("  Files: %d, Size: %d bytes", stats['file_count'], stats['total_bytes'])
    logger.info("  By category: %s", stats['by_category'])

    all_paths = db.list_all_file_paths(kid)
    logger.info("  Sample paths: %s...", all_paths[:5])

    wiki_path = all_paths[0]
    text = db.get_file_text_by_path(kid, wiki_path)
    if text:
        logger.info("  First 80 chars of %s: %s...", wiki_path, text[:80])

    tree = db.get_directory_tree(kid)
    logger.info("  Top-level dirs in tree: %s", list(tree.keys()))

    results = db.search(kid, "wiki")
    logger.info("  Search 'wiki' -> %d results", len(results))

    db.close()
    logger.info("Done.")


if __name__ == "__main__":
    main()