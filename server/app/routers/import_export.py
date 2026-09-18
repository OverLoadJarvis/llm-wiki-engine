"""Import / export knowledge-base routes."""
from __future__ import annotations

import io
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, File, Query, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

from app.deps import get_db, get_engine
from app.schemas import ImportDirBody
from app.services.streams import (
    save_upload_to_temp,
    stream_import_dir_events,
    stream_import_kb_events,
    stream_import_zip_events,
)
from app.sse import sse_response
from tools.logger import get_logger
from wiki_engine.constants import DEFAULT_UPLOAD_DIR

logger = get_logger(__name__)

router = APIRouter(prefix="/api/kbs", tags=["import-export"])


@router.post("/import")
def import_kb(
    file: UploadFile = File(...),
    stream: bool = Query(False),
):
    """Import a full KB ZIP at POST /api/kbs/import (before /{kb_id}/... routes)."""
    if not file.filename:
        return JSONResponse({"error": "未提供文件"}, status_code=400)

    if not file.filename.lower().endswith(".zip"):
        return JSONResponse({"error": "仅支持 .zip 格式的压缩包"}, status_code=400)

    kb_name = Path(file.filename).stem

    if stream:
        db = get_db()
        try:
            existing = db.get_kb_by_name(kb_name)
            if existing:
                return JSONResponse(
                    {"error": f'知识库 "{kb_name}" 已存在'},
                    status_code=409,
                )
        finally:
            db.close()
        tmp_path = save_upload_to_temp(file)
        return sse_response(stream_import_kb_events(tmp_path, kb_name))

    db = get_db()
    try:
        existing = db.get_kb_by_name(kb_name)
        if existing:
            return JSONResponse(
                {"error": f'知识库 "{kb_name}" 已存在'},
                status_code=409,
            )

        kb_id = db.create_kb(kb_name)

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            tmp.write(file.file.read())
            tmp_path = Path(tmp.name)

        try:
            with zipfile.ZipFile(str(tmp_path), "r") as zf:
                file_count = 0
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    rel_path = info.filename.replace("\\", "/")
                    content = zf.read(info.filename)
                    db.add_file(kb_id, rel_path, content)
                    file_count += 1
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

        return JSONResponse(
            {
                "kb_id": kb_id,
                "kb_name": kb_name,
                "file_count": file_count,
            },
            status_code=201,
        )
    finally:
        db.close()


@router.post("/{kb_id}/import")
def import_files(kb_id: int, body: ImportDirBody):
    source_dir = body.source_dir
    if not source_dir:
        return JSONResponse({"error": "缺少 source_dir 参数"}, status_code=400)

    if body.stream:
        return sse_response(stream_import_dir_events(kb_id, source_dir))

    engine = get_engine()
    try:
        return engine.import_raw_files(kb_id, source_dir)
    finally:
        engine.close()


@router.post("/{kb_id}/import-zip")
def import_zip(
    kb_id: int,
    file: UploadFile = File(...),
    stream: bool = Query(False),
):
    if not file.filename:
        return JSONResponse({"error": "未提供文件"}, status_code=400)

    if not file.filename.lower().endswith(".zip"):
        return JSONResponse({"error": "仅支持 .zip 格式的压缩包"}, status_code=400)

    if stream:
        tmp_path = save_upload_to_temp(file)
        return sse_response(stream_import_zip_events(kb_id, tmp_path))

    db = get_db()
    try:
        kb = db.get_kb(kb_id)
        if not kb:
            return JSONResponse({"error": "知识库不存在"}, status_code=404)

        extract_dir = DEFAULT_UPLOAD_DIR / kb["name"]
        extract_dir.mkdir(parents=True, exist_ok=True)

        import_result: dict = {}
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            tmp.write(file.file.read())
            tmp_path = Path(tmp.name)

        try:
            with zipfile.ZipFile(str(tmp_path), "r") as zf:
                zf.extractall(str(extract_dir))

            engine = get_engine()
            try:
                logger.info("Importing files from %s", extract_dir)
                import_result = engine.import_raw_files(kb_id, str(extract_dir))
            finally:
                engine.close()
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

        return import_result
    finally:
        db.close()


@router.get("/{kb_id}/export")
def export_kb(kb_id: int):
    db = get_db()
    try:
        kb = db.get_kb(kb_id)
        if not kb:
            return JSONResponse({"error": "知识库不存在"}, status_code=404)

        prefixes = ("raw/", "wiki/", "graph/")
        all_files = []
        for prefix in prefixes:
            files = db.list_files(kb_id, prefix)
            all_files.extend(files)

        if not all_files:
            return JSONResponse({"error": "知识库没有可导出的文件"}, status_code=404)

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in all_files:
                rel_path = f["relative_path"]
                row = db.conn.execute(
                    "SELECT content FROM files WHERE kb_id = ? AND relative_path = ?",
                    (kb_id, rel_path),
                ).fetchone()
                content = row["content"] if row and row["content"] else b""
                zf.writestr(rel_path, content)

        buf.seek(0)
        kb_name = kb["name"]
        safe_name = f"kb_{kb_id}_export.zip"
        encoded_name = quote(kb_name, safe="")
        return StreamingResponse(
            buf,
            media_type="application/zip",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{safe_name}"; '
                    f"filename*=UTF-8''{encoded_name}_export.zip"
                ),
            },
        )
    finally:
        db.close()
