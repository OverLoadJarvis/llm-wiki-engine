"""导出与搜索功能模块

提供知识库导出、Wiki 文本导出、知识库统计和全文搜索功能。

类:
    ExportManager — 导出与搜索管理器
"""

from pathlib import Path
from typing import Any


class ExportManager:
    """导出与搜索管理器。

    封装知识库的导出、统计和搜索功能。

    Args:
        db: WikiStorage 数据库实例
    """

    def __init__(self, db) -> None:
        self.db = db

    def export_kb(self, kb_id: int, output_dir: str | Path) -> int:
        """将知识库导出到磁盘目录。

        将 SQLite 中存储的所有知识库文件导出到指定目录，
        保持原有的相对路径结构。

        Args:
            kb_id: 知识库 ID
            output_dir: 输出目录路径

        Returns:
            导出的文件数量
        """
        return self.db.export_kb(kb_id, output_dir)

    def export_wiki_text(self, kb_id: int) -> dict[str, str]:
        """以文本形式导出所有 Wiki 页面内容。

        仅导出 wiki/ 前缀下的文件，跳过原始文件和图谱数据。

        Args:
            kb_id: 知识库 ID

        Returns:
            以相对路径为键、内容文本为值的字典
        """
        wiki_files = self.db.list_files(kb_id, "wiki/")
        result = {}
        for f in wiki_files:
            text = self.db.get_file_text_by_path(kb_id, f["relative_path"])
            if text is not None:
                result[f["relative_path"]] = text
        return result

    def get_kb_stats(self, kb_id: int) -> dict[str, Any]:
        """获取知识库统计信息。

        包括文件数量、各类别文件数、总大小等。

        Args:
            kb_id: 知识库 ID

        Returns:
            知识库统计信息字典
        """
        return self.db.kb_stats(kb_id)

    def search(self, kb_id: int, keyword: str) -> list[dict[str, Any]]:
        """全文搜索知识库中的文件。

        在知识库的所有文件中搜索包含指定关键词的文件。

        Args:
            kb_id: 知识库 ID
            keyword: 搜索关键词

        Returns:
            匹配的文件记录列表
        """
        return self.db.search(kb_id, keyword)
