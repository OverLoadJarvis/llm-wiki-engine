"""项目管理与文件导入模块

提供项目的 CRUD 操作，以及将本地文件导入 SQLite 的功能。

类:
    ProjectManager — 项目生命周期管理
    FileImporter   — 原始文件扫描、格式转换与导入
"""

import tempfile
from pathlib import Path
from typing import Any

from storage.db import WikiStorage
from wiki_engine.constants import (
    ALL_SUPPORTED_EXTENSIONS,
    CONVERTIBLE_EXTENSIONS,
)


class ProjectManager:
    """项目生命周期管理。

    封装对 WikiStorage 的项目 CRUD 操作，提供统一的项目管理接口。

    Args:
        db: WikiStorage 数据库实例
    """

    def __init__(self, db: WikiStorage) -> None:
        self.db = db

    def create_project(self, name: str, description: str = "") -> int:
        """创建新项目。

        Args:
            name: 项目名称
            description: 项目描述

        Returns:
            新创建项目的 ID
        """
        return self.db.create_project(name, description)

    def get_project(self, project_id: int) -> dict[str, Any] | None:
        """获取项目信息。

        Args:
            project_id: 项目 ID

        Returns:
            项目信息字典，若不存在返回 ``None``
        """
        return self.db.get_project(project_id)

    def list_projects(self) -> list[dict[str, Any]]:
        """列出所有项目。

        Returns:
            项目信息字典列表
        """
        return self.db.list_projects()

    def delete_project(self, project_id: int) -> bool:
        """删除项目及其所有关联的文件。

        Args:
            project_id: 项目 ID

        Returns:
            是否删除成功

        Note:
            删除项目时会同步删除所有关联的文件记录（包括 raw/、wiki/、graph/ 等）。
        """
        return self.db.delete_project(project_id)


class FileImporter:
    """原始文件扫描、格式转换与导入。

    负责将本地目录中的文件扫描并转换为 Markdown 后存入 SQLite。
    支持 Markdown 直接导入，以及通过 markitdown 将其他格式转换为 Markdown。

    Args:
        db: WikiStorage 数据库实例
    """

    def __init__(self, db: WikiStorage) -> None:
        self.db = db

    def import_raw_files(self, project_id: int, source_dir: str | Path) -> dict[str, int]:
        """将本地目录中的原始文件扫描并转换为 Markdown 后存入 SQLite。

        递归扫描 ``source_dir`` 下的所有文件，跳过隐藏文件和不支持的格式。
        Markdown 文件直接存入，其他格式通过 markitdown 转换后存入。
        原始文件本身不存入 SQLite，仅保存转换后的 MD 文件。

        Args:
            project_id: 项目 ID
            source_dir: 源文件目录路径

        Returns:
            包含三个键的统计字典：
            - ``imported``: 成功导入的文件数
            - ``skipped``: 跳过的文件数（隐藏文件/不支持的格式/转换失败）
            - ``errors``: 出错的文件数

        Raises:
            FileNotFoundError: 目录不存在
            ValueError: 项目不存在
        """
        source_dir = Path(source_dir)
        if not source_dir.is_dir():
            raise FileNotFoundError(f"目录不存在: {source_dir}")

        proj = self.db.get_project(project_id)
        if not proj:
            raise ValueError(f"项目不存在: {project_id}")

        stats = {"imported": 0, "skipped": 0, "errors": 0}
        for filepath in source_dir.rglob("*"):
            if not filepath.is_file():
                continue
            if filepath.name.startswith("."):
                stats["skipped"] += 1
                continue

            ext = filepath.suffix.lower()
            if ext not in ALL_SUPPORTED_EXTENSIONS:
                stats["skipped"] += 1
                continue

            try:
                if ext == ".md":
                    md_content = filepath.read_text(encoding="utf-8", errors="replace")
                    rel_path = f"raw/{filepath.name}"
                    self.db.add_file(project_id, rel_path, md_content)
                    stats["imported"] += 1
                else:
                    content_bytes = filepath.read_bytes()
                    md_content = self.convert_to_md(content_bytes, filepath.name)
                    if md_content is None:
                        stats["skipped"] += 1
                        continue
                    stem = Path(filepath).stem
                    rel_path = f"raw/{stem}.md"
                    self.db.add_file(project_id, rel_path, md_content)
                    stats["imported"] += 1
            except Exception:
                stats["errors"] += 1

        return stats

    def add_raw_content(self, project_id: int, filename: str, content: str | bytes) -> int:
        """添加单个原始文件内容到 SQLite。

        Args:
            project_id: 项目 ID
            filename: 文件名（含扩展名）
            content: 文件内容（文本或字节）

        Returns:
            新创建的文件记录 ID
        """
        rel_path = f"raw/{filename}"
        return self.db.add_file(project_id, rel_path, content)

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
            return None

        try:
            from markitdown import MarkItDown
        except ImportError:
            return None

        md = MarkItDown(enable_plugins=False)
        tmp_path = None
        try:
            tmp_path = Path(tempfile.mktemp(suffix=ext))
            tmp_path.write_bytes(content_bytes)
            result = md.convert(str(tmp_path))
            return result.text_content
        except Exception:
            return None
        finally:
            if tmp_path and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
