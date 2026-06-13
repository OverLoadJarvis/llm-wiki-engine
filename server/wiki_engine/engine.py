"""LLM Wiki Engine — 主引擎模块

将各功能模块组装为统一的 LLMWikiEngine 类，提供完整的知识库管理能力。

模块组合:
    - ProjectManager  → 项目 CRUD
    - FileImporter    → 文件导入与转换
    - IngestWorkflow  → 知识库构建与摄入
    - QueryWorkflow   → 知识库查询
    - HealthWorkflow  → 健康检查与代码检查
    - GraphWorkflow   → 知识图谱构建
    - ExportManager   → 导出与搜索

Usage:
    from wiki_engine.engine import LLMWikiEngine

    engine = LLMWikiEngine("storage/wiki.db")
    pid = engine.create_project("my-project", "企业文档知识库")
    engine.import_raw_files(pid, "/path/to/docs")
    result = engine.build_knowledge_base(pid)
    answer = engine.query(pid, "这个项目的主要内容是什么?")
"""

from pathlib import Path
from typing import Any

from storage.db import WikiStorage
from wiki_engine.constants import REPO_ROOT
from wiki_engine.projects import ProjectManager, FileImporter
from wiki_engine.ingest import IngestWorkflow
from wiki_engine.query import QueryWorkflow
from wiki_engine.health import HealthWorkflow
from wiki_engine.graph import GraphWorkflow
from wiki_engine.export import ExportManager
from wiki_engine.heal import HealWorkflow
from tools.logger import get_logger

logger = get_logger(__name__)


def _ensure_engine_schema(db: WikiStorage) -> None:
    """确保数据库 schema 已初始化。

    读取 storage/schema.sql 并执行，创建所需的表结构。

    Args:
        db: WikiStorage 数据库实例
    """
    db.conn.executescript((REPO_ROOT / "storage" / "schema.sql").read_text(encoding="utf-8"))
    db.conn.commit()


class LLMWikiEngine:
    """LLM Wiki 企业知识库引擎。

    基于 SQLite 存储后端，提供构建知识库、更新知识库、检查知识库、
    查询知识库的对外服务能力。

    内部将功能委托给各专业模块：
        - :class:`ProjectManager` — 项目 CRUD
        - :class:`FileImporter` — 文件导入与格式转换
        - :class:`IngestWorkflow` — 知识库构建与摄入
        - :class:`QueryWorkflow` — 知识库查询
        - :class:`HealthWorkflow` — 健康检查与代码检查
        - :class:`GraphWorkflow` — 知识图谱构建
        - :class:`ExportManager` — 导出与搜索

    Args:
        db_path: SQLite 数据库文件路径，默认 ``"storage/wiki.db"``

    Example::

        engine = LLMWikiEngine("storage/wiki.db")
        pid = engine.create_project("my-project", "描述")
        engine.import_raw_files(pid, "/path/to/docs")
        result = engine.build_knowledge_base(pid)
    """

    def __init__(self, db_path: str | Path = "storage/wiki.db") -> None:
        self.db = WikiStorage(db_path)
        self.db_path = Path(db_path)
        _ensure_engine_schema(self.db)

        # 初始化各功能模块
        self._projects = ProjectManager(self.db)
        self._importer = FileImporter(self.db)
        self._ingest = IngestWorkflow(self.db, self._importer)
        self._query = QueryWorkflow(self.db)
        self._health = HealthWorkflow(self.db)
        self._graph = GraphWorkflow(self.db)
        self._export = ExportManager(self.db)
        self._heal = HealWorkflow(self.db)

    def close(self) -> None:
        """关闭数据库连接。"""
        self.db.close()

    # ── 项目管理 ────────────────────────────────────────────────────

    def create_project(self, name: str, description: str = "") -> int:
        """创建新项目。

        Args:
            name: 项目名称
            description: 项目描述

        Returns:
            新创建项目的 ID
        """
        return self._projects.create_project(name, description)

    def get_project(self, project_id: int) -> dict[str, Any] | None:
        """获取项目信息。

        Args:
            project_id: 项目 ID

        Returns:
            项目信息字典，若不存在返回 ``None``
        """
        return self._projects.get_project(project_id)

    def list_projects(self) -> list[dict[str, Any]]:
        """列出所有项目。

        Returns:
            项目信息字典列表
        """
        return self._projects.list_projects()

    def delete_project(self, project_id: int) -> bool:
        """删除项目。

        Args:
            project_id: 项目 ID

        Returns:
            是否删除成功
        """
        return self._projects.delete_project(project_id)

    # ── 原始文件导入 ────────────────────────────────────────────────

    def import_raw_files(self, project_id: int, source_dir: str | Path) -> dict[str, int]:
        """将本地目录中的原始文件扫描并转换为 Markdown 后存入 SQLite。

        递归扫描 ``source_dir`` 下的所有文件，跳过隐藏文件和不支持的格式。
        Markdown 文件直接存入，其他格式通过 markitdown 转换后存入。

        Args:
            project_id: 项目 ID
            source_dir: 源文件目录路径

        Returns:
            统计字典：``{"imported": count, "skipped": count, "errors": count}``

        Raises:
            FileNotFoundError: 目录不存在
            ValueError: 项目不存在
        """
        return self._importer.import_raw_files(project_id, source_dir)

    def add_raw_content(self, project_id: int, filename: str, content: str | bytes) -> int:
        """添加单个原始文件内容到 SQLite。

        Args:
            project_id: 项目 ID
            filename: 文件名（含扩展名）
            content: 文件内容

        Returns:
            新创建的文件记录 ID
        """
        return self._importer.add_raw_content(project_id, filename, content)

    # ── 核心工作流 1: 构建知识库 ────────────────────────────────────

    def build_knowledge_base(
        self,
        project_id: int,
        auto_convert: bool = True,
        skip_graph: bool = False,
    ) -> dict[str, Any]:
        """对项目中的所有 raw 文件执行完整的知识库构建流程。

        流程：
            1. 获取项目中所有 raw 文件
            2. 逐个执行 LLM 摄入
            3. （可选）构建知识图谱

        Args:
            project_id: 项目 ID
            auto_convert: 是否自动转换非 MD 文件
            skip_graph: 是否跳过图谱构建

        Returns:
            构建结果字典，包含 ``ingested``、``pages_created``、``errors`` 等键

        Raises:
            ValueError: 项目不存在
        """
        return self._ingest.build_knowledge_base(
            project_id,
            auto_convert=auto_convert,
            skip_graph=skip_graph,
            graph_builder=self._graph if not skip_graph else None,
        )

    # ── 核心工作流 2: 更新知识库 ────────────────────────────────────

    def update_knowledge_base(
        self,
        project_id: int,
        source_dir: str | Path | None = None,
    ) -> dict[str, Any]:
        """增量更新知识库。

        若提供了 ``source_dir``，先导入新的原始文件，然后只摄入尚未处理的新文件。

        Args:
            project_id: 项目 ID
            source_dir: 可选的源文件目录路径

        Returns:
            与 :meth:`build_knowledge_base` 格式相同的字典
        """
        return self._ingest.update_knowledge_base(project_id, source_dir)

    # ── 核心工作流 3: 查询知识库 ────────────────────────────────────

    def query(self, project_id: int, question: str, save: bool = False) -> str:
        """查询项目知识库。

        从 Wiki 中检索相关页面，由 LLM 综合生成回答。

        Args:
            project_id: 项目 ID
            question: 查询问题
            save: 是否将结果保存为 synthesis 页面

        Returns:
            LLM 综合生成的回答（Markdown 格式）

        Raises:
            ValueError: 项目不存在
        """
        return self._query.query(project_id, question, save=save)

    # ── 核心工作流 4: 检查知识库 ────────────────────────────────────

    def health_check(self, project_id: int) -> dict[str, Any]:
        """结构健康检查（无 LLM 调用，纯确定性检查）。

        检查空/存根文件、索引同步、日志覆盖等结构问题。

        Args:
            project_id: 项目 ID

        Returns:
            健康检查结果字典

        Raises:
            ValueError: 项目不存在
        """
        return self._health.health_check(project_id)

    def lint(self, project_id: int, save: bool = False) -> str:
        """内容质量检查（包含 LLM 语义分析）。

        检查孤立页面、损坏链接、缺失实体、稀疏页面和语义问题。

        Args:
            project_id: 项目 ID
            save: 是否将报告保存到 wiki/lint-report.md

        Returns:
            Markdown 格式的检查报告

        Raises:
            ValueError: 项目不存在
        """
        return self._health.lint(project_id, save=save)

    # ── 核心工作流 5: 构建知识图谱 ──────────────────────────────────

    def build_graph(
        self,
        project_id: int,
        infer: bool = True,
        clean: bool = False,
        resume: bool = True,
        report: bool = True,
    ) -> dict[str, Any]:
        """为项目构建知识图谱。

        从 wikilink 提取显式边，可选地通过 LLM 推理隐式边，
        执行社区检测，生成可视化 HTML 和可选的健康报告。

        Args:
            project_id: 项目 ID
            infer: 是否进行语义推理
            clean: 是否清除推理缓存
            resume: 是否从上次中断处继续
            report: 是否生成图谱健康报告

        Returns:
            构建结果字典，包含 ``n_nodes``、``n_edges`` 等键

        Raises:
            ValueError: 项目不存在
        """
        return self._graph.build_graph(
            project_id, infer=infer, clean=clean, resume=resume, report=report
        )

    # ── 导出 ────────────────────────────────────────────────────────

    def export_project(self, project_id: int, output_dir: str | Path) -> int:
        """将项目导出到磁盘目录。

        Args:
            project_id: 项目 ID
            output_dir: 输出目录路径

        Returns:
            导出的文件数量
        """
        return self._export.export_project(project_id, output_dir)

    def export_wiki_text(self, project_id: int) -> dict[str, str]:
        """以文本形式导出所有 Wiki 页面内容。

        Args:
            project_id: 项目 ID

        Returns:
            {relative_path: content_text, ...}
        """
        return self._export.export_wiki_text(project_id)

    def get_project_stats(self, project_id: int) -> dict[str, Any]:
        """获取项目统计信息。

        Args:
            project_id: 项目 ID

        Returns:
            项目统计信息字典
        """
        return self._export.get_project_stats(project_id)

    def search(self, project_id: int, keyword: str) -> list[dict[str, Any]]:
        """全文搜索项目中的文件。

        Args:
            project_id: 项目 ID
            keyword: 搜索关键词

        Returns:
            匹配的文件记录列表
        """
        return self._export.search(project_id, keyword)

    # ── 核心工作流 6: 图谱自愈 ──────────────────────────────────

    def heal_graph(self, project_id: int, min_refs: int = 3, max_sources: int = 15,
                   model: str = "claude-3-5-haiku-latest") -> dict[str, Any]:
        """自动补全缺失的实体页面。

        扫描 wiki 中缺失的实体页面（被引用但无独立页面），
        使用 LLM 生成实体定义页面以修复断裂的实体链接。

        Args:
            project_id: 项目 ID
            min_refs: 最小引用次数阈值
            max_sources: 每个实体最多检索的引用来源数
            model: 使用的 LLM 模型

        Returns:
            自愈结果字典

        Raises:
            ValueError: 项目不存在
        """
        return self._heal.heal_missing_entities(
            project_id, min_refs=min_refs, max_sources=max_sources, model=model
        )

    # ── 简便方法：一键构建 ──────────────────────────────────────────

    def quick_build(self, project_name: str, source_dir: str | Path) -> dict[str, Any]:
        """一键构建知识库（创建项目 → 导入文件 → 构建知识库）。

        便捷方法，自动完成项目创建、文件导入和知识库构建三个步骤。

        Args:
            project_name: 项目名称
            source_dir: 源文件目录

        Returns:
            构建结果字典
        """
        project_id = self.create_project(project_name, f"从 {source_dir} 导入")
        logger.info("创建项目: %s (id=%d)", project_name, project_id)

        self.import_raw_files(project_id, source_dir)
        return self.build_knowledge_base(project_id)
