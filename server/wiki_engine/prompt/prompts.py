# ── 知识库摄入 ─────────────────────────────────────────────────────

INGEST_PROMPT = """\
你正在维护一个企业知识库 Wiki。处理这份源文档并将其知识整合到 Wiki 中。

项目: {kb_name}

格式规范:
{schema}

当前 Wiki 状态:
{wiki_context}

待摄入的新源文档 (文件: {source_filename}):
=== 源文档开始 ===
{source_content}
=== 源文档结束 ===

当前日期: {today}

用户构建指令:
{ingest_instruction}

只返回一个有效的 JSON 对象(不要 markdown 代码围栏，不要 JSON 之外的任何文字):
{{
  "title": "源文档的人类可读标题，和页面中的title一致",
  "slug": "文档索引，可以和标题相同",
  "source_page": "wiki/sources/<slug>.md 的完整 markdown 内容 — 使用格式规范中的源页面格式。关键：将关键人物、产品、概念和项目积极转换为内联 [[WikiLink]]",
  "index_entry": "- [标题](sources/slug.md) — 一行摘要",
  "overview_update": "wiki/overview.md 的完整更新内容，或 null",
  "entity_pages": [
    {{"path": "entities/实体名.md", "content": "完整 markdown 内容"}}
  ],
  "concept_pages": [
    {{"path": "concepts/概念名.md", "content": "完整 markdown 内容"}}
  ],
  "contradictions": ["描述与现有 Wiki 内容的任何矛盾，或空列表"],
  "log_entry": "## [{today}] ingest | <标题>\\n\\n摄入源文档。关键主张: ..."
}}

重要提示:
- 来源页、实体页 和 概念页中的每一页都必须包含完整的 YAML frontmatter (title, slug, type, tags, sources 等字段)
- WikiLink链接必须使用目标页面的 **slug（不含 .md 扩展名）**，而不是标题，不一致时使用 slug
- 用户构建指令是用户自定义的，用于指导wiki生成的内容，务必重视参考。
"""

# ── 知识库查询 - 综合回答生成 ─────────────────────────────────────

QUERY_ANSWER_PROMPT = """\
你正在查询一个企业知识库 Wiki。使用以下 Wiki 页面综合一个详尽的回答。使用 [[slug]] 的WikiLink语法引用来源。

项目: {kb_name}

格式规范:
{schema}

Wiki 页面:
{pages_context}

问题: {question}

写一个结构良好的 Markdown 回答，包含标题、要点和 [[wikilink]] 引用。在末尾添加 ## 来源 部分，列出你使用的页面。
"""

# ── 知识库查询 - LLM 辅助页面检索 ────────────────────────────────

QUERY_RELEVANT_PAGES_PROMPT = """\
给定以下 wiki 索引：
{index_content}

哪些页面与回答以下问题最相关："{question}"

仅返回一个相对路径的 JSON 数组，例如 ["sources/foo.md", "concepts/Bar.md"]。最多 15 个页面。

"""

# ── 健康检查 - 语义质量审查 ──────────────────────────────────────

HEALTH_SEMANTIC_CHECK_PROMPT = """\
你正在检查一个企业知识库 Wiki。审查以下页面并识别:
1. 页面之间的矛盾（冲突的主张）
2. 过时内容（已被新源文档取代的摘要）
3. 数据缺口（Wiki 无法回答的重要问题 —— 建议具体来源）
4. 被提及但缺乏深度的概念

Wiki 页面（{sample_count} 个页面样本）:
{pages_context}

返回一个 Markdown 检查报告，包含以下部分:
## 矛盾
## 过时内容
## 数据缺口和建议来源
## 需要深化的概念

请具体指明涉及的页面和主张。
"""

# ── 知识图谱 - 隐式语义边推理 ────────────────────────────────────

GRAPH_INFER_EDGE_PROMPT = """\
分析此 wiki 页面，识别与其他页面的隐式语义关系。

源页面: {src}
内容:
{full_content}

所有可用页面:
{node_list}

此页面已提取的边:
{existing_edge_summary}

仅返回一个 JSON 对象，包含 "edges" 数组，列出尚未被显式 wikilink 捕获的新关系。响应必须严格为以下格式的合法 JSON：
{{
  "edges": [
    {{"to": "page-id", "relationship": "一句话描述", "confidence": 0.0-1.0, "type": "INFERRED 或 AMBIGUOUS"}}
  ]
}}

关键指令:
你必须仅返回以 {{ 开头、以 }} 结尾的原始 JSON 字符串。
不要输出项目符号。不要输出 Markdown 列表。
任何对话性前缀都会导致系统崩溃。

规则:
- 仅包含上述可用页面列表中的页面
- 置信度 >= 0.7 → INFERRED，< 0.7 → AMBIGUOUS
- 不要重复已提取列表中的边
- 如果没有发现新关系，返回 {{"edges": []}}
"""

# ── 图谱自愈 - 缺失实体页面生成 ──────────────────────────────────

HEAL_ENTITY_PROMPT = """\
你正在维护一个企业知识库 Wiki。
为实体 "{entity}" 创建一个定义页面。

该实体在当前 wiki 中的引用上下文：
{context}

格式：
---
title: "{entity}"
type: entity
tags: []
sources: {sources_list}
---

# {entity}

写一段全面的段落，定义 `{entity}` 在该 wiki 上下文中的含义、主要意义，
以及与之相关的任何行动或关联。
"""
