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
from datetime import date
from pathlib import Path
from typing import Any, Iterator

from storage.db import WikiStorage
from wiki_engine.prompt import FORMAT_SELECT_PROMPT, INGEST_PROMPT
from wiki_engine.format_schema import (
    build_ingest_schema,
    format_catalog_for_prompt,
    resolve_source_format_ids,
)
from wiki_engine.graph import GraphWorkflow
from wiki_engine.helpers import (
    append_log,
    bootstrap_ingest_manifest,
    build_wiki_context,
    extract_title_from_content,
    is_raw_ingested,
    load_ingest_manifest,
    record_ingest,
    save_ingest_manifest,
    update_index,
    validate_ingest,
)
from tools.utils import call_llm, parse_json_from_response, sha256
from wiki_engine.kbs import FileImporter
from tools.logger import get_logger

logger = get_logger(__name__)

# 格式预判时送入 LLM 的正文截断长度
_FORMAT_SELECT_EXCERPT_CHARS = 3000


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

    def _select_formats_for_ingest(
        self, source_filename: str, source_content: str
    ) -> tuple[list[str], str]:
        """用 LLM 预判来源页格式，返回 (format_ids, reason)。

        失败时回退为通用来源页格式 ``["3"]``。
        """
        catalog = format_catalog_for_prompt()
        excerpt = source_content[:_FORMAT_SELECT_EXCERPT_CHARS]
        prompt = FORMAT_SELECT_PROMPT.format(
            format_catalog=catalog,
            source_filename=source_filename,
            source_excerpt=excerpt,
        )
        logger.info(
            "Format select start: file=%s, excerpt_len=%d",
            source_filename,
            len(excerpt),
        )
        try:
            raw = call_llm(
                prompt,
                max_tokens=512,
                validate_json=True,
            )
            data = parse_json_from_response(raw)
            selected = data.get("format_ids") or []
            reason = str(data.get("reason") or "")
            resolved = resolve_source_format_ids(selected)
            logger.info(
                "Format select ok: file=%s, selected=%s, resolved=%s, reason=%s",
                source_filename,
                selected,
                resolved,
                reason,
            )
            return resolved, reason
        except Exception as e:
            logger.warning(
                "Format select failed, fallback to [3]: file=%s, error=%s",
                source_filename,
                e,
            )
            return ["3"], f"fallback: {e}"

    def _select_pending_raw_files(
        self, kb_id: int, raw_files: list[dict]
    ) -> tuple[list[dict], int]:
        """按 ingest manifest（path + content hash）筛选待摄入 raw 文件。

        Returns:
            (pending_files, skipped_count)
        """
        manifest = load_ingest_manifest(self.db, kb_id)
        if not manifest.get("entries"):
            manifest = bootstrap_ingest_manifest(self.db, kb_id, manifest)

        pending: list[dict] = []
        skipped = 0
        for f in raw_files:
            rel_path = f["relative_path"]
            md_content = self.db.get_file_text_by_path(kb_id, rel_path)
            if md_content is None:
                content_bytes = self.db.get_file_content(f["id"])
                if content_bytes is None:
                    pending.append(f)
                    continue
                md_content = content_bytes.decode("utf-8", errors="replace")

            content_hash = sha256(md_content)
            if is_raw_ingested(manifest, rel_path, content_hash):
                skipped += 1
                logger.info("  [跳过] 已摄入且未变更: %s", rel_path)
                continue
            pending.append(f)

        return pending, skipped

    def build_knowledge_base(
        self,
        kb_id: int,
        auto_convert: bool = True,
        skip_graph: bool = False,
        graph_builder: GraphWorkflow = None,
    ) -> dict[str, Any]:
        """对知识库中的所有 raw 文件执行完整的知识库构建流程。"""
        result: dict[str, Any] | None = None
        for event in self.build_knowledge_base_stream(
            kb_id,
            auto_convert=auto_convert,
            skip_graph=skip_graph,
            graph_builder=graph_builder,
        ):
            if event.get("event") == "done":
                result = event.get("result")
            elif event.get("event") == "error":
                raise ValueError(event.get("message", "构建失败"))
        if result is None:
            raise RuntimeError("构建未返回结果")
        return result

    def build_knowledge_base_stream(
        self,
        kb_id: int,
        auto_convert: bool = True,
        skip_graph: bool = False,
        graph_builder: GraphWorkflow = None,
    ) -> Iterator[dict[str, Any]]:
        """流式构建知识库，逐步 yield 进度事件。

        仅摄入尚未记录在 ingest manifest 中（或内容 hash 已变）的 raw 文件。
        """
        del auto_convert  # 保留接口兼容
        kb = self.db.get_kb(kb_id)
        if not kb:
            yield {"event": "error", "message": f"知识库不存在: {kb_id}"}
            return

        raw_files = self.db.list_files_by_category(kb_id, "raw")
        if not raw_files:
            result = {
                "kb_id": kb_id,
                "kb_name": kb["name"],
                "status": "no_raw_files",
                "message": "没有找到原始文件，请先使用 import_raw_files() 导入",
                "ingested": 0,
                "skipped": 0,
                "pages_created": [],
                "errors": [],
            }
            yield {"event": "start", "kb_name": kb["name"], "total": 0, "task": "build"}
            yield {"event": "done", "result": result}
            return

        pending_files, skipped_count = self._select_pending_raw_files(kb_id, raw_files)

        logger.info("\n%s", "=" * 60)
        logger.info("  开始构建知识库: %s (id=%d)", kb["name"], kb_id)
        logger.info("  原始文件: %d, 待摄入: %d, 已跳过: %d", len(raw_files), len(pending_files), skipped_count)
        logger.info("%s\n", "=" * 60)

        if not pending_files:
            result = {
                "kb_id": kb_id,
                "kb_name": kb["name"],
                "status": "up_to_date",
                "message": "所有 raw 文件已摄入且未变更，无需重复构建",
                "ingested": 0,
                "skipped": skipped_count,
                "total_raw_files": len(raw_files),
                "pages_created": [],
                "errors": [],
            }
            yield {
                "event": "start",
                "kb_name": kb["name"],
                "total": 0,
                "skipped": skipped_count,
                "task": "build",
            }
            yield {"event": "done", "result": result}
            return

        ingested = 0
        all_created: list[str] = []
        errors: list[dict] = []

        batch_result: dict[str, Any] | None = None
        for event in self._run_ingest_batch_stream(kb_id, pending_files, task="build"):
            ev = event.get("event")
            if ev == "done":
                batch_result = event.get("result")
                continue
            yield event

        if batch_result:
            ingested = batch_result.get("ingested", 0)
            all_created = batch_result.get("pages_created", [])
            errors = batch_result.get("errors", [])

        if not skip_graph and ingested > 0 and graph_builder is not None:
            logger.info("\n\n--- 构建知识图谱 ---")
            yield {"event": "graph_start"}
            try:
                graph_result = graph_builder.build_graph(kb_id)
                logger.info(
                    "  图谱: %d 节点, %d 边",
                    graph_result.get("n_nodes", 0),
                    graph_result.get("n_edges", 0),
                )
                yield {
                    "event": "graph_done",
                    "n_nodes": graph_result.get("n_nodes", 0),
                    "n_edges": graph_result.get("n_edges", 0),
                }
            except Exception as e:
                logger.warning("  图谱构建失败: %s", e)
                yield {"event": "graph_error", "error": str(e)}

        logger.info("\n%s", "=" * 60)
        logger.info("  知识库构建完成!")
        logger.info("  摄入文件: %d/%d (跳过 %d)", ingested, len(pending_files), skipped_count)
        logger.info("  创建页面: %d", len(all_created))
        logger.info("  错误数: %d", len(errors))
        logger.info("%s\n", "=" * 60)

        result = {
            "kb_id": kb_id,
            "kb_name": kb["name"],
            "status": "completed",
            "ingested": ingested,
            "skipped": skipped_count,
            "total_raw_files": len(raw_files),
            "pages_created": all_created,
            "errors": errors,
        }
        yield {"event": "done", "result": result}

    def ingest_single(
        self,
        kb_id: int,
        source_filename: str,
        source_content: str,
        raw_relative_path: str | None = None,
    ) -> dict[str, Any]:
        """对单个原始文件执行 LLM 摄入。

        将源文档发送给 LLM，由 LLM 生成源页面、实体页面、概念页面，
        并更新索引和日志。最后执行摄入后验证。

        Args:
            kb_id: 知识库 ID
            source_filename: 源文件名
            source_content: 源文件 Markdown 内容
            raw_relative_path: raw 相对路径（写入 manifest），默认 ``raw/<filename>``

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
        rel_path = raw_relative_path or f"raw/{Path(source_filename).name}"

        wiki_context = build_wiki_context(self.db, kb_id)
        format_ids, format_reason = self._select_formats_for_ingest(
            source_filename, source_content
        )
        schema = build_ingest_schema(format_ids)
        logger.info(
            "Ingest schema assembled: file=%s, format_ids=%s, schema_len=%d, reason=%s",
            source_filename,
            format_ids,
            len(schema),
            format_reason,
        )
        kb = self.db.get_kb(kb_id)
        kb_name = kb["name"] if kb else "unknown"
        ingest_instruction = self.db.get_ingest_instruction(kb_id)
        if not ingest_instruction.strip():
            ingest_instruction = "（无特殊指令，按默认规范处理）"

        prompt = INGEST_PROMPT.format(
            kb_name=kb_name,
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
            debug_file = REPO_ROOT / "tmp" / f"ingest_debug_{kb_id}.txt"
            debug_file.parent.mkdir(exist_ok=True)
            debug_file.write_text(raw, encoding="utf-8")
            raise RuntimeError(f"API 响应解析失败: {e}") from e

        pages_created: list[str] = []

        slug = data.get("slug", "")
        source_path = f"wiki/sources/{slug}.md"
        self.db.add_file(kb_id, source_path, data.get("source_page", ""))
        pages_created.append(source_path)

        for page in data.get("entity_pages", []):
            wiki_path = f"wiki/{page['path']}"
            self.db.add_file(kb_id, wiki_path, page["content"])
            pages_created.append(wiki_path)
            entity_title = extract_title_from_content(page["content"])
            entity_entry = f"- [{entity_title}]({page['path']})"
            update_index(self.db, kb_id, entity_entry, section="Entities")

        for page in data.get("concept_pages", []):
            wiki_path = f"wiki/{page['path']}"
            self.db.add_file(kb_id, wiki_path, page["content"])
            pages_created.append(wiki_path)
            concept_title = extract_title_from_content(page["content"])
            concept_entry = f"- [{concept_title}]({page['path']})"
            update_index(self.db, kb_id, concept_entry, section="Concepts")

        # 更新概述
        if data.get("overview_update"):
            self.db.add_file(kb_id, "wiki/overview.md", data["overview_update"])

        update_index(self.db, kb_id, data.get("index_entry", ""), section="Sources")
        append_log(self.db, kb_id, data.get("log_entry", ""))

        contradictions = data.get("contradictions", [])
        if contradictions:
            logger.warning("  检测到 %d 处矛盾:", len(contradictions))
            for c in contradictions:
                logger.warning("     - %s", c)

        validation = validate_ingest(self.db, kb_id, pages_created)
        if validation["broken_links"]:
            logger.warning("  %d 个损坏链接", len(validation['broken_links']))
        if validation["unindexed"]:
            logger.warning("  %d 个未索引页面", len(validation['unindexed']))
        if not validation["broken_links"] and not validation["unindexed"]:
            logger.info("  验证通过")

        # 记录到 ingest manifest（path + hash，与 LLM slug 无关）
        manifest = load_ingest_manifest(self.db, kb_id)
        record_ingest(
            manifest,
            rel_path,
            source_hash,
            source_slug=slug,
            pages=pages_created,
        )
        save_ingest_manifest(self.db, kb_id, manifest)
        logger.info("  Manifest recorded: %s (hash=%s…)", rel_path, source_hash[:12])

        return {
            "title": data.get("title", ""),
            "slug": slug,
            "pages_created": pages_created,
            "contradictions": contradictions,
            "validation": validation,
        }

    def update_knowledge_base(
        self,
        kb_id: int,
        source_dir: str | Path | None = None,
    ) -> dict[str, Any]:
        """增量更新知识库。"""
        result: dict[str, Any] | None = None
        for event in self.update_knowledge_base_stream(kb_id, source_dir):
            if event.get("event") == "done":
                result = event.get("result")
            elif event.get("event") == "error":
                raise ValueError(event.get("message", "更新失败"))
        if result is None:
            raise RuntimeError("更新未返回结果")
        return result

    def update_knowledge_base_stream(
        self,
        kb_id: int,
        source_dir: str | Path | None = None,
    ) -> Iterator[dict[str, Any]]:
        """流式增量更新知识库。"""
        if source_dir:
            yield {"event": "import_start", "source_dir": str(source_dir)}
            for import_event in self.file_importer.import_raw_files_stream(kb_id, Path(source_dir)):
                yield import_event
                if import_event.get("event") == "error":
                    return

        raw_files = self.db.list_files_by_category(kb_id, "raw")
        new_files, skipped_count = self._select_pending_raw_files(kb_id, raw_files)

        if not new_files:
            result = {
                "kb_id": kb_id,
                "status": "up_to_date",
                "message": "知识库已是最新状态，没有新的原始文件需要处理",
                "ingested": 0,
                "skipped": skipped_count,
                "pages_created": [],
                "errors": [],
            }
            yield {
                "event": "start",
                "total": 0,
                "skipped": skipped_count,
                "task": "update",
            }
            yield {"event": "done", "result": result}
            return

        logger.info("\n  发现 %d 个新/变更文件待摄入 (跳过 %d)", len(new_files), skipped_count)
        yield from self._run_ingest_batch_stream(kb_id, new_files, task="update")

    def _run_ingest_batch(
        self, kb_id: int, raw_files: list[dict]
    ) -> dict[str, Any]:
        """对一批原始文件执行摄入。"""
        result: dict[str, Any] | None = None
        for event in self._run_ingest_batch_stream(kb_id, raw_files, task="ingest"):
            if event.get("event") == "done":
                result = event.get("result")
            elif event.get("event") == "error":
                raise ValueError(event.get("message", "摄入失败"))
        if result is None:
            raise RuntimeError("摄入未返回结果")
        return result

    def _run_ingest_batch_stream(
        self,
        kb_id: int,
        raw_files: list[dict],
        task: str = "ingest",
    ) -> Iterator[dict[str, Any]]:
        """流式对一批原始文件执行摄入。"""
        kb = self.db.get_kb(kb_id)
        if not kb:
            yield {"event": "error", "message": f"知识库不存在: {kb_id}"}
            return

        total = len(raw_files)
        yield {"event": "start", "kb_name": kb["name"], "total": total, "task": task}

        ingested = 0
        all_created: list[str] = []
        errors: list[dict] = []

        for index, f in enumerate(raw_files, start=1):
            rel_path = f["relative_path"]
            filename = Path(rel_path).name
            logger.info("\n--- 摄入: %s ---", filename)
            yield {"event": "file_start", "file": filename, "index": index, "total": total}
            try:
                content_bytes = self.db.get_file_content(f["id"])
                if content_bytes is None:
                    continue

                md_content: str | None = None
                ingest_path = rel_path
                if Path(filename).suffix.lower() != ".md":
                    logger.info("  转换 %s 为 Markdown...", filename)
                    md_content = self.file_importer.convert_to_md(content_bytes, filename)
                    if md_content is None:
                        err_msg = f"格式不支持: {Path(filename).suffix}"
                        errors.append({"file": filename, "error": err_msg})
                        yield {"event": "file_error", "file": filename, "error": err_msg}
                        continue
                    converted_path = f"raw/{Path(filename).stem}.md"
                    self.db.add_file(kb_id, converted_path, md_content)
                    ingest_path = converted_path
                else:
                    md_content = content_bytes.decode("utf-8", errors="replace")

                if not md_content or not md_content.strip():
                    continue

                result = self.ingest_single(
                    kb_id,
                    filename,
                    md_content,
                    raw_relative_path=ingest_path,
                )
                ingested += 1
                pages = result.get("pages_created", [])
                all_created.extend(pages)
                yield {
                    "event": "file_done",
                    "file": filename,
                    "pages_created": len(pages),
                }
            except Exception as e:
                errors.append({"file": filename, "error": str(e)})
                yield {"event": "file_error", "file": filename, "error": str(e)}

        result = {
            "kb_id": kb_id,
            "kb_name": kb["name"] if kb else "",
            "status": "completed",
            "ingested": ingested,
            "total_raw_files": total,
            "pages_created": all_created,
            "errors": errors,
        }
        yield {"event": "done", "result": result}
