"""Standard SSE helpers: event: <name> + data: <json payload>."""
from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from fastapi.responses import StreamingResponse
from tools.logger import get_logger

logger = get_logger(__name__)

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


def format_sse(event: str, data: dict[str, Any] | None = None) -> str:
    """Build one SSE message. Payload must not include an 'event' key."""
    payload = data or {}
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def iter_dict_events(event_iter: Iterator[dict[str, Any]]) -> Iterator[str]:
    """Convert legacy dict events {event, ...} into standard SSE frames."""
    try:
        for item in event_iter:
            if not isinstance(item, dict):
                continue
            name = item.get("event") or "message"
            payload = {k: v for k, v in item.items() if k != "event"}
            yield format_sse(str(name), payload)
    except Exception as e:
        logger.exception("SSE stream error")
        yield format_sse("error", {"message": str(e)})


def sse_response(event_iter: Iterator[dict[str, Any]]) -> StreamingResponse:
    return StreamingResponse(
        iter_dict_events(event_iter),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


def sse_raw_response(line_iter: Iterator[str]) -> StreamingResponse:
    return StreamingResponse(
        line_iter,
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
