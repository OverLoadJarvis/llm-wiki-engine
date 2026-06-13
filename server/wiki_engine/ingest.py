"""知识库构建与摄入工作流模块

提供知识库的完整构建和增量更新功能，包括：
- 单文件 LLM 摄入
- 批量摄入
- 全量构建
- 增量更新

类:
    IngestWorkflow — 摄入工作流
"""

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from storage.db import WikiStorage
from wiki_engine.constants import SCHEMA_FILE
from wiki_engine.prompt import INGEST_PROMPT
from wiki_engine.graph import GraphWorkflow
from wiki_engine.helpers import (
    append_log,
    build_wiki_context,
    extract_title_from_content,
    get_ingested_slugs,
    update_index,
    validate_ingest,
)
from tools.utils import call_llm, parse_json_from_response, sha256
from wiki_engine.projects import FileImporter
from tools.logger import get_logger

logger = get_logger(__name__)


class IngestWorkflow:
    """知识库摄入工作流。

    负责将原始文件通过 LLM 处理，生成 wiki 页面（源页面、实体页面、概念页面），
    并更新索引和日志。

    Args:
        db: WikiStorage 数据库实例
        file_importer: FileImporter 实例，用于文件格式转换
    """

    def __init__(self, db: WikiStorage, file_importer: FileImporter) -> None:
        self.db = db
        self.file_importer = file_importer

    def build_knowledge_base(
        self,
        project_id: int,
        auto_convert: bool = True,
        skip_graph: bool = False,
        graph_builder: GraphWorkflow = None,
    ) -> dict[str, Any]:
        """对项目中的所有 raw 文件执行完整的知识库构建流程。

        流程：
            1. 获取项目中所有 raw 文件
            2. 逐个执行 LLM 摄入
            3. （可选）构建知识图谱

        Args:
            project_id: 项目 ID
            auto_convert: 是否自动转换非 MD 文件（当前未使用，保留接口兼容）
            skip_graph: 是否跳过图谱构建
            graph_builder: GraphWorkflow 实例，用于构建图谱；若为 ``None`` 且
                ``skip_graph=False``，将跳过图谱构建

        Returns:
            构建结果字典，包含：
            - ``project_id``: 项目 ID
            - ``project_name``: 项目名称
            - ``status``: 状态字符串（``"completed"`` / ``"no_raw_files"``）
            - ``ingested``: 成功摄入的文件数
            - ``total_raw_files``: 原始文件总数
            - ``pages_created``: 创建的 wiki 页面路径列表
            - ``errors``: 错误信息列表

        Raises:
            ValueError: 项目不存在
        """
        proj = self.db.get_project(project_id)
        if not proj:
            raise ValueError(f"项目不存在: {project_id}")

        raw_files = self.db.list_files_by_category(project_id, "raw")
        if not raw_files:
            return {
                "project_id": project_id,
                "project_name": proj["name"],
                "status": "no_raw_files",
                "message": "没有找到原始文件，请先使用 import_raw_files() 导入",
                "ingested": 0,
                "pages_created": [],
                "errors": [],
            }

        logger.info("\n%s", "=" * 60)
        logger.info("  开始构建知识库: %s (id=%d)", proj['name'], project_id)
        logger.info("  原始文件数: %d", len(raw_files))
        logger.info("%s\n", "=" * 60)

        ingested = 0
        all_created: list[str] = []
        errors: list[dict] = []

        for f in raw_files:
            rel_path = f["relative_path"]
            filename = Path(rel_path).name
            logger.info("\n--- 摄入: %s ---", filename)

            try:
                md_content = self.db.get_file_text_by_path(project_id, rel_path)
                if md_content is None:
                    errors.append({"file": filename, "error": "文件内容为空"})
                    continue

                if not md_content.strip():
                    errors.append({"file": filename, "error": "文件内容为空"})
                    continue

                result = self.ingest_single(project_id, filename, md_content)
                ingested += 1
                all_created.extend(result.get("pages_created", []))

            except Exception as e:
                errors.append({"file": filename, "error": str(e)})
                logger.error("  %s: %s", filename, e)

        if not skip_graph and ingested > 0 and graph_builder is not None:
            logger.info("\n\n--- 构建知识图谱 ---")
            try:
                graph_result = graph_builder.build_graph(project_id)
                logger.info("  图谱: %d 节点, %d 边", graph_result.get('n_nodes', 0), graph_result.get('n_edges', 0))
            except Exception as e:
                logger.warning("  图谱构建失败: %s", e)

        logger.info("\n%s", "=" * 60)
        logger.info("  知识库构建完成!")
        logger.info("  摄入文件: %d/%d", ingested, len(raw_files))
        logger.info("  创建页面: %d", len(all_created))
        logger.info("  错误数: %d", len(errors))
        logger.info("%s\n", "=" * 60)

        return {
            "project_id": project_id,
            "project_name": proj["name"],
            "status": "completed",
            "ingested": ingested,
            "total_raw_files": len(raw_files),
            "pages_created": all_created,
            "errors": errors,
        }

    def ingest_single(
        self, project_id: int, source_filename: str, source_content: str
    ) -> dict[str, Any]:
        """对单个原始文件执行 LLM 摄入。

        将源文档发送给 LLM，由 LLM 生成源页面、实体页面、概念页面，
        并更新索引和日志。最后执行摄入后验证。

        Args:
            project_id: 项目 ID
            source_filename: 源文件名
            source_content: 源文件 Markdown 内容

        Returns:
            摄入结果字典，包含：
            - ``title``: 源文档标题
            - ``slug``: 源文档 slug, 原文档的文件名，转换为 kebab-case 格式
            - ``pages_created``: 创建的页面路径列表
            - ``contradictions``: 检测到的矛盾列表
            - ``validation``: 验证结果字典

        Raises:
            RuntimeError: LLM 响应解析失败
        """
        today = date.today().isoformat()
        source_hash = sha256(source_content)

        wiki_context = build_wiki_context(self.db, project_id)
        schema = SCHEMA_FILE.read_text(encoding="utf-8")
        proj = self.db.get_project(project_id)
        proj_name = proj["name"] if proj else "unknown"
        ingest_instruction = self.db.get_ingest_instruction(project_id)
        if not ingest_instruction.strip():
            ingest_instruction = "（无特殊指令，按默认规范处理）"

        prompt = INGEST_PROMPT.format(
            proj_name=proj_name,
            schema=schema,
            wiki_context=wiki_context if wiki_context else "(Wiki 为空 — 这是第一份源文档)",
            source_filename=source_filename,
            source_content=source_content,
            today=today,
            ingest_instruction=ingest_instruction,
        )
        logger.info("  调用 LLM API...")
        raw = call_llm(prompt, max_tokens=16384, validate_json=True)
        try:
            data = parse_json_from_response(raw)
        except (ValueError, json.JSONDecodeError) as e:
            from wiki_engine.constants import REPO_ROOT
            debug_file = REPO_ROOT / "tmp" / f"ingest_debug_{project_id}.txt"
            debug_file.parent.mkdir(exist_ok=True)
            debug_file.write_text(raw, encoding="utf-8")
            raise RuntimeError(f"API 响应解析失败: {e}") from e

        pages_created: list[str] = []

        slug = data.get("slug", "")
        source_path = f"wiki/sources/{slug}.md"
        self.db.add_file(project_id, source_path, data.get("source_page", ""))
        pages_created.append(source_path)

        for page in data.get("entity_pages", []):
            wiki_path = f"wiki/{page['path']}"
            self.db.add_file(project_id, wiki_path, page["content"])
            pages_created.append(wiki_path)
            entity_title = extract_title_from_content(page["content"])
            entity_entry = f"- [{entity_title}]({page['path']})"
            update_index(self.db, project_id, entity_entry, section="Entities")

        for page in data.get("concept_pages", []):
            wiki_path = f"wiki/{page['path']}"
            self.db.add_file(project_id, wiki_path, page["content"])
            pages_created.append(wiki_path)
            concept_title = extract_title_from_content(page["content"])
            concept_entry = f"- [{concept_title}]({page['path']})"
            update_index(self.db, project_id, concept_entry, section="Concepts")

        # 更新概述
        if data.get("overview_update"):
            self.db.add_file(project_id, "wiki/overview.md", data["overview_update"])

        update_index(self.db, project_id, data.get("index_entry", ""), section="Sources")
        append_log(self.db, project_id, data.get("log_entry", ""))

        contradictions = data.get("contradictions", [])
        if contradictions:
            logger.warning("  检测到 %d 处矛盾:", len(contradictions))
            for c in contradictions:
                logger.warning("     - %s", c)

        validation = validate_ingest(self.db, project_id, pages_created)
        if validation["broken_links"]:
            logger.warning("  %d 个损坏链接", len(validation['broken_links']))
        if validation["unindexed"]:
            logger.warning("  %d 个未索引页面", len(validation['unindexed']))
        if not validation["broken_links"] and not validation["unindexed"]:
            logger.info("  验证通过")

        return {
            "title": data.get("title", ""),
            "slug": slug,
            "pages_created": pages_created,
            "contradictions": contradictions,
            "validation": validation,
        }

    def update_knowledge_base(
        self,
        project_id: int,
        source_dir: str | Path | None = None,
    ) -> dict[str, Any]:
        """增量更新知识库。

        流程：
            1. 若提供了 ``source_dir``，先导入新的原始文件
            2. 对比已摄入 slug，找出尚未处理的新文件
            3. 对新文件执行 LLM 摄入

        Args:
            project_id: 项目 ID
            source_dir: 可选的源文件目录路径，若提供则先导入文件

        Returns:
            与 :meth:`build_knowledge_base` 格式相同的字典；
            若没有新文件则 ``status`` 为 ``"up_to_date"``
        """
        if source_dir:
            import_stats = self.file_importer.import_raw_files(project_id, Path(source_dir))
            logger.info("  导入完成: %s", import_stats)

        ingested_slugs = get_ingested_slugs(self.db, project_id)
        raw_files = self.db.list_files_by_category(project_id, "raw")
        new_files = [
            f for f in raw_files
            if Path(f["relative_path"]).stem.lower() not in ingested_slugs
        ]

        if not new_files:
            return {
                "project_id": project_id,
                "status": "up_to_date",
                "message": "知识库已是最新状态，没有新的原始文件需要处理",
                "ingested": 0,
                "pages_created": [],
                "errors": [],
            }

        logger.info("\n  发现 %d 个新文件待摄入", len(new_files))
        return self._run_ingest_batch(project_id, new_files)

    def _run_ingest_batch(
        self, project_id: int, raw_files: list[dict]
    ) -> dict[str, Any]:
        """对一批原始文件执行摄入。

        逐个处理文件：非 MD 文件先转换为 Markdown，然后执行 LLM 摄入。

        Args:
            project_id: 项目 ID
            raw_files: 待处理的文件记录列表

        Returns:
            摄入结果字典
        """
        proj = self.db.get_project(project_id)
        ingested = 0
        all_created: list[str] = []
        errors: list[dict] = []

        for f in raw_files:
            filename = Path(f["relative_path"]).name
            logger.info("\n--- 摄入: %s ---", filename)
            try:
                content_bytes = self.db.get_file_content(f["id"])
                if content_bytes is None:
                    continue

                md_content: str | None = None
                if Path(filename).suffix.lower() != ".md":
                    logger.info("  转换 %s 为 Markdown...", filename)
                    md_content = self.file_importer.convert_to_md(content_bytes, filename)
                    if md_content is None:
                        errors.append({"file": filename, "error": f"格式不支持: {Path(filename).suffix}"})
                        continue
                    converted_path = f"raw/{Path(filename).stem}.md"
                    self.db.add_file(project_id, converted_path, md_content)
                else:
                    md_content = content_bytes.decode("utf-8", errors="replace")

                if not md_content or not md_content.strip():
                    continue

                result = self.ingest_single(project_id, filename, md_content)
                ingested += 1
                all_created.extend(result.get("pages_created", []))
            except Exception as e:
                errors.append({"file": filename, "error": str(e)})

        return {
            "project_id": project_id,
            "project_name": proj["name"] if proj else "",
            "status": "completed",
            "ingested": ingested,
            "total_raw_files": len(raw_files),
            "pages_created": all_created,
            "errors": errors,
        }
