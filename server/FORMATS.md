# Wiki 格式规范

本文档集中描述 wiki 中所有文件/页面的格式规范，并说明每种格式的适用场景。

---

## 1. 通用页面格式

**适用文件：** `wiki/` 下所有页面文件（包括 `wiki/sources/`、`wiki/entities/`、`wiki/concepts/`、`wiki/syntheses/` 下的每一篇 `.md` 页面）。

**用途：** 这是所有 wiki 页面的通用元数据头。每个页面文件开头都必须包含此 frontmatter，用于声明页面的标题、类型、标签、引用来源和更新时间。

```yaml
---
标题: "页面标题"
索引: "页面索引名"
类型: source | entity | concept | synthesis
标签: []
来源: []       # list of source slugs that inform this page
更新时间: YYYY-MM-DD
---
```

`索引` 字段用于生成页面的 URL，应与文件名匹配。
`类型` 字段取值说明：
- `source` — 来源文档摘要页
- `entity` — 实体页（人物、公司、项目、产品）
- `concept` — 概念页（思想、框架、方法、理论）
- `synthesis` — 综合/分析页（保存的查询回答）

正文中使用 `[[索引]]` wikilinks 链接到其他 wiki 页面。

---

## 2. 命名规范

**适用场景：** 创建任何新的 wiki 页面文件时的文件命名规则。

| 页面类型 | 命名规则 | 示例 |
|---|---|---|
| 来源页 | `标题.md`，与源文件名匹配 | `我的文章` |
| 实体页 | `标题案例.md` | `OpenAI.md`、`SamAltman.md` |
| 概念页 | `标题案例.md` | `强化学习.md`、`RAG.md` |

---

## 3. 来源页格式

**适用文件：** `wiki/sources/<slug>.md`

**用途：** 每摄入一份原始文档（`raw/` 目录下的文件），都应在 `wiki/sources/` 下生成一篇对应摘要页。此模板用于规范摘要页的结构。

```markdown
---
标题: "源标题"
索引: "源索引名"
类型: source
标签: []
日期: YYYY-MM-DD
来源: raw/...
---

## 摘要
2–4 句子总结源文档的主要内容。

## 关键断言
- 断言 1
- 断言 2

## 引用内容
> "引用内容" — 上下文

## 关联
- [[实体名称]] — 实体之间的关系
- [[概念名称]] — 概念之间的联系

## 矛盾
- 与[[其他页面]]的矛盾： — ...
```

---

## 4. 特定领域模板

当摄入的源文档属于特定领域时，应使用专用模板替代上述通用来源页格式。

### 4a. 日记模板

**适用文件：** `wiki/sources/<slug>.md`（当源文档为个人日记/日志时）

```markdown
---
标题: "YYYY-MM-DD 日记标题"
索引: "YYYY-MM-DD-日记"
类型: source
标签: [diary]
日期: YYYY-MM-DD
---
## 事件摘要
...
## 决策键
...
## 能量 & Mood
...
## 关联
...
## 变化 & 矛盾
...
```

### 4b. 会议记录模板

**适用文件：** `wiki/sources/<slug>.md`（当源文档为会议记录时）

```markdown
---
标题: "会议标题"
索引: "YYYY-MM-DD-会议"
类型: source
标签: [meeting]
日期: YYYY-MM-DD
---
## 目标
...
## 讨论键
...
## 决策键
...
## 动作项
...
```

---

## 5. 索引格式

**适用文件：** `wiki/index.md`

**用途：** `wiki/index.md` 是整个 wiki 的目录/索引页，记录所有 wiki 页面的清单。每次完成 ingest 操作后都需要更新此文件。

```markdown
# Wiki Index

## 全局概览
- [全局概览](overview.md) — 全局概览/综合页

## 来源文档
- [源文档标题](sources/slug.md) — 源文档摘要页

## 实体页
- [实体名称](entities/EntityName.md) — 实体页描述

## 概念页
- [概念名称](concepts/ConceptName.md) — 概念页描述

## Synthesis
- [分析标题](syntheses/slug.md) — 问题回答
```

---

## 7. 概述格式

**适用文件：** `wiki/overview.md`

**用途：** `wiki/overview.md` 是整个 wiki 的全局概览/综合页，由 LLM 在每次摄入后自动更新。它整合了所有来源文档、实体和概念的核心信息，形成一份连贯的、持续演进的知识总结。

此文件没有固定的 YAML frontmatter，正文结构由 LLM 根据当前 wiki 状态动态生成，通常包含：

```markdown
# Wiki 概览

## 摘要
知识库的主题和范围的简要概述。

## 关键实体
- [[实体名称]] — 实体页描述
- [[实体名称]] — 实体页描述

## 核心概念
- [[概念名称]] — 概念页描述
- [[概念名称]] — 概念页描述

## 发现
- 发现 1
- 发现 2

## 矛盾
- 矛盾关系 1
- 开放问题 1

## 时间线
- YYYY-MM-DD: 事件/摄入
- YYYY-MM-DD: 事件/摄入
```

每次 ingest 操作时，LLM 会读取当前 `overview.md` 的内容，结合新摄入的源文档，生成更新后的完整内容并覆盖原文件。

---

## 8. 日志格式

**适用文件：** `wiki/log.md`

**用途：** `wiki/log.md` 是 wiki 的追加式操作日志，记录每一次操作（ingest、query、health、lint、graph、report 等）。每次操作完成后在文件末尾追加一条新记录。

格式：

```
## [YYYY-MM-DD] <operation> | <title>
```

其中 `<operation>` 可以是：`ingest`、`query`、`health`、`lint`、`graph`、`report`