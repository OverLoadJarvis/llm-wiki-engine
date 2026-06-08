"""知识库查询工作流模块

提供基于 LLM 的知识库查询功能，包括：
- 相关页面检索（关键词匹配 + LLM 辅助）
- 综合回答生成
- 查询结果归档为 synthesis 页面

类:
    QueryWorkflow — 查询工作流
"""

import json
import re
from datetime import date
from typing import Any

from storage.db import WikiStorage
from wiki_engine.constants import SCHEMA_FILE
from wiki_engine.helpers import append_log
from tools.utils import call_llm


class QueryWorkflow:
    """知识库查询工作流。

    根据用户问题从 Wiki 中检索相关页面，然后由 LLM 综合生成回答。
    支持将回答保存为 synthesis 页面。

    Args:
        db: WikiStorage 数据库实例
    """

    def __init__(self, db: WikiStorage) -> None:
        self.db = db

    def query(self, project_id: int, question: str, save: bool = False) -> str:
        """查询项目知识库。

        流程：
            1. 验证项目存在且知识库非空
            2. 从索引中检索与问题相关的页面
            3. 将相关页面内容发送给 LLM，综合生成回答
            4. （可选）将回答保存为 synthesis 页面

        Args:
            project_id: 项目 ID
            question: 查询问题
            save: 是否将结果保存为 synthesis 页面

        Returns:
            LLM 综合生成的回答（Markdown 格式）

        Raises:
            ValueError: 项目不存在
        """
        proj = self.db.get_project(project_id)
        if not proj:
            raise ValueError(f"项目不存在: {project_id}")

        wiki_files = self.db.list_files(project_id, "wiki/")
        if not wiki_files:
            return "知识库为空。请先使用 build_knowledge_base() 构建知识库。"

        today = date.today().isoformat()
        schema = SCHEMA_FILE.read_text(encoding="utf-8")

        relevant_pages = self.find_relevant_pages(project_id, question)

        pages_context = ""
        for p in relevant_pages:
            content = self.db.get_file_text_by_path(project_id, p["relative_path"])
            if content:
                pages_context += f"\n\n### {p['relative_path']}\n{content[:3000]}"

        if not pages_context:
            index_content = self.db.get_file_text_by_path(project_id, "wiki/index.md") or ""
            pages_context = f"\n\n### wiki/index.md\n{index_content[:3000]}"

        print(f"  从 {len(relevant_pages)} 个相关页面综合回答...")
        prompt = f"""你正在查询一个企业知识库 Wiki。使用以下 Wiki 页面综合一个详尽的回答。使用 [[PageName]] 语法引用来源。

项目: {proj['name']}

格式规范:
{schema}

Wiki 页面:
{pages_context}

问题: {question}

写一个结构良好的 Markdown 回答，包含标题、要点和 [[wikilink]] 引用。在末尾添加 ## 来源 部分，列出你使用的页面。
"""
        answer = call_llm(prompt, max_tokens=8192)

        if save:
            self._save_synthesis(project_id, question, answer, today)

        append_log(
            self.db,
            project_id,
            f"## [{today}] query | {question[:80]}\n\n从 {len(relevant_pages)} 个页面综合回答。",
        )

        return answer

    def find_relevant_pages(
        self, project_id: int, question: str
    ) -> list[dict[str, Any]]:
        """从项目 Wiki 页面中找到与问题相关的页面。

        采用两阶段检索策略：
            1. **关键词匹配**：从 index.md 中提取链接，用 bigram（中文）
               或 word（英文）匹配问题关键词
            2. **LLM 辅助**：若关键词匹配结果不足，调用 LLM 从索引中选择
               最相关的页面

        始终将 overview.md 包含在结果中。

        Args:
            project_id: 项目 ID
            question: 查询问题

        Returns:
            相关页面记录列表，最多 15 个
        """
        index_content = self.db.get_file_text_by_path(project_id, "wiki/index.md") or ""

        md_links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", index_content)
        question_lower = question.lower()
        relevant: list[dict] = []

        for title, href in md_links:
            title_lower = title.lower()
            has_cjk = any("\u4e00" <= ch <= "\u9fff" for ch in title)

            if has_cjk:
                matched = any(
                    title_lower[j : j + 2] in question_lower
                    for j in range(len(title_lower) - 1)
                    if any("\u4e00" <= c <= "\u9fff" for c in title_lower[j : j + 2])
                )
            else:
                matched = any(
                    word in question_lower
                    for word in title_lower.split()
                    if len(word) > 2
                )

            if matched:
                wiki_path = f"wiki/{href}"
                f = self.db.get_file_by_path(project_id, wiki_path)
                if f and f not in relevant:
                    relevant.append(f)

        overview = self.db.get_file_by_path(project_id, "wiki/overview.md")
        if overview and overview not in relevant:
            relevant.insert(0, overview)

        if len(relevant) <= 1:
            prompt = (
                f"给定以下 wiki 索引：\n\n{index_content}\n\n"
                f'哪些页面与回答以下问题最相关："{question}"\n\n'
                f'仅返回一个相对路径的 JSON 数组，例如 ["sources/foo.md", "concepts/Bar.md"]。最多 15 个页面。'
            )
            raw = call_llm(prompt, "LLM_MODEL_FAST", "claude-3-5-haiku-latest", max_tokens=5120)
            raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
            raw = re.sub(r"\s*```$", "", raw.strip())
            try:
                paths = json.loads(raw)
                for p in paths:
                    wiki_path = f"wiki/{p}"
                    f = self.db.get_file_by_path(project_id, wiki_path)
                    if f and f not in relevant:
                        relevant.append(f)
            except (json.JSONDecodeError, TypeError):
                pass
        # 仅返回前 15 个相关页面
        return relevant[:15]

    def _save_synthesis(
        self, project_id: int, question: str, answer: str, today: str
    ) -> None:
        """将查询回答保存为 synthesis 页面并更新索引。

        Args:
            project_id: 项目 ID
            question: 原始问题
            answer: LLM 生成的回答
            today: 日期字符串（YYYY-MM-DD）
        """
        slug = re.sub(r"[^\w\s-]", "", question[:40]).strip().lower()
        slug = re.sub(r"[-\s]+", "-", slug)
        synth_path = f"wiki/syntheses/{slug}.md"

        frontmatter = f"""---
title: "{question[:80]}"
type: synthesis
tags: []
sources: []
last_updated: {today}
---

"""
        self.db.add_file(project_id, synth_path, frontmatter + answer)

        index_content = self.db.get_file_text_by_path(project_id, "wiki/index.md") or ""
        entry = f"- [{question[:60]}](syntheses/{slug}.md) — synthesis"
        if "## 综合" in (index_content or ""):
            index_content = index_content.replace("## 综合\n", f"## 综合\n{entry}\n")
            self.db.add_file(project_id, "wiki/index.md", index_content)
        print(f"  已保存到: {synth_path}")
