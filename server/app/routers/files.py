"""File tree, content, graph, and search routes."""
from __future__ import annotations

import json

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, PlainTextResponse

from app.deps import get_db
from app.schemas import FileContentBody
from tools.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/kbs", tags=["files"])


@router.get("/{kb_id}/tree")
def get_tree(kb_id: int):
    db = get_db()
    try:
        return db.get_directory_tree(kb_id)
    finally:
        db.close()


@router.get("/{kb_id}/files")
def list_files(kb_id: int, prefix: str = Query("")):
    db = get_db()
    try:
        return db.list_files(kb_id, prefix)
    finally:
        db.close()


@router.get("/{kb_id}/files/{rel_path:path}")
def get_file_content(kb_id: int, rel_path: str):
    db = get_db()
    try:
        text = db.get_file_text_by_path(kb_id, rel_path)
        if text is None:
            return JSONResponse({"error": "文件不存在或内容为空"}, status_code=404)
        return PlainTextResponse(text, media_type="text/plain; charset=utf-8")
    finally:
        db.close()


@router.put("/{kb_id}/files/{rel_path:path}")
def update_file_content(kb_id: int, rel_path: str, body: FileContentBody):
    if body.content is None:
        return JSONResponse({"error": "缺少 content 字段"}, status_code=400)
    db = get_db()
    try:
        ok = db.update_file_by_path(kb_id, rel_path, body.content)
        if not ok:
            return JSONResponse({"error": "文件不存在"}, status_code=404)
        return {"ok": True}
    finally:
        db.close()


@router.get("/{kb_id}/graph")
def get_graph(kb_id: int, file: str = Query("graph/graph.json")):
    db = get_db()
    try:
        graph_json = db.get_file_text_by_path(kb_id, file)
        if not graph_json:
            return JSONResponse({"error": "图谱数据不存在"}, status_code=404)
        try:
            data = json.loads(graph_json)
        except (json.JSONDecodeError, ValueError) as e:
            return JSONResponse(
                {"error": f"图谱文件内容不是合法的 JSON: {e}"},
                status_code=500,
            )
        return data
    finally:
        db.close()


@router.get("/{kb_id}/graph/files")
def list_graph_files(kb_id: int):
    db = get_db()
    try:
        return db.list_files(kb_id, "graph/")
    finally:
        db.close()


@router.get("/{kb_id}/search")
def search_files(kb_id: int, q: str = Query("")):
    db = get_db()
    try:
        if not q:
            return []
        return db.search(kb_id, q)
    finally:
        db.close()
