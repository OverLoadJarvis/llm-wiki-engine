"""File upload routes (KB-scoped and external)."""
from __future__ import annotations

import re
import shutil
import tempfile
import zipfile
from pathlib import Path

from fastapi import APIRouter, File, Form, Query, UploadFile
from fastapi.responses import JSONResponse

from app.deps import get_db, get_engine
from tools.logger import get_logger
from wiki_engine.constants import DEFAULT_UPLOAD_DIR

logger = get_logger(__name__)

router = APIRouter(tags=["upload"])


def _secure_filename(filename: str) -> str:
    """Basename-only sanitize (no Flask/werkzeug dependency)."""
    name = Path(filename).name
    name = name.replace("\\", "/").split("/")[-1]
    name = re.sub(r"[^\w.\-]+", "_", name, flags=re.UNICODE)
    return name or "upload.bin"


@router.post("/api/kbs/{kb_id}/upload-file")
def upload_file_to_kb(
    kb_id: int,
    file: UploadFile = File(...),
    update: bool = Query(False),
):
    if not file.filename:
        return JSONResponse({"error": "未提供文件"}, status_code=400)

    db = get_db()
    try:
        kb = db.get_kb(kb_id)
        if not kb:
            return JSONResponse({"error": "知识库不存在"}, status_code=404)

        safe_name = _secure_filename(file.filename)
        is_zip = safe_name.lower().endswith(".zip")

        upload_dir = DEFAULT_UPLOAD_DIR / kb["name"]
        upload_dir.mkdir(parents=True, exist_ok=True)

        engine = get_engine()
        try:
            if is_zip:
                extract_dir = upload_dir / f"_tmp_{safe_name}"
                extract_dir.mkdir(parents=True, exist_ok=True)

                with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                    tmp.write(file.file.read())
                    tmp_path = Path(tmp.name)

                try:
                    with zipfile.ZipFile(str(tmp_path), "r") as zf:
                        zf.extractall(str(extract_dir))

                    import_result = engine.import_raw_files(kb_id, str(extract_dir))
                    file_count = import_result.get("imported", 0)
                finally:
                    if tmp_path.exists():
                        tmp_path.unlink()
                    if extract_dir.exists():
                        shutil.rmtree(str(extract_dir), ignore_errors=True)
            else:
                dest_path = upload_dir / safe_name
                dest_path.write_bytes(file.file.read())

                import_result = engine.import_raw_files(kb_id, str(upload_dir))
                file_count = import_result.get("imported", 0)

                if dest_path.exists():
                    dest_path.unlink()

            update_result = None
            if update:
                update_result = engine.update_knowledge_base(kb_id)

            return {
                "file_name": safe_name,
                "import_result": import_result,
                "file_count": file_count,
                "update_result": update_result,
            }
        finally:
            engine.close()
    finally:
        db.close()


@router.post("/api/external/upload")
def external_upload(
    kb_name: str = Form(""),
    files: list[UploadFile] | None = File(None),
):
    kb_name = (kb_name or "").strip()
    if not kb_name:
        return JSONResponse({"error": "缺少 kb_name 参数"}, status_code=400)

    uploaded = files or []
    if not uploaded or all(not f.filename for f in uploaded):
        return JSONResponse({"error": "未提供任何文件"}, status_code=400)

    upload_dir = DEFAULT_UPLOAD_DIR / kb_name
    upload_dir.mkdir(parents=True, exist_ok=True)

    saved_files = []
    for f in uploaded:
        if not f.filename:
            continue
        safe_name = _secure_filename(f.filename)
        dest_path = upload_dir / safe_name
        dest_path.write_bytes(f.file.read())
        saved_files.append(safe_name)

    if not saved_files:
        return JSONResponse({"error": "没有有效的文件被保存"}, status_code=400)

    db = get_db()
    try:
        kb = db.get_kb_by_name(kb_name)
        if kb:
            kb_id = kb["id"]
        else:
            kb_id = db.create_kb(kb_name, f"外部上传: {kb_name}")

        engine = get_engine()
        try:
            import_result = engine.import_raw_files(kb_id, str(upload_dir))
            return {
                "kb_id": kb_id,
                "kb_name": kb_name,
                "upload_dir": str(upload_dir),
                "files": saved_files,
                "import_result": import_result,
            }
        finally:
            engine.close()
            for fname in saved_files:
                fp = upload_dir / fname
                if fp.exists():
                    fp.unlink()
    finally:
        db.close()
