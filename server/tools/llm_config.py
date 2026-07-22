"""Runtime LLM settings: DB overrides env, with in-process cache."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from tools.logger import get_logger

logger = get_logger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_DB_PATH = _REPO_ROOT / "storage" / "wiki.db"

# Raw DB row (may contain empty strings). None = not yet loaded.
_stored: dict[str, str] | None = None


def _empty_stored() -> dict[str, str]:
    return {
        "base_url": "",
        "api_key": "",
        "model": "",
        "model_fast": "",
    }


def update_cache(settings: dict[str, Any] | None) -> None:
    """Replace in-memory stored settings from a DB row / dict."""
    global _stored
    if not settings:
        _stored = _empty_stored()
    else:
        _stored = {
            "base_url": (settings.get("base_url") or "").strip(),
            "api_key": settings.get("api_key") or "",
            "model": (settings.get("model") or "").strip(),
            "model_fast": (settings.get("model_fast") or "").strip(),
        }
    logger.info(
        "LLM config cache updated: base_url=%s, model=%s, model_fast=%s, api_key_set=%s",
        _stored["base_url"] or "(env)",
        _stored["model"] or "(env)",
        _stored["model_fast"] or "(env)",
        bool(_stored["api_key"]),
    )


def reload_from_storage(db: Any) -> None:
    """Load settings from WikiStorage into cache."""
    try:
        update_cache(db.get_llm_settings())
    except Exception:
        logger.exception("Failed to load LLM settings from storage")
        update_cache(None)


def _ensure_loaded() -> None:
    """Lazy-load from default DB path if cache is cold (CLI / MCP)."""
    global _stored
    if _stored is not None:
        return
    try:
        from storage.db import WikiStorage

        db = WikiStorage(str(_DEFAULT_DB_PATH))
        try:
            reload_from_storage(db)
        finally:
            db.close()
    except Exception:
        logger.exception("Lazy load of LLM settings failed; using env only")
        update_cache(None)


def get_stored() -> dict[str, str]:
    """Return raw stored (DB) values; empty string means unset."""
    _ensure_loaded()
    assert _stored is not None
    return dict(_stored)


def get_resolved(
    default_model: str = "claude-3-5-sonnet-latest",
    default_model_fast: str | None = None,
) -> dict[str, str]:
    """
    Resolve effective LLM config: non-empty DB field wins, else env, else default.

    Returns keys: base_url, api_key, model, model_fast
    """
    _ensure_loaded()
    assert _stored is not None

    fast_fallback = default_model_fast if default_model_fast is not None else default_model

    base_url = _stored["base_url"] or (os.getenv("OPENAI_API_BASE") or "").strip()
    api_key = _stored["api_key"] or (os.getenv("OPENAI_API_KEY") or "")
    model = _stored["model"] or (os.getenv("LLM_MODEL") or "").strip() or default_model
    model_fast = (
        _stored["model_fast"]
        or (os.getenv("LLM_MODEL_FAST") or "").strip()
        or fast_fallback
    )

    return {
        "base_url": base_url,
        "api_key": api_key,
        "model": model,
        "model_fast": model_fast,
    }


def mask_api_key(api_key: str) -> str:
    """Mask API key for API responses (never return plaintext)."""
    if not api_key:
        return ""
    if len(api_key) <= 4:
        return "****"
    return "****" + api_key[-4:]


def resolve_for_test(
    base_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    model_fast: str | None = None,
    which: str = "model",
) -> dict[str, str]:
    """
    Build credentials for a connection test from form values.
    Empty api_key / fields fall back to get_resolved().
    """
    resolved = get_resolved()
    eff_base = (base_url or "").strip() or resolved["base_url"]
    form_key = api_key if api_key is not None else ""
    eff_key = form_key if form_key else resolved["api_key"]
    eff_model = (model or "").strip() or resolved["model"]
    eff_fast = (model_fast or "").strip() or resolved["model_fast"]
    chosen = eff_fast if which == "model_fast" else eff_model
    return {
        "base_url": eff_base,
        "api_key": eff_key,
        "model": chosen,
    }
