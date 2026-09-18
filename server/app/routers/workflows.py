"""Build, update, query, health, lint, and graph-build workflows."""
from __future__ import annotations

from fastapi import APIRouter

from app.deps import get_db, get_engine
from app.schemas import BuildBody, QueryBody, UpdateBody
from app.services.streams import stream_build_events, stream_update_events
from app.sse import format_sse, sse_raw_response, sse_response
from tools.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/kbs", tags=["workflows"])


@router.post("/{kb_id}/build")
def build_knowledge_base(kb_id: int, body: BuildBody | None = None):
    body = body or BuildBody()
    if body.stream:
        return sse_response(stream_build_events(kb_id))

    db = get_db()
    try:
        db.set_kb_state(kb_id, "building")
    finally:
        db.close()

    engine = get_engine()
    try:
        result = engine.build_knowledge_base(kb_id)

        db2 = get_db()
        try:
            db2.set_kb_state(kb_id, "completed")
        finally:
            db2.close()

        return result
    except Exception:
        db2 = get_db()
        try:
            db2.set_kb_state(kb_id, "unbuilt")
        finally:
            db2.close()
        raise
    finally:
        engine.close()


@router.post("/{kb_id}/update")
def update_knowledge_base(kb_id: int, body: UpdateBody | None = None):
    body = body or UpdateBody()
    if body.stream:
        return sse_response(stream_update_events(kb_id, body.source_dir))

    db = get_db()
    try:
        db.set_kb_state(kb_id, "building")
    finally:
        db.close()

    engine = get_engine()
    try:
        result = engine.update_knowledge_base(kb_id, body.source_dir)

        db2 = get_db()
        try:
            db2.set_kb_state(kb_id, "completed")
        finally:
            db2.close()

        return result
    except Exception:
        db2 = get_db()
        try:
            db2.set_kb_state(kb_id, "unbuilt")
        finally:
            db2.close()
        raise
    finally:
        engine.close()


@router.post("/{kb_id}/query")
def query_knowledge_base(kb_id: int, body: QueryBody):
    question = body.question
    stream = body.stream
    engine = get_engine()

    if stream:
        def generate():
            try:
                for chunk in engine.query_stream(kb_id, question):
                    yield format_sse("chunk", {"chunk": chunk})
                yield format_sse("done", {})
            except Exception as e:
                yield format_sse("error", {"error": str(e)})
                yield format_sse("done", {})
            finally:
                engine.close()

        return sse_raw_response(generate())

    try:
        answer = engine.query(kb_id, question)
        return {"answer": answer}
    finally:
        engine.close()


@router.get("/{kb_id}/health")
def health_check(kb_id: int):
    engine = get_engine()
    try:
        return engine.health_check(kb_id)
    finally:
        engine.close()


@router.post("/{kb_id}/lint")
def lint_kb(kb_id: int):
    engine = get_engine()
    try:
        report = engine.lint(kb_id, save=True)
        return {"report": report}
    finally:
        engine.close()


@router.post("/{kb_id}/graph/build")
def build_graph(kb_id: int):
    engine = get_engine()
    try:
        return engine.build_graph(kb_id)
    finally:
        engine.close()
