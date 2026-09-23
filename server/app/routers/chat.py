"""Knowledge-base librarian chat agent (LangGraph ReAct) SSE endpoint."""
from __future__ import annotations

from fastapi import APIRouter

from app.deps import get_db
from app.schemas import ChatBody
from app.sse import format_sse, sse_raw_response
from tools.logger import get_logger
from wiki_engine.chat_agent import stream_librarian_events

logger = get_logger(__name__)

router = APIRouter(prefix="/api/kbs", tags=["chat"])


@router.post("/{kb_id}/chat")
def chat_with_librarian(kb_id: int, body: ChatBody):
    messages = [{"role": m.role, "content": m.content} for m in (body.messages or [])]
    logger.info(
        "POST /api/kbs/%s/chat: messages=%d",
        kb_id,
        len(messages),
    )

    def generate():
        db = get_db()
        try:
            for event in stream_librarian_events(db, kb_id, messages):
                name = event.get("event") or "message"
                payload = {k: v for k, v in event.items() if k != "event"}
                yield format_sse(str(name), payload)
        except Exception as e:
            logger.exception("Chat stream failed: kb_id=%s", kb_id)
            yield format_sse("error", {"error": str(e)})
            yield format_sse("done", {})
        finally:
            db.close()

    return sse_raw_response(generate())
