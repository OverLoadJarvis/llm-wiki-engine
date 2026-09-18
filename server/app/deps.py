"""Shared paths and DB/engine factories."""
from __future__ import annotations

from pathlib import Path

from storage.db import WikiStorage
from wiki_engine import LLMWikiEngine

# server/app/deps.py → parent.parent = server/
REPO_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = REPO_ROOT.parent
DB_PATH = REPO_ROOT / "storage" / "wiki.db"

_UI_DIST_CANDIDATES = (
    PROJECT_ROOT / "ui-dist",
    PROJECT_ROOT / "ui-apple" / "dist",
)
_LEGACY_WEB_DIST = PROJECT_ROOT / "web-dist"


def resolve_frontend_dist() -> Path | None:
    for candidate in _UI_DIST_CANDIDATES:
        if (candidate / "index.html").is_file():
            return candidate
    if (_LEGACY_WEB_DIST / "index.html").is_file():
        return _LEGACY_WEB_DIST
    return None


def get_db() -> WikiStorage:
    return WikiStorage(str(DB_PATH))


def get_engine() -> LLMWikiEngine:
    return LLMWikiEngine(str(DB_PATH))


def init_llm_config_cache() -> None:
    from tools.llm_config import reload_from_storage

    db = get_db()
    try:
        reload_from_storage(db)
    finally:
        db.close()
