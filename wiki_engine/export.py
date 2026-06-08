"""导出与搜索功能模块

提供项目导出、Wiki 文本导出、项目统计和全文搜索功能。

类:
    ExportManager — 导出与搜索管理器
"""

from pathlib import Path
from typing import Any


class ExportManager:
    """导出与搜索管理器。

    封装项目的导出、统计和搜索功能。

    Args:
        db: WikiStorage 数据库实例
    """

    def __init__(self, db) -> None:
        self.db = db

    def export_project(self, project_id: int, output_dir: str | Path) -> int:
        """将项目导出到磁盘目录。

        将 SQLite 中存储的所有项目文件导出到指定目录，
        保持原有的相对路径结构。

        Args:
            project_id: 项目 ID
            output_dir: 输出目录路径

        Returns:
            导出的文件数量
        """
        return self.db.export_project(project_id, output_dir)

    def export_wiki_text(self, project_id: int) -> dict[str, str]:
        """以文本形式导出所有 Wiki 页面内容。

        仅导出 wiki/ 前缀下的文件，跳过原始文件和图谱数据。

        Args:
            project_id: 项目 ID

        Returns:
            以相对路径为键、内容文本为值的字典
        """
        wiki_files = self.db.list_files(project_id, "wiki/")
        result = {}
        for f in wiki_files:
            text = self.db.get_file_text_by_path(project_id, f["relative_path"])
            if text is not None:
                result[f["relative_path"]] = text
        return result

    def get_project_stats(self, project_id: int) -> dict[str, Any]:
        """获取项目统计信息。

        包括文件数量、各类别文件数、总大小等。

        Args:
            project_id: 项目 ID

        Returns:
            项目统计信息字典
        """
        return self.db.project_stats(project_id)

    def search(self, project_id: int, keyword: str) -> list[dict[str, Any]]:
        """全文搜索项目中的文件。

        在项目的所有文件中搜索包含指定关键词的文件。

        Args:
            project_id: 项目 ID
            keyword: 搜索关键词

        Returns:
            匹配的文件记录列表
        """
        return self.db.search(project_id, keyword)
