"""图谱自愈工作流模块

提供自动补全缺失实体页面的功能，包括：
- 查找缺失实体（被引用但无独立页面）
- 检索引用来源
- LLM 生成实体定义页面

类:
    HealWorkflow — 图谱自愈工作流
"""

from datetime import date
from pathlib import Path
from typing import Any

from storage.db import WikiStorage
from wiki_engine.helpers import append_log
from tools.utils import call_llm, extract_wikilinks
from wiki_engine.prompt import HEAL_ENTITY_PROMPT
from tools.logger import get_logger

logger = get_logger(__name__)


class HealWorkflow:
    """图谱自愈工作流。

    自动检索 wiki 中缺失的实体页面，并使用 LLM 生成完整的实体定义页面，
    从而修复断裂的实体链接。

    Args:
        db: WikiStorage 数据库实例
    """

    def __init__(self, db: WikiStorage) -> None:
        self.db = db

    def heal_missing_entities(
        self,
        project_id: int,
        min_refs: int = 3,
        max_sources: int = 15,
        model: str = "claude-3-5-haiku-latest",
    ) -> dict[str, Any]:
        """自动补全缺失的实体页面。

        流程：
            1. 扫描所有 wiki 页面，找出被引用但没有独立页面的实体
            2. 对每个缺失实体，查找最多 max_sources 个引用来源页面
            3. 调用 LLM 基于引用上下文生成实体定义页面
            4. 保存实体页面到 wiki/entities/ 目录

        Args:
            project_id: 项目 ID
            min_refs: 最小引用次数阈值，低于此值的实体不处理
            max_sources: 每个实体最多检索的引用来源数
            model: 使用的 LLM 模型

        Returns:
            自愈结果字典，包含：
            - ``project_id``: 项目 ID
            - ``status``: 状态字符串
            - ``healed``: 成功补全的实体数
            - ``total_missing``: 缺失实体总数
            - ``entities_created``: 创建的实体页面路径列表
            - ``errors``: 错误信息列表

        Raises:
            ValueError: 项目不存在
        """
        proj = self.db.get_project(project_id)
        if not proj:
            raise ValueError(f"项目不存在: {project_id}")

        wiki_files = self.db.list_files(project_id, "wiki/")
        pages = [
            f for f in wiki_files
            if Path(f["relative_path"]).name
            not in ("index.md", "log.md", "lint-report.md")
        ]

        missing_entities = self._find_missing_entities(project_id, pages, min_refs)

        if not missing_entities:
            return {
                "project_id": project_id,
                "project_name": proj["name"],
                "status": "fully_connected",
                "message": "图谱已完全连接，没有缺失的实体页面",
                "healed": 0,
                "total_missing": 0,
                "entities_created": [],
                "errors": [],
            }

        logger.info("\n%s", "=" * 60)
        logger.info("  开始图谱自愈: %s (id=%d)", proj['name'], project_id)
        logger.info("  缺失实体数: %d", len(missing_entities))
        logger.info("%s\n", "=" * 60)

        healed = 0
        entities_created: list[str] = []
        errors: list[dict] = []

        for entity in missing_entities:
            logger.info("--- 自愈实体: %s ---", entity)
            try:
                sources = self._search_sources(entity, pages, max_sources)
                content = self._generate_entity_page(project_id, entity, sources, model)

                entity_path = f"wiki/entities/{entity}.md"
                self.db.add_file(project_id, entity_path, content)
                entities_created.append(entity_path)
                healed += 1

                rel_path = entity_path.replace("wiki/", "")
                entity_entry = f"- [{entity}]({rel_path})"
                self._update_index(project_id, entity_entry)

                logger.info("  -> 已保存: %s", entity_path)

            except Exception as e:
                errors.append({"entity": entity, "error": str(e)})
                logger.error("  %s: %s", entity, e)

        today = date.today().isoformat()
        append_log(
            self.db,
            project_id,
            f"## [{today}] heal | 图谱自愈\n\n补全了 {healed} 个缺失实体页面。",
        )

        logger.info("\n%s", "=" * 60)
        logger.info("  自愈完成!")
        logger.info("  补全实体: %d/%d", healed, len(missing_entities))
        logger.info("  错误数: %d", len(errors))
        logger.info("%s\n", "=" * 60)

        return {
            "project_id": project_id,
            "project_name": proj["name"],
            "status": "completed",
            "healed": healed,
            "total_missing": len(missing_entities),
            "entities_created": entities_created,
            "errors": errors,
        }

    def _find_missing_entities(
        self, project_id: int, pages: list[dict], min_refs: int = 3
    ) -> list[str]:
        """查找缺失实体页面（被 min_refs 次以上引用但没有独立页面的实体）。

        Args:
            project_id: 项目 ID
            pages: 页面记录列表
            min_refs: 最小引用次数阈值

        Returns:
            缺失实体名称列表
        """
        existing_stems = {Path(p["relative_path"]).stem.lower() for p in pages}
        mention_counts: dict[str, int] = {}

        for p in pages:
            content = self.db.get_file_text_by_path(project_id, p["relative_path"]) or ""
            links = extract_wikilinks(content)
            for link in links:
                link_stem = link.lower()
                if "/" in link:
                    link_stem = Path(link).stem.lower()
                if link_stem not in existing_stems:
                    mention_counts[link] = mention_counts.get(link, 0) + 1

        return [name for name, count in mention_counts.items() if count >= min_refs]

    def _search_sources(
        self, entity: str, pages: list[dict], max_sources: int = 15
    ) -> list[dict]:
        """查找引用了该实体的页面作为来源。

        Args:
            entity: 实体名称
            pages: 页面记录列表
            max_sources: 最大来源数

        Returns:
            来源页面列表，每个包含 path 和 content 字段
        """
        sources = []
        for p in pages:
            rel_path = p["relative_path"]
            # 跳过 entities 和 concepts 目录，只从 sources 和其他页面找引用
            if "entities" in rel_path or "concepts" in rel_path:
                continue
            content = self.db.get_file_text_by_path(self.db_path, rel_path) or ""
            if entity.lower() in content.lower():
                sources.append({"path": rel_path, "content": content})
                if len(sources) >= max_sources:
                    break
        return sources

    def _generate_entity_page(
        self, project_id: int, entity: str, sources: list[dict], model: str
    ) -> str:
        """调用 LLM 生成实体定义页面。

        Args:
            project_id: 项目 ID
            entity: 实体名称
            sources: 引用来源列表
            model: 使用的 LLM 模型

        Returns:
            生成的实体页面 Markdown 内容
        """
        context = ""
        for s in sources:
            truncated = s["content"][:800]
            context += f"\n\n### {Path(s['path']).name}\n{truncated}"

        sources_list = str([Path(s["path"]).name for s in sources])
        prompt = HEAL_ENTITY_PROMPT.format(
            entity=entity,
            context=context,
            sources_list=sources_list,
        )
        result = call_llm(prompt, default_model=model, max_tokens=8192)
        return result

    def _update_index(self, project_id: int, entry: str) -> None:
        """更新索引，添加实体条目。

        Args:
            project_id: 项目 ID
            entry: 索引条目，格式如 "- [实体名](entities/实体名.md)"
        """
        index_content = self.db.get_file_text_by_path(project_id, "wiki/index.md") or ""

        if "## Entities" not in index_content:
            index_content += "\n\n## Entities\n"

        lines = index_content.splitlines()
        new_lines = []
        inserted = False

        for line in lines:
            new_lines.append(line)
            if line.strip().startswith("## Entities") and not inserted:
                inserted = True

        if not inserted:
            new_lines.append("## Entities")

        new_lines.append(entry)

        self.db.add_file(project_id, "wiki/index.md", "\n".join(new_lines))
