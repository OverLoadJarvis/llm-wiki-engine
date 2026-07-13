"""知识库管理与文件导入模块

提供知识库的 CRUD 操作，以及将本地文件导入 SQLite 的功能。

类:
    KbManager   — 知识库生命周期管理
    FileImporter — 原始文件扫描、格式转换与导入
"""

import tempfile
from pathlib import Path
from typing import Any

from storage.db import WikiStorage
from wiki_engine.constants import (
    ALL_SUPPORTED_EXTENSIONS,
    CONVERTIBLE_EXTENSIONS,
)
from tools.logger import get_logger

logger = get_logger(__name__)


class KbManager:
    """知识库生命周期管理。

    封装对 WikiStorage 的知识库 CRUD 操作，提供统一的知识库管理接口。

    Args:
        db: WikiStorage 数据库实例
    """

    def __init__(self, db: WikiStorage) -> None:
        self.db = db

    def create_kb(self, name: str, description: str = "") -> int:
        """创建新知识库。

        Args:
            name: 知识库名称
            description: 知识库描述

        Returns:
            新创建知识库的 ID
        """
        return self.db.create_kb(name, description)

    def get_kb(self, kb_id: int) -> dict[str, Any] | None:
        """获取知识库信息。

        Args:
            kb_id: 知识库 ID

        Returns:
            知识库信息字典，若不存在返回 ``None``
        """
        return self.db.get_kb(kb_id)

    def list_kbs(self) -> list[dict[str, Any]]:
        """列出所有知识库。

        Returns:
            知识库信息字典列表
        """
        return self.db.list_kbs()

    def delete_kb(self, kb_id: int) -> bool:
        """删除知识库及其所有关联的文件。

        Args:
            kb_id: 知识库 ID

        Returns:
            是否删除成功

        Note:
            删除知识库时会同步删除所有关联的文件记录（包括 raw/、wiki/、graph/ 等）。
        """
        return self.db.delete_kb(kb_id)


class FileImporter:
    """原始文件扫描、格式转换与导入。

    负责将本地目录中的文件扫描并转换为 Markdown 后存入 SQLite。
    支持 Markdown 直接导入，以及通过 markitdown 将其他格式转换为 Markdown。

    Args:
        db: WikiStorage 数据库实例
    """

    def __init__(self, db: WikiStorage) -> None:
        self.db = db

    def import_raw_files(self, kb_id: int, source_dir: str | Path) -> dict[str, int]:
        """将本地目录中的原始文件扫描并转换为 Markdown 后存入 SQLite。"""
        result: dict[str, int] | None = None
        for event in self.import_raw_files_stream(kb_id, source_dir):
            if event.get("event") == "done":
                result = event.get("result")
            elif event.get("event") == "error":
                raise ValueError(event.get("message", "导入失败"))
        if result is None:
            raise RuntimeError("导入未返回结果")
        return result

    def import_raw_files_stream(
        self, kb_id: int, source_dir: str | Path
    ):
        """流式导入本地目录中的原始文件。"""
        from typing import Iterator

        source_dir = Path(source_dir)
        if not source_dir.is_dir():
            yield {"event": "error", "message": f"目录不存在: {source_dir}"}
            return

        kb = self.db.get_kb(kb_id)
        if not kb:
            yield {"event": "error", "message": f"知识库不存在: {kb_id}"}
            return

        all_files = [f for f in source_dir.rglob("*") if f.is_file()]
        candidates = [
            f for f in all_files
            if not f.name.startswith(".") and f.suffix.lower() in ALL_SUPPORTED_EXTENSIONS
        ]
        total = len(candidates)

        logger.info("[import_raw_files] 开始扫描目录: %s", source_dir)
        yield {"event": "start", "kb_name": kb["name"], "total": total, "task": "import"}

        stats = {"imported": 0, "skipped": 0, "errors": 0}
        index = 0

        for filepath in source_dir.rglob("*"):
            if not filepath.is_file():
                continue
            rel_display = filepath.relative_to(source_dir).as_posix()
            if filepath.name.startswith("."):
                logger.info("  [跳过] 隐藏文件: %s", rel_display)
                stats["skipped"] += 1
                continue

            ext = filepath.suffix.lower()
            if ext not in ALL_SUPPORTED_EXTENSIONS:
                logger.info("  [跳过] 不支持的格式 (%s): %s", ext, rel_display)
                stats["skipped"] += 1
                continue

            index += 1
            yield {"event": "file_start", "file": rel_display, "index": index, "total": total}

            try:
                rel = filepath.relative_to(source_dir)
                if ext == ".md":
                    md_content = filepath.read_text(encoding="utf-8", errors="replace")
                    rel_path = f"raw/{rel.as_posix()}"
                    self.db.add_file(kb_id, rel_path, md_content)
                    logger.info("  [导入] %s -> %s", rel_display, rel_path)
                    stats["imported"] += 1
                    yield {"event": "file_imported", "file": rel_display}
                else:
                    content_bytes = filepath.read_bytes()
                    md_content = self.convert_to_md(content_bytes, filepath.name)
                    if md_content is None:
                        logger.info("  [跳过] 转换失败: %s", rel_display)
                        stats["skipped"] += 1
                        yield {"event": "file_skipped", "file": rel_display, "reason": "转换失败"}
                        continue
                    rel_path = f"raw/{rel.with_suffix('.md').as_posix()}"
                    self.db.add_file(kb_id, rel_path, md_content)
                    logger.info("  [导入] %s -> %s (已转换为 Markdown)", rel_display, rel_path)
                    stats["imported"] += 1
                    yield {"event": "file_imported", "file": rel_display}
            except Exception as e:
                logger.error("  [错误] %s: %s", rel_display, e)
                stats["errors"] += 1
                yield {"event": "file_error", "file": rel_display, "error": str(e)}

        logger.info(
            "[import_raw_files] 完成: 导入 %d, 跳过 %d, 错误 %d",
            stats["imported"], stats["skipped"], stats["errors"],
        )
        yield {"event": "done", "result": stats}

    def add_raw_content(self, kb_id: int, filename: str, content: str | bytes) -> int:
        """添加单个原始文件内容到 SQLite。

        Args:
            kb_id: 知识库 ID
            filename: 文件名（含扩展名）
            content: 文件内容（文本或字节）

        Returns:
            新创建的文件记录 ID
        """
        rel_path = f"raw/{filename}"
        return self.db.add_file(kb_id, rel_path, content)

    @staticmethod
    def convert_to_md(content_bytes: bytes, filename: str) -> str | None:
        """将非 Markdown 文件内容转换为 Markdown。

        使用 markitdown 库进行格式转换。转换过程中会创建临时文件，
        转换完成后自动清理。

        Args:
            content_bytes: 文件的原始字节内容
            filename: 原始文件名（含扩展名），用于判断格式

        Returns:
            转换后的 Markdown 文本；若格式不支持或转换失败，返回 ``None``
        """
        ext = Path(filename).suffix.lower()
        if ext == ".md":
            return content_bytes.decode("utf-8", errors="replace")
        if ext not in CONVERTIBLE_EXTENSIONS:
            logger.warning("    [convert_to_md] 不支持转换的格式: %s", ext)
            return None

        try:
            from markitdown import MarkItDown
        except ImportError:
            logger.warning("    [convert_to_md] markitdown 库未安装，无法转换 %s", filename)
            return None

        logger.info("    [convert_to_md] 正在转换 %s (%d bytes)...", filename, len(content_bytes))
        md = MarkItDown(enable_plugins=False)
        tmp_path = None
        try:
            tmp_path = Path(tempfile.mktemp(suffix=ext))
            tmp_path.write_bytes(content_bytes)
            result = md.convert(str(tmp_path))
            logger.info("    [convert_to_md] 转换成功: %s -> %d chars", filename, len(result.text_content))
            return result.text_content
        except Exception as e:
            logger.error("    [convert_to_md] 转换失败 %s: %s", filename, e)
            return None
        finally:
            if tmp_path and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass