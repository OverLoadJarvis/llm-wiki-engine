"""LLM Wiki Engine — 企业知识库引擎

基于 SQLite 存储后端，提供构建知识库、更新知识库、检查知识库、查询知识库的对外服务能力。

模块结构:
    wiki_engine.constants   — 全局常量与配置
    wiki_engine.projects    — 项目管理与文件导入
    wiki_engine.ingest      — 知识库构建与摄入工作流
    wiki_engine.query       — 知识库查询工作流
    wiki_engine.health      — 健康检查与代码检查工作流
    wiki_engine.graph       — 知识图谱构建工作流
    wiki_engine.helpers     — 辅助方法（索引/日志/验证/上下文）
    wiki_engine.export      — 导出与搜索功能
    wiki_engine.cli         — 命令行入口

Usage:
    from wiki_engine import LLMWikiEngine

    engine = LLMWikiEngine("storage/wiki.db")
    pid = engine.create_project("my-project", "企业文档知识库")
    engine.import_raw_files(pid, "/path/to/docs")
    result = engine.build_knowledge_base(pid)
    answer = engine.query(pid, "这个项目的主要内容是什么?")
"""

from wiki_engine.engine import LLMWikiEngine

__all__ = ["LLMWikiEngine"]
