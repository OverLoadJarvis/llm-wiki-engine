-- SQLite schema for storing graph / raw / wiki file trees as kbs.
-- Each kb holds a snapshot of the three directories with full path preservation,
-- enabling search, retrieval, and directory-structure reconstruction.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS kbs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    description TEXT    DEFAULT '',
    state       TEXT    NOT NULL DEFAULT 'unbuilt',
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS files (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    kb_id        INTEGER NOT NULL,
    category     TEXT    NOT NULL DEFAULT '', -- parent dir: 'graph', 'wiki/concepts', 'raw' etc.
    relative_path TEXT   NOT NULL,            -- e.g. 'wiki/concepts/全面从严治党.md'
    file_name    TEXT    NOT NULL,             -- basename: '全面从严治党.md'
    content      BLOB,                        -- raw file bytes (text or binary)
    content_text TEXT,                        -- text version for FTS; NULL for pure-binary files
    file_size    INTEGER NOT NULL DEFAULT 0,
    checksum     TEXT,                        -- SHA-256 hex digest
    created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (kb_id) REFERENCES kbs(id) ON DELETE CASCADE,
    UNIQUE(kb_id, relative_path)
);

CREATE INDEX IF NOT EXISTS idx_files_kb    ON files(kb_id);
CREATE INDEX IF NOT EXISTS idx_files_path  ON files(kb_id, relative_path);
CREATE INDEX IF NOT EXISTS idx_files_category ON files(kb_id, category);

CREATE VIRTUAL TABLE IF NOT EXISTS files_fts USING fts5(
    relative_path,
    content_text,
    content='files',
    content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS files_ai AFTER INSERT ON files BEGIN
    INSERT INTO files_fts(rowid, relative_path, content_text)
    VALUES (new.id, new.relative_path, new.content_text);
END;

CREATE TRIGGER IF NOT EXISTS files_ad AFTER DELETE ON files BEGIN
    INSERT INTO files_fts(files_fts, rowid, relative_path, content_text)
    VALUES ('delete', old.id, old.relative_path, old.content_text);
END;

CREATE TRIGGER IF NOT EXISTS files_au AFTER UPDATE ON files BEGIN
    INSERT INTO files_fts(files_fts, rowid, relative_path, content_text)
    VALUES ('delete', old.id, old.relative_path, old.content_text);
    INSERT INTO files_fts(rowid, relative_path, content_text)
    VALUES (new.id, new.relative_path, new.content_text);
END;

-- Global LLM settings (single row, id must be 1)
CREATE TABLE IF NOT EXISTS llm_settings (
    id         INTEGER PRIMARY KEY CHECK (id = 1),
    base_url   TEXT NOT NULL DEFAULT '',
    api_key    TEXT NOT NULL DEFAULT '',
    model      TEXT NOT NULL DEFAULT '',
    model_fast TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);