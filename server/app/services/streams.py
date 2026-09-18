"""SSE event generators for build / update / import workflows."""
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import UploadFile

from app.deps import get_db, get_engine
from tools.logger import get_logger
from wiki_engine.constants import DEFAULT_UPLOAD_DIR

logger = get_logger(__name__)


def set_kb_state(kb_id: int, state: str) -> None:
    db = get_db()
    try:
        db.set_kb_state(kb_id, state)
    finally:
        db.close()


def save_upload_to_temp(upload_file: UploadFile) -> Path:
    """Read UploadFile into a NamedTemporaryFile for later SSE generators."""
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        contents = upload_file.file.read()
        tmp.write(contents)
        return Path(tmp.name)


def stream_build_events(kb_id: int):
    """构建知识库 SSE 事件流，并管理 KB 状态。"""
    set_kb_state(kb_id, "building")
    engine = get_engine()
    final_state = "unbuilt"
    try:
        for event in engine.build_knowledge_base_stream(kb_id):
            ev = event.get("event")
            if ev == "done":
                final_state = "completed"
            elif ev == "error":
                final_state = "unbuilt"
            yield event
    except Exception as e:
        logger.exception("Build stream failed: kb_id=%s", kb_id)
        final_state = "unbuilt"
        yield {"event": "error", "message": str(e)}
    finally:
        engine.close()
        set_kb_state(kb_id, final_state)


def stream_update_events(kb_id: int, source_dir: str | None):
    """增量更新知识库 SSE 事件流，并管理 KB 状态。"""
    set_kb_state(kb_id, "building")
    engine = get_engine()
    final_state = "unbuilt"
    try:
        for event in engine.update_knowledge_base_stream(kb_id, source_dir):
            ev = event.get("event")
            if ev == "done":
                final_state = "completed"
            elif ev == "error":
                final_state = "unbuilt"
            yield event
    except Exception as e:
        logger.exception("Update stream failed: kb_id=%s", kb_id)
        final_state = "unbuilt"
        yield {"event": "error", "message": str(e)}
    finally:
        engine.close()
        set_kb_state(kb_id, final_state)


def stream_import_dir_events(kb_id: int, source_dir: str):
    """目录导入 SSE 事件流。"""
    engine = get_engine()
    try:
        for event in engine.import_raw_files_stream(kb_id, source_dir):
            yield event
    finally:
        engine.close()


def stream_import_zip_events(kb_id: int, tmp_path: Path):
    """ZIP 上传导入 SSE 事件流（tmp_path 须在请求上下文内预先落盘）。"""
    import zipfile

    db = get_db()
    try:
        kb = db.get_kb(kb_id)
        if not kb:
            yield {"event": "error", "message": "知识库不存在"}
            return

        extract_dir = DEFAULT_UPLOAD_DIR / kb["name"]
        extract_dir.mkdir(parents=True, exist_ok=True)

        try:
            yield {"event": "extracting", "path": str(extract_dir)}
            with zipfile.ZipFile(str(tmp_path), "r") as zf:
                zf.extractall(str(extract_dir))

            engine = get_engine()
            try:
                logger.info("Importing files from %s (stream)", extract_dir)
                for event in engine.import_raw_files_stream(kb_id, str(extract_dir)):
                    yield event
            finally:
                engine.close()
        finally:
            if tmp_path.exists():
                tmp_path.unlink()
    finally:
        db.close()


def stream_import_kb_events(tmp_path: Path, kb_name: str):
    """Import KB ZIP SSE 事件流（tmp_path 须在请求上下文内预先落盘）。"""
    import zipfile

    db = get_db()
    try:
        existing = db.get_kb_by_name(kb_name)
        if existing:
            yield {"event": "error", "message": f'知识库 "{kb_name}" 已存在'}
            return

        kb_id = db.create_kb(kb_name)

        try:
            with zipfile.ZipFile(str(tmp_path), "r") as zf:
                entries = [info for info in zf.infolist() if not info.is_dir()]
                total = len(entries)
                yield {
                    "event": "start",
                    "kb_name": kb_name,
                    "total": total,
                    "task": "import_kb",
                }

                file_count = 0
                for index, info in enumerate(entries, start=1):
                    rel_path = info.filename.replace("\\", "/")
                    yield {
                        "event": "file_start",
                        "file": rel_path,
                        "index": index,
                        "total": total,
                    }
                    try:
                        content = zf.read(info.filename)
                        db.add_file(kb_id, rel_path, content)
                        file_count += 1
                        yield {"event": "file_imported", "file": rel_path}
                    except Exception as e:
                        logger.error("Import KB file error: %s: %s", rel_path, e)
                        yield {"event": "file_error", "file": rel_path, "error": str(e)}

                yield {
                    "event": "done",
                    "result": {
                        "kb_id": kb_id,
                        "kb_name": kb_name,
                        "file_count": file_count,
                    },
                }
        finally:
            if tmp_path.exists():
                tmp_path.unlink()
    finally:
        db.close()
