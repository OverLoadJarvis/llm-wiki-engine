"""Global LLM settings routes."""
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.deps import get_db
from app.schemas import LlmSettingsBody, LlmTestBody
from tools.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _llm_settings_public(stored: dict) -> dict:
    """Build API response without plaintext api_key."""
    from tools.llm_config import get_resolved, mask_api_key

    api_key = stored.get("api_key") or ""
    resolved = get_resolved()
    return {
        "base_url": stored.get("base_url") or "",
        "model": stored.get("model") or "",
        "model_fast": stored.get("model_fast") or "",
        "api_key_set": bool(api_key),
        "api_key_masked": mask_api_key(api_key),
        "resolved_base_url": resolved["base_url"],
        "resolved_model": resolved["model"],
        "resolved_model_fast": resolved["model_fast"],
    }


@router.get("/llm")
def get_llm_settings():
    from tools.llm_config import reload_from_storage

    db = get_db()
    try:
        stored = db.get_llm_settings()
        reload_from_storage(db)
        logger.info(
            "GET /api/settings/llm: api_key_set=%s, base_url=%s, model=%s",
            bool(stored.get("api_key")),
            stored.get("base_url") or "(empty)",
            stored.get("model") or "(empty)",
        )
        return _llm_settings_public(stored)
    finally:
        db.close()


@router.put("/llm")
def put_llm_settings(body: LlmSettingsBody):
    from tools.llm_config import reload_from_storage

    base_url = (body.base_url or "").strip()
    model = (body.model or "").strip()
    model_fast = (body.model_fast or "").strip()
    api_key_in = body.api_key

    db = get_db()
    try:
        existing = db.get_llm_settings()
        if api_key_in is None or api_key_in == "":
            api_key = existing.get("api_key") or ""
        else:
            api_key = str(api_key_in)

        stored = db.set_llm_settings(
            base_url=base_url,
            api_key=api_key,
            model=model,
            model_fast=model_fast,
        )
        reload_from_storage(db)
        logger.info(
            "PUT /api/settings/llm ok: base_url=%s, model=%s, model_fast=%s, api_key_set=%s",
            base_url or "(empty)",
            model or "(empty)",
            model_fast or "(empty)",
            bool(api_key),
        )
        return _llm_settings_public(stored)
    except Exception:
        logger.exception("PUT /api/settings/llm failed")
        return JSONResponse({"error": "保存 LLM 设置失败"}, status_code=500)
    finally:
        db.close()


@router.post("/llm/test")
def test_llm_settings(body: LlmTestBody):
    from tools.llm_config import resolve_for_test

    which = body.which if body.which in ("model", "model_fast") else "model"

    creds = resolve_for_test(
        base_url=body.base_url,
        api_key=body.api_key,
        model=body.model,
        model_fast=body.model_fast,
        which=which,
    )
    model = creds["model"]
    api_base = creds["base_url"]
    api_key = creds["api_key"]

    if not model:
        return {"ok": False, "error": "未指定模型名称"}

    logger.info(
        "POST /api/settings/llm/test start: which=%s, model=%s, api_base=%s",
        which,
        model,
        api_base or "(default)",
    )

    try:
        from litellm import completion
    except ImportError:
        logger.error("litellm not installed")
        return {"ok": False, "error": "litellm 未安装"}

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with OK"}],
        "max_tokens": 8,
        "extra_body": {"enable_thinking": False},
        "headers": {"Accept-Encoding": "identity"},
    }
    if api_base:
        kwargs["api_base"] = api_base
    if api_key:
        kwargs["api_key"] = api_key

    t0 = time.perf_counter()
    try:
        completion(**kwargs)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        logger.info(
            "POST /api/settings/llm/test ok: model=%s, latency_ms=%d",
            model,
            latency_ms,
        )
        return {"ok": True, "latency_ms": latency_ms, "model": model}
    except Exception as e:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        err_msg = str(e)
        logger.warning(
            "POST /api/settings/llm/test failed: model=%s, latency_ms=%d, error=%s",
            model,
            latency_ms,
            err_msg,
        )
        return {"ok": False, "error": err_msg, "model": model, "latency_ms": latency_ms}
