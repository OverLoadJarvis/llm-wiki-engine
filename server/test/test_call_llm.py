"""
测试 tools/utils.py 中的 call_llm 函数 - 真实 API 调用测试
"""
import os
import sys
from pathlib import Path

# 确保能导入 tools/utils.py
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tools.utils import call_llm
from tools.logger import get_logger, setup_logging

logger = get_logger(__name__)

# 构造提示词
prompt = """你正在维护一个企业知识库 Wiki。处理这份源文档并将其摄入到 Wiki 中。

# Wiki 格式规范

本文档从 [AGENTS.md](AGENTS.md) 提取，集中描述 wiki 中所有文件/页面的格式规范。

## 1. Page Format（页面格式）

**适用文件：** `wiki/` 下所有页面文件（包括 `wiki/sources/`、`wiki/entities/`、`wiki/concepts/` 等）。

**用途：** 这是所有 wiki 页面的通用元数据头。每个页面文件开头都必须包含此 frontmatter，用于描述页面类型和关联信息。

```yaml
---
title: "Page Title"
type: source | entity | concept | synthesis
tags: []
sources: []       # 为此页面提供信息的源页面 slug 列表
last_updated: YYYY-MM-DD
---
```

`type` 字段取值说明：
- `source` — 来源文档摘要页（`wiki/sources/`）
- `entity` — 实体页（人物、公司、项目、产品）
- `concept` — 概念页（思想、框架、方法、理论）
- `synthesis` — 综合/分析页（保存的查询回答）

正文中使用 `[[PageName]]` wikilink 语法链接到其他 wiki 页面。

## 2. Naming Conventions（命名规范）

**适用场景：** 创建任何新的 wiki 页面文件时的文件命名规则。

| 页面类型 | 命名规则 | 示例 |
|---|---|---|
| Source slugs | `kebab-case`，与源文件名匹配 | `my-paper.md` |
| Entity pages | `TitleCase.md` | `OpenAI.md`、`SamAltman.md` |
| Concept pages | `TitleCase.md` | `ReinforcementLearning.md`、`RAG.md` |

---

## 3. Source Page Format（来源页格式）

**适用文件：** `wiki/sources/<slug>.md`

每份原始文档（`raw/` 目录下的文件），都应在 `wiki/sources/` 下生成一篇对应摘要页。此模板用于规范摘要页的结构。

```markdown
---
title: "Source Title"
type: source
tags: []
date: YYYY-MM-DD
source_file: raw/...
---

## Summary
2–4 sentence summary.

## Key Claims
- Claim 1
- Claim 2

## Key Quotes
> "Quote here" — context

## Connections
- [[EntityName]] — how they relate
- [[ConceptName]] — how it connects

## Contradictions
- Contradicts [[OtherPage]] on: ...
```

---

## 4. Domain-Specific Templates（特定领域模板）

当摄入的源文档属于特定领域时，使用专用模板而不是通用模板。

### 4a. Diary / Journal Template（日记模板）

**适用文件：** `wiki/sources/<slug>.md`（当源文档是日记时）

```markdown
---
title: "YYYY-MM-DD Diary"
type: source
tags: [diary]
date: YYYY-MM-DD
---
## Event Summary
...
## Key Decisions
...
## Energy & Mood
...
## Connections
...
## Shifts & Contradictions
...
```

### 4b. Meeting Notes Template（会议记录模板）

**适用文件：** `wiki/sources/<slug>.md`（当源文档是会议记录时）

```markdown
---
title: "Meeting Title"
type: source
tags: [meeting]
date: YYYY-MM-DD
---
## Objectives
...
## Key Discussions
...
## Decisions Made
...
## Action Items
...
```

---

## 5. Index Format（索引格式）

**适用文件：** `wiki/index.md`

**用途：** 这是 wiki 的目录/索引页，记录所有 wiki 页面的清单。每次完成 ingest 操作后都需要更新此文件。

```markdown
# Wiki Index

## Overview
- [Overview](overview.md) — living synthesis

## Sources
- [Source Title](sources/slug.md) — one-line summary

## Entities
- [Entity Name](entities/EntityName.md) — one-line description

## Concepts
- [Concept Name](concepts/ConceptName.md) — one-line description

## Syntheses
- [Synthesis Title](syntheses/slug.md) — the question it answers
```

---

## 6. Log Format（日志格式）

**适用文件：** `wiki/log.md`

**用途：** 记录 wiki 的每次操作（ingest、query、health、lint、graph、report 等）。每次操作完成后在文件末尾追加一条新记录。

格式：`## [YYYY-MM-DD] <operation> | <title>`

其中 `<operation>` 可以是：`ingest`、`query`、`health`、`lint`、`graph`、`report`

当前 Wiki 状态：
- 现有源文档 (文件: 02-作战篇.md):
=== 源文档开始 ===
孙子兵法·作战篇

【原文】
孙子曰：凡用兵之法，驰车千驷，革车千乘，带甲十万，千里馈粮，则内外之费，宾客之用，胶漆之材，车甲之奉，日费千金，然后十万之师举矣。其用战也胜，久则钝兵挫锐，攻城则力屈，久暴师则国用不足。夫钝兵挫锐，屈力殚货，则诸侯乘其弊而起，虽有智者，不能善其后矣。故兵闻拙速，未睹巧之久也。夫兵久而国利者，未之有也。故不尽知用兵之害者，则不能尽知用兵之利也。

【译文】
孙子说：根据一般作战常规，出动战车千乘，运输车千辆，统兵十万，沿途千里转运粮草，内外的日常开支，使者往来的费用，修缮武器用的胶漆、战车所需的补给，车甲的供应，每天要耗费千金，然后十万大军才能出动。用兵打仗就要做到胜任裕如，举兵必克，否则，长久僵持，兵锋折损、锐气被挫，攻城就会力竭，长期在外作战必然会使国家财力不足。兵锋折损，锐气受挫、兵力耗尽、财政枯竭，那么，其他诸侯国就会趁这个困顿局面举兵进攻，即使睿智高明的人也难以收拾好这个局面。所以，只听说过虽拙犹速的用兵之道，没见过求巧而久耗的战争。战争时间长而对国家有利这种事，从来就没有过。因此，不能全面了解战争危害的人，就不能全面认识战争的益处。

【原文】
善用兵者，役不再籍，粮不三载；取用于国，因粮于敌，故军食可足也。

【译文】
善于用兵的人，兵员不再次征集，粮秣不多次运送；武器装备从国内解决，粮草补给在敌国就地解决，那么，军粮就可满足了。

【原文】
国之贫于师者远输，远输则百姓贫。近于师者贵卖，贵卖则百姓财竭，财竭则急于丘役。力屈、财殚，中原内虚于家。百姓之费，十去其七；公家之费，破车罢马，甲胄矢弩，戟楯蔽橹，丘牛大车，十去其六。

【译文】
国家因用兵而导致贫困的，在于远道运输，远道运输就会使百姓贫困。军队经过的地方物价高涨，物价上涨就会使百姓财物枯竭，财物枯竭就汲汲于应付赋役。民力耗尽，财力枯竭，中原地区家家空虚。百姓的资财，耗去了十分之七；国家的资财，战车破损了，战马疲病了，盔甲、矢弩、矛盾、牛、车之类，耗去了十分之六。

【原文】
故智将务食于敌，食敌一钟，当吾二十钟；忌杆一石，当吾二十石。

【译文】
因而，高明的将领务求从敌方夺取粮草。就地从敌方夺取粮食一钟，相当于自己从本国运出二十钟；就地夺取敌人饲草一石，相当于自己从本国运出二十石。

【原文】
故杀敌者，怒也；取敌之利者，货也。故车战，得车十乘已上，赏其先得者，而更其旌旗，车杂而乘之，卒善而养之，是谓胜敌而益强。

【译文】
所以，要使士卒奋勇杀敌，是使之威怒；鼓励将士夺取敌人资财，要用财物奖励。因此在车战中，凡缴获战车十辆以上的，奖赏那先夺得战车的人，并且换上我方的旗帜，混合编入自己的车阵之中，对于俘虏，则予优待、抚慰，任用他们作战，这就是所谓战胜敌人而使自己日益强大。

【原文】
故兵贵胜，不贵久。故知兵之将，生民之司命，国家安危之主也。

【译文】
所以，用兵作战以胜任裕如，举兵必克为贵，不主张力不从心，僵持消耗。深知用兵之法的将帅，是民众命运的掌握者，是国家安危的主宰者。
=== 源文档结束 ===

当前日期: 2026-06-03

只返回一个有效的 JSON 对象(不要 markdown 代码围栏，不要额外文本):
{
  "title": "人类可读标题",
  "slug": "kebab-case-slug",
  "source_page": "wiki/sources/<slug>.md 的完整 markdown 内容 — 严格遵循上述的源页面格式。关键：将关键人物、产品、概念和项目积极转换为内联 [[WikiLink]]",
  "index_entry": "- [标题](sources/slug.md) — 一行摘要",
  "overview_update": "wiki/overview.md 的完整更新内容，或 null",
  "entity_pages": [
    {"path": "entities/实体名.md", "content": "完整 markdown 内容"}
  ],
  "concept_pages": [
    {"path": "concepts/概念名.md", "content": "完整 markdown 内容"}
  ],
  "contradictions": ["描述与现有 Wiki 内容的任何矛盾，或空数组"],
  "log_entry": "## [2026-06-03] ingest | <标题>\\n\\n摄入源文档。关键主张: ..."
}

重要提示:
- source_page、entity_pages 和 concept_pages 中的每一页都必须包含完整的 YAML frontmatter (title, type, tags, sources 等字段)
- 所有 YAML frontmatter 使用英文字段名，内容使用中文
- 页面中使用 [[PageName]] 语法创建 Wiki 链接
"""

prompt2 = "你是个有趣的智能助手，告诉我世界第一高峰是什么？"

# 发起调用
setup_logging(level="INFO")
logger.info("=" * 60)
logger.info("开始调用 call_llm...")
logger.info("API Base: %s", os.environ['OPENAI_API_BASE'])
logger.info("Model: %s", os.environ['LLM_MODEL'])
logger.info("Prompt 长度: %d 字符", len(prompt))
logger.info("=" * 60)

result = call_llm(prompt, max_tokens=16384)

logger.info("\n" + "=" * 60)
logger.info("模型返回结果:")
logger.info("=" * 60)
logger.info(result)
logger.info("=" * 60)
