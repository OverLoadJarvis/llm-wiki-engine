# LLM Wiki Agent — 架构与工作流说明

本 wiki 完全由你的编码 agent 维护。无需 API 密钥或 Python 脚本——只需在 Codex、OpenCode 或任何能读取此文件的 agent 中打开此仓库，然后与它对话即可。

## 使用方法

用自然语言描述你想要做什么：
- *"摄入此文件：raw/papers/my-paper.md"*
- *"wiki 关于 transformer 模型说了什么？"*
- *"检查 wiki 中的孤立页面和矛盾之处"*
- *"构建知识图谱"*

或使用简写触发器：
- `ingest <file>` → 运行摄入工作流
- `query: <question>` → 运行查询工作流
- `health` → 运行健康检查工作流（快速，每次会话执行）
- `lint` → 运行代码检查工作流（耗时，定期执行）
- `build graph` → 运行图谱工作流

---

## 目录结构

```
raw/          # 不可变的源文档——永远不要修改这些
wiki/         # Agent 完全拥有此层
  index.md    # 所有页面的目录——每次摄入时更新
  log.md      # 仅追加的按时间顺序的记录
  overview.md # 跨所有源文档的动态综合
  sources/    # 每个源文档一个摘要页面
  entities/   # 人物、公司、项目、产品
  concepts/   # 想法、框架、方法、理论
  syntheses/  # 已保存的查询答案
graph/        # 自动生成的图谱数据
workflows/    # 需要 LLM 的完整工作流
  ingest.py   # 知识摄入工作流
  query.py    # 知识查询工作流
  lint.py     # 内容质量检查工作流
  build_graph.py  # 知识图谱构建工作流
  heal.py     # 图谱自愈工作流
tools/        # 不需要 LLM 的基础工具
  health.py   # 结构健康检查（确定性，无 LLM 调用）
  refresh.py  # 源页面刷新
  file_to_md.py  # 文件转 Markdown
  pdf2md.py   # PDF 转 Markdown
  utils.py    # 公共工具函数（LLM 调用、文件操作等）
```

---

## 页面格式

每个 wiki 页面使用此 frontmatter：

```yaml
---
title: "页面标题"
type: source | entity | concept | synthesis
tags: []
sources: []       # 为此页面提供信息的源页面 slug 列表
last_updated: YYYY-MM-DD
---
```

使用 `[[PageName]]` wikilink 来链接到其他 wiki 页面。

---

## 摄入工作流

触发方式：*"ingest <file>"*

**支持的格式：** Markdown（`.md`）直接摄入。非 markdown 文件（`.pdf`、`.docx`、`.pptx`、`.xlsx`、`.html`、`.txt`、`.csv`、`.json`、`.xml`、`.rst`、`.rtf`、`.epub`、`.ipynb`、`.yaml`、`.yml`、`.tsv`、`.wav`、`.mp3`）在摄入前通过 [markitdown](https://github.com/microsoft/markitdown) 自动转换为 markdown。使用 `--no-convert` 跳过自动转换。

步骤（按顺序）：
1. 完整阅读源文档（非 markdown 则自动转换）
2. 阅读 `wiki/index.md` 和 `wiki/overview.md` 获取当前 wiki 上下文
3. 写入 `wiki/sources/<slug>.md`——使用下方的源页面格式
4. 更新 `wiki/index.md`——在 Sources 部分添加条目
5. 更新 `wiki/overview.md`——如有需要则修订综合内容
6. 更新/创建提及的关键人物、公司、项目的实体页面
7. 更新/创建讨论的关键想法和框架的概念页面
8. 标记与现有 wiki 内容的任何矛盾
9. 追加到 `wiki/log.md`：`## [YYYY-MM-DD] ingest | <标题>`
10. **摄入后验证**——检查损坏的 `[[wikilinks]]`，验证所有新页面都在 `index.md` 中，打印变更摘要

### 源页面格式

```markdown
---
title: "源标题"
type: source
tags: []
date: YYYY-MM-DD
source_file: raw/...
---

## 摘要
2-4 句话的摘要。

## 关键主张
- 主张 1
- 主张 2

## 关键引用
> "引用内容"——上下文

## 关联
- [[实体名称]]——它们如何关联
- [[概念名称]]——它如何连接

## 矛盾
- 与 [[其他页面]] 在以下方面矛盾：...
```

### 领域特定模板

如果源文档属于特定领域（例如个人日记、会议记录），agent 应使用专用模板而不是上方的默认通用模板：

#### 日记模板
```markdown
---
title: "YYYY-MM-DD 日记"
type: source
tags: [diary]
date: YYYY-MM-DD
---
## 事件摘要
...
## 关键决策
...
## 精力与情绪
...
## 关联
...
## 转变与矛盾
...
```

#### 会议记录模板
```markdown
---
title: "会议标题"
type: source
tags: [meeting]
date: YYYY-MM-DD
---
## 目标
...
## 关键讨论
...
## 做出的决策
...
## 行动项
...
```

---

## 查询工作流

触发方式：*"query: <question>"*

步骤：
1. 阅读 `wiki/index.md` 识别相关页面
2. 阅读这些页面
3. 综合答案，使用 `[[PageName]]` wikilink 作为内联引用
4. 询问用户是否要将答案归档为 `wiki/syntheses/<slug>.md`

---

## 代码检查工作流

触发方式：*"lint"*

检查项：
- **孤立页面**——没有其他页面通过 `[[links]]` 链接到的 wiki 页面
- **损坏链接**——指向不存在页面的 `[[WikiLinks]]`
- **矛盾**——跨页面冲突的主张
- **过时摘要**——新源文档出现后未更新的页面
- **缺失实体页面**——在 3+ 页面中被提及但没有自己页面的实体
- **稀疏页面**——出站 `[[wikilinks]]` 少于 2 个的页面（链接密度预算）
- **数据缺口**——wiki 无法回答的问题；建议新源文档

图谱感知检查（需要 `build graph` 生成的 `graph.json`）：
- **枢纽存根**——度数 > μ+2σ 的神节点，但内容单薄（< 500 字符）
- **脆弱桥梁**——仅通过 1 条边连接的社区对
- **孤立社区**——零外部连接的集群

输出代码检查报告，并询问用户是否要保存到 `wiki/lint-report.md`。

---

## 健康检查工作流

触发方式：*"health"*

运行：`python tools/health.py`（或 `python tools/health.py --json` 获取机器可读输出）

快速结构完整性检查——**零 LLM 调用**，每次会话安全运行：
- **空/存根文件**——除 frontmatter 外无内容的页面（限制速率损害）
- **索引同步**——`wiki/index.md` 条目与磁盘上的实际文件对比
- **日志覆盖**——源页面在 `wiki/log.md` 中缺少对应的 `ingest` 条目

输出健康报告。使用 `--save` 写入到 `wiki/health-report.md`。

### 健康检查与代码检查的边界

| 维度 | `health` | `lint` |
|---|---|---|
| **范围** | 结构完整性 | 内容质量 |
| **LLM 调用** | 零 | 是（语义分析） |
| **成本** | 免费 | Token |
| **频率** | 每次会话，在其他工作之前 | 每 10-15 次摄入 |
| **检查项** | 空文件、索引同步、日志同步 | 孤立页面、损坏链接、矛盾、缺口 |
| **工具** | `tools/health.py` | `workflows/lint.py` |
| **运行顺序** | 首先（预检） | 健康检查通过后 |

> 先运行 `health`——对空文件进行代码检查会浪费 token。

---

## 图谱工作流

触发方式：*"build graph"*

首先尝试：`python workflows/build_graph.py --open`

如果 Python/依赖不可用，则手动构建：
1. 搜索所有 wiki 页面中的 `[[wikilinks]]`
2. 构建节点（每个页面一个）和边（每个链接一条）
3. 推断 wikilinks 未捕获的隐式关系——标记 `INFERRED` 并附带置信度分数；低置信度 → `AMBIGUOUS`
4. 写入 `graph/graph.json`，包含 `{nodes, edges, built: date}`
5. 写入 `graph/graph.html` 作为自包含的 vis.js 可视化

---

## 命名约定

- 源 slug：`kebab-case`，与源文件名匹配
- 实体页面：`TitleCase.md`（例如 `OpenAI.md`、`SamAltman.md`）
- 概念页面：`TitleCase.md`（例如 `ReinforcementLearning.md`、`RAG.md`）

## 索引格式

```markdown
# Wiki 索引

## 概述
- [概述](overview.md)——动态综合

## 源文档
- [源标题](sources/slug.md)——一行摘要

## 实体
- [实体名称](entities/EntityName.md)——一行描述

## 概念
- [概念名称](concepts/ConceptName.md)——一行描述

## 综合
- [分析标题](syntheses/slug.md)——它回答的问题
```

## 日志格式

`## [YYYY-MM-DD] <操作> | <标题>`

操作：`ingest`、`query`、`health`、`lint`、`graph`、`report`

---

## 图谱健康报告

触发方式：*"graph report"* 或 `python workflows/build_graph.py --report`

`--report` 标志生成结构化的图谱健康报告，涵盖：
- **健康摘要**——边/节点比、孤立页面百分比、社区数量、链接密度
- **孤立节点**——零图谱连接的页面
- **神节点**——度数 > μ+2σ 的枢纽页面（连接数不成比例）
- **脆弱桥梁**——仅通过 1 条边连接的社区对
- **幻影枢纽**——被 2+ 现有页面通过 `[[wikilinks]]` 引用但指向不存在页面的链接（页面创建信号）

使用 `--save` 将报告写入到 `graph/graph-report.md`。

---

## 第三阶段设计约束（自动链接——开放中）

第三阶段提议基于图谱分析自动插入 `[[wikilink]]`。以下硬性规则适用：

### 晋升门控：`draft → stable`
- 自动链接的边以 `DRAFT` 状态开始（在图谱中可见，不写入页面正文）
- 专门的 `promote` 阶段验证源依据 + 一致性
- 只有通过验证的边才会作为 `[[wikilinks]]` 实体化到页面中
- **链接密度预算**：页面在晋升前必须有 ≥2 个出站 wikilink

### 硬性规则
| ID | 规则 | 理由 |
|---|---|---|
| HG-WA-01 | 图谱层绝对不能从损坏链接自动创建页面——仅报告 | LLM 摄入会产生幻觉 wikilink；自动创建会放大噪声 |
| HG-WA-02 | 新的斜杠命令绝对不能与现有命令覆盖范围重复 | 防止用户混淆；合并到现有命令中 |
| HG-WA-03 | 源文件内容是中文，提取的知识也必须是中文 | 保持知识的一致性 |

