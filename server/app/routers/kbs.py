"""Knowledge-base CRUD and instruction routes."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.deps import get_db
from app.schemas import CreateKbBody, InstructionBody
from tools.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/kbs", tags=["kbs"])


@router.get("")
def list_kbs():
    db = get_db()
    try:
        return db.list_kbs()
    finally:
        db.close()


@router.post("")
def create_kb(body: CreateKbBody):
    db = get_db()
    try:
        kid = db.create_kb(body.name, body.description)
        return JSONResponse({"id": kid, "name": body.name}, status_code=201)
    finally:
        db.close()


@router.get("/{kb_id}")
def get_kb(kb_id: int):
    db = get_db()
    try:
        kb = db.get_kb(kb_id)
        if not kb:
            return JSONResponse({"error": "知识库不存在"}, status_code=404)
        return kb
    finally:
        db.close()


@router.delete("/{kb_id}")
def delete_kb(kb_id: int):
    db = get_db()
    try:
        ok = db.delete_kb(kb_id)
        return {"deleted": ok}
    finally:
        db.close()


@router.get("/{kb_id}/stats")
def kb_stats(kb_id: int):
    db = get_db()
    try:
        return db.kb_stats(kb_id)
    finally:
        db.close()


@router.get("/{kb_id}/instruction")
def get_instruction(kb_id: int):
    db = get_db()
    try:
        instruction = db.get_ingest_instruction(kb_id)
        return {"instruction": instruction}
    finally:
        db.close()


@router.put("/{kb_id}/instruction")
def set_instruction(kb_id: int, body: InstructionBody):
    db = get_db()
    try:
        ok = db.set_ingest_instruction(kb_id, body.instruction)
        if not ok:
            return JSONResponse({"error": "知识库不存在"}, status_code=404)
        return {"instruction": body.instruction}
    finally:
        db.close()
