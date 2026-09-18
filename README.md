# LLM Wiki Engine

一个由 LLM 驱动的企业级知识库引擎，支持文档自动摄入、知识图谱构建、自然语言查询与图谱自愈。

> 本项目参考 [SamurAIGPT/llm-wiki-agent](https://github.com/SamurAIGPT/llm-wiki-agent) 的设计理念与架构，在其基础上进行了大量重构与增强，包括：SQLite 多项目存储、MCP Server 集成、Vue 3 现代化前端、多格式文档支持、图谱自愈等。

## 主视图

![LLM Wiki Engine 主视图](images/主视图.png)

## 特性

- **多格式文档摄入**：支持 Markdown 直接读取，PDF/DOCX/PPTX/XLSX 等 20+ 格式通过 markitdown 自动转换
- **LLM 驱动的知识提取**：自动提取实体、概念、关系，生成结构化 Wiki 页面
- **知识图谱**：基于 wikilink 和语义推理构建交互式图谱，支持社区检测与可视化
- **自然语言查询**：对知识库进行自然语言提问，LLM 综合多页面生成带引用的答案（支持流式输出）
- **图谱自愈**：自动检测缺失的实体页面并生成定义，修复断裂链接
- **健康检查**：结构检查（零 LLM 调用）+ 内容质量检查（LLM 语义分析）
- **REST API**：完整的 FastAPI 后端服务，支持前端 Web 界面与外部系统集成
- **MCP Server**：内置 Model Context Protocol 服务，AI 客户端可直接操作知识库
- **多知识库管理**：基于 SQLite 的多知识库隔离存储，支持 FTS5 全文搜索
- **Vue 3 前端**：现代化 Web UI（ui-apple），支持知识库管理、文件浏览、知识图谱可视化与对话式查询

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 20+（前端构建需要）
- uv（Python 包管理器）

### 后端配置

1. 进入后端目录：

```bash
cd server
```

2. 创建虚拟环境并安装依赖：

```bash
uv venv --python 3.13
.venv\Scripts\Activate.ps1  # Windows PowerShell
uv pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
```

3. 配置环境变量：

复制 `.env.example` 为 `.env`，配置 LLM API：

```env
# LLM API 配置
LLM_MODEL=deepseek-v4-flash
LLM_MODEL_FAST=deepseek-v4-flash
OPENAI_API_KEY=your_api_key
OPENAI_API_BASE=https://api.deepseek.com/v1

# 服务端口
API_PORT=5000
MCP_PORT=8081
```

4. 启动服务：

```bash
cd server
python api_server.py
```

5. **推荐部署**：用 Docker Compose（对外仅 `:5173`，见下方「Docker 部署」）。

### 前端开发（可选）

前端为 Vue 3 + Vite 项目，位于 `ui-apple/` 目录。本地开发时需**同时**启动后端与 Vite：

```bash
# 终端 1：后端
cd server
python api_server.py

# 终端 2：前端
cd ui-apple
npm install
npm run dev      # http://localhost:5173（API 经 Vite 代理到 :5000）
```

可选：`cd ui-apple && npm run build` 后，也可由 FastAPI 在 `:5000` 托管静态页（仅本地调试用；正式部署请用 Compose）。

---

## 项目文件结构

```
llm-wiki-engine/
├── server/                          # 后端服务
│   ├── wiki_engine/                 # 核心引擎模块
│   │   ├── __init__.py              # 模块初始化
│   │   ├── __main__.py              # 支持 python -m wiki_engine 运行
│   │   ├── cli.py                   # 命令行入口（build/update/query/lint/health/graph/heal 等子命令）
│   │   ├── constants.py             # 全局常量（文件扩展名、图谱颜色方案、默认路径）
│   │   ├── engine.py                # 主引擎 LLMWikiEngine（组装所有功能模块的统一接口）
│   │   ├── kbs.py                   # 知识库管理（KbManager）与文件导入（FileImporter）
│   │   ├── ingest.py                # 知识库构建与摄入工作流（IngestWorkflow）
│   │   ├── query.py                 # 知识库查询工作流（QueryWorkflow）
│   │   ├── health.py                # 健康检查与内容质量检查（HealthWorkflow）
│   │   ├── graph.py                 # 知识图谱构建（GraphWorkflow）
│   │   ├── heal.py                  # 图谱自愈（HealWorkflow）
│   │   ├── export.py                # 知识库导出与全文搜索（ExportManager）
│   │   ├── helpers.py               # 辅助方法（Wiki 上下文构建、索引更新、日志追加等）
│   │   └── prompt/                  # LLM Prompt 模板
│   │       ├── __init__.py
│   │       └── prompts.py           # 摄入/查询/图谱推理/自愈/质量检查等 Prompt
│   ├── storage/                     # 数据存储层
│   │   ├── __init__.py
│   │   ├── db.py                    # SQLite 数据库封装（WikiStorage 类，知识库 CRUD、文件 CRUD、全文搜索、目录树）
│   │   └── schema.sql               # 数据库表结构定义（FTS5 全文搜索、级联删除、自动触发器）
│   ├── tools/                       # 独立工具脚本
│   │   ├── file_to_md.py            # 批量文件格式转换（任意格式 → Markdown）
│   │   ├── pdf2md.py                # PDF/arXiv 专用转换（支持 marker/pymupdf4llm/arxiv2md 后端）
│   │   ├── refresh.py               # 源文档刷新（基于 SHA-256 哈希检测变化）
│   │   ├── utils.py                 # 通用工具函数（LLM 调用、wikilink 提取、JSON 解析等）
│   │   ├── health.py                # 独立健康检查脚本
│   │   └── logger.py                # 日志工具
│   ├── docs/                        # 文档
│   │   ├── automated-sync.md
│   │   └── automated-sync_zh.md
│   ├── .env.example                 # 环境变量示例
│   ├── api_server.py                # 兼容启动入口（uvicorn app.main:app）
│   ├── app/                         # FastAPI 应用（routers / MCP / SSE）
│   ├── tests/                       # API 冒烟测试
│   ├── requirements.txt             # Python 依赖
│   ├── pyproject.toml               # 项目配置（PEP 621）
│   ├── FORMATS.md                   # Wiki 页面格式规范
│   └── uv.lock                      # uv 依赖锁定文件
├── ui-apple/                        # Vue 3 前端（Apple 风格 UI）
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChatPanel.vue        # 对话式知识库查询面板
│   │   │   ├── DetailPanel.vue      # 文件详情/编辑面板
│   │   │   ├── FileView.vue         # 文件内容渲染视图
│   │   │   ├── GraphView.vue        # 知识图谱可视化（vis-network）
│   │   │   ├── ModalGroup.vue       # 通用模态框组件
│   │   │   ├── Sidebar.vue          # 知识库/文件树侧边栏
│   │   │   ├── StatusBar.vue        # 状态栏
│   │   │   └── Topbar.vue           # 顶部导航栏
│   │   ├── styles/
│   │   │   └── styles.css
│   │   ├── utils/
│   │   │   ├── api.js               # API 请求封装
│   │   │   └── markdown.js          # Markdown 渲染工具
│   │   ├── App.vue                  # 根组件
│   │   └── main.js                  # 入口文件
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── package-lock.json
├── skills/                          # 本地 Agent 调试 Skill（REST）
│   └── llm-wiki/                    # CRUD / 上传 / 构建 / 查询 / 导入导出
│       ├── SKILL.md
│       ├── reference.md
│       └── scripts/wiki.py
├── inbox/                           # Compose↔MCP 共享投递（宿主机 ↔ /data/inbox）
├── .dockerignore
├── .gitignore
├── AGENTS.md                        # Agent / 项目指引
├── Dockerfile.backend               # Compose 后端镜像
├── docker-compose.yml               # 官方部署：frontend + backend
├── LICENSE
└── README.md
```

---

## 核心模块说明

### wiki_engine/engine.py — 主引擎

`LLMWikiEngine` 类提供统一的对外接口，内部委托给各专业模块：

| 方法 | 说明 |
|------|------|
| `create_kb(name, description)` | 创建知识库，返回知识库 ID |
| `list_kbs()` | 列出所有知识库 |
| `delete_kb(kb_id)` | 删除知识库 |
| `import_raw_files(kb_id, source_dir)` | 导入本地目录的原始文件，自动转换格式 |
| `add_raw_content(kb_id, filename, content)` | 添加单个原始文件内容 |
| `build_knowledge_base(kb_id)` | 完整构建知识库（摄入 + 可选图谱） |
| `update_knowledge_base(kb_id, source_dir)` | 增量更新知识库 |
| `query(kb_id, question)` | 查询知识库，返回 LLM 生成的答案 |
| `query_stream(kb_id, question)` | 流式查询知识库，逐块返回答案 |
| `health_check(kb_id)` | 结构健康检查（零 LLM 调用） |
| `lint(kb_id)` | 内容质量检查（含 LLM 语义分析） |
| `build_graph(kb_id)` | 构建知识图谱（含语义推理） |
| `heal_graph(kb_id)` | 图谱自愈，补全缺失实体页面 |
| `export_kb(kb_id, output_dir)` | 导出知识库到磁盘 |
| `search(kb_id, keyword)` | 全文搜索 |
| `get_kb_stats(kb_id)` | 获取知识库统计 |
| `quick_build(kb_name, source_dir)` | 一键构建（创建知识库 → 导入 → 构建） |

### wiki_engine/cli.py — 命令行接口

通过 `python -m wiki_engine` 调用，支持以下子命令：

| 命令 | 说明 | 关键参数 |
|------|------|----------|
| `build` | 构建知识库 | `--kb`, `--source`, `--no-convert`, `--skip-graph` |
| `update` | 增量更新知识库 | `--kb-id`, `--source` |
| `query` | 查询知识库 | `--kb-id`, `--question`, `--save` |
| `lint` | 内容质量检查 | `--kb-id`, `--save` |
| `health` | 结构健康检查 | `--kb-id` |
| `graph` | 构建知识图谱 | `--kb-id` |
| `list` | 列出所有知识库 | — |
| `stats` | 知识库统计 | `--kb-id` |
| `heal` | 图谱自愈 | `--kb-id`, `--min-refs`, `--max-sources`, `--model` |

### storage/db.py — 数据存储

`WikiStorage` 类封装 SQLite 操作，基于 [schema.sql](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/storage/schema.sql) 定义的表结构：

| 方法 | 说明 |
|------|------|
| `create_kb(name, description)` | 创建知识库 |
| `delete_kb(kb_id)` | 删除知识库及关联文件（级联删除） |
| `get_kb(kb_id)` / `get_kb_by_name(name)` | 获取知识库信息 |
| `list_kbs()` | 列出所有知识库 |
| `add_file(kb_id, relative_path, content)` | 添加/替换文件（自动更新 FTS 索引） |
| `get_file_text_by_path(kb_id, relative_path)` | 获取文件文本内容 |
| `list_files(kb_id, prefix)` | 列出文件（支持目录前缀过滤） |
| `get_directory_tree(kb_id)` | 获取嵌套目录树结构 |
| `search(kb_id, keyword)` | 全文搜索（FTS5） |
| `export_kb(kb_id, output_dir)` | 导出知识库到磁盘目录 |
| `import_directory(kb_id, dir_path)` | 从磁盘导入目录 |
| `kb_stats(kb_id)` | 知识库统计（文件数、大小、分类分布） |
| `set_kb_state(kb_id, state)` | 更新知识库状态（unbuilt/building/completed） |

---

## REST API 接口

启动服务：`cd server && python api_server.py`（或 `uvicorn app.main:app --port 5000`），访问 `http://localhost:5000`（文档 `/docs`）

### 知识库 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/kbs` | 列出所有知识库 |
| POST | `/api/kbs` | 创建知识库（body: `{name, description}`） |
| GET | `/api/kbs/<id>` | 获取知识库详情 |
| DELETE | `/api/kbs/<id>` | 删除知识库 |
| GET | `/api/kbs/<id>/stats` | 获取知识库统计 |
| GET | `/api/kbs/<id>/instruction` | 获取构建指令 |
| PUT | `/api/kbs/<id>/instruction` | 更新构建指令（body: `{instruction}`） |

### 文件 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/kbs/<id>/tree` | 获取文件目录树 |
| GET | `/api/kbs/<id>/files?prefix=` | 列出文件（支持 prefix 过滤） |
| GET | `/api/kbs/<id>/files/<path>` | 获取文件内容 |
| PUT | `/api/kbs/<id>/files/<path>` | 更新文件内容（body: `{content}`） |

### 知识图谱 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/kbs/<id>/graph?file=` | 获取知识图谱 JSON 数据 |
| GET | `/api/kbs/<id>/graph/files` | 列出图谱目录下的文件 |

### 搜索 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/kbs/<id>/search?q=` | 全文搜索（FTS5） |

### 引擎工作流 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/kbs/<id>/build` | 构建知识库（完整流程） |
| POST | `/api/kbs/<id>/update` | 增量更新知识库（body: `{source_dir}` 可选） |
| POST | `/api/kbs/<id>/query` | 查询知识库（body: `{question, stream}`） |
| GET | `/api/kbs/<id>/health` | 健康检查 |
| POST | `/api/kbs/<id>/lint` | 内容质量检查 |
| POST | `/api/kbs/<id>/graph/build` | 构建知识图谱 |

### 文件上传与导入导出 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/kbs/<id>/import` | 从本地目录导入（body: `{source_dir}`） |
| POST | `/api/kbs/<id>/import-zip` | 上传 ZIP 压缩包导入（multipart/form-data） |
| POST | `/api/kbs/<id>/upload-file` | 上传单个文件/ZIP 到知识库（query: `update=true` 可选增量更新） |
| GET | `/api/kbs/<id>/export` | 导出知识库为 ZIP 下载 |
| POST | `/api/kbs/import` | 导入知识库 ZIP 包恢复完整知识库（multipart/form-data） |
| POST | `/api/external/upload` | 外部系统上传（multipart/form-data，form: `kb_name`, `files[]`） |

---

## 工作流说明

### 典型使用流程

```bash
cd server

# 1. 命令行一键构建
python -m wiki_engine build --kb "my-docs" --source ./local

# 2. 查询知识
python -m wiki_engine query --kb-id 1 --question "核心概念是什么？"

# 3. 健康检查
python -m wiki_engine health --kb-id 1

# 4. 构建知识图谱
python -m wiki_engine graph --kb-id 1

# 5. 图谱自愈
python -m wiki_engine heal --kb-id 1 --min-refs 3
```

### API 调用示例

```bash
# 创建知识库
curl -X POST http://localhost:5000/api/kbs \
  -H "Content-Type: application/json" \
  -d '{"name": "my-project", "description": "测试项目"}'

# 构建知识库
curl -X POST http://localhost:5000/api/kbs/1/build

# 查询（非流式）
curl -X POST http://localhost:5000/api/kbs/1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "项目的主要内容是什么？"}'

# 查询（流式 SSE）
curl -X POST http://localhost:5000/api/kbs/1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "项目的主要内容是什么？", "stream": true}'

# 外部上传文件
curl -X POST http://localhost:5000/api/external/upload \
  -F "kb_name=my-project" \
  -F "files=@document.pdf"
```

---

## MCP Server

LLM Wiki Engine 内置了 MCP (Model Context Protocol) Server，以 Streamable HTTP 方式运行，允许 AI 客户端（如 Claude Code、Cursor、Trae 等）直接调用知识库引擎的全部能力。

### 启动方式

MCP Server 随 API 服务一同启动（`python api_server.py` 或 `uvicorn app.main:app`），进程内默认监听 `8081`。仅在非 debug 模式下自动启动（`DEBUG=1` 时禁用）。

```bash
# 本地开发：启动 API + MCP
cd server
python api_server.py

# 日志：
#   MCP 服务: http://localhost:8081/mcp
```

**Docker Compose（推荐）**：宿主机只暴露前端 `5173`，nginx 统一反代 `/api` → backend:5000、`/mcp` → backend:8081。backend 端口不映射到宿主机。

```bash
docker compose up -d --build
# Web:  http://localhost:5173
# API:  http://localhost:5173/api/...
# MCP:  http://localhost:5173/mcp
```

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MCP_PORT` | `8081` | 容器/进程内 MCP 端口（compose 下不必对外映射） |
| `API_PORT` | `5000` | FastAPI (uvicorn) 服务端口 |
| `CORS_ORIGINS` | `*` | 逗号分隔；空则允许全部来源 |
| `MCP_ALLOWED_HOSTS` | （空） | 直连 MCP 端口时的额外 Host 白名单。经 compose 前端反代时 nginx 会改写 Host，一般无需配置 |
| `MCP_DNS_REBINDING_PROTECTION` | `1` | 设为 `0` 可关闭 Host 校验（仅可信内网） |

在 `server/.env` 中配置：

```env
# 服务端口
API_PORT=5000
MCP_PORT=8081
# 仅在「直连 :8081」且 Host 非 localhost 时需要：
# MCP_ALLOWED_HOSTS=192.168.7.203,host.docker.internal
```

### AI 客户端配置

**Docker Compose 统一入口（推荐）**：

```json
{
  "mcpServers": {
    "llm-wiki-engine": {
      "transport": "streamable_http",
      "url": "http://localhost:5173/mcp"
    }
  }
}
```

同宿主机其他容器（如 QwenPaw）可用：`http://host.docker.internal:5173/mcp`。

**本地直接跑后端**（未走 compose 前端）时仍用：

```json
{
  "mcpServers": {
    "llm-wiki-engine": {
      "type": "url",
      "url": "http://localhost:8081/mcp"
    }
  }
}
```

**通用 Streamable HTTP MCP 客户端**：Compose 下为 `http://<host>:5173/mcp`；直连后端为 `http://<host>:8081/mcp`。

### MCP 工具列表

| 工具名称 | 说明 | 关键参数 |
|---------|------|---------|
| `list_kbs` | 列出所有知识库及状态 | — |
| `create_kb` | 创建空知识库 | `name`, `description` |
| `import_kb` | 从 ZIP 创建知识库并导入 | `zip_url` / `file_path`, `kb_name` |
| `export_kb` | 导出知识库为 Base64 ZIP | `kb_id` |
| `delete_kb` | 删除知识库（不可逆） | `kb_id`, `confirm=true` |
| `build_knowledge` | 构建/增量更新知识库 | `kb_id`, `instruction`, `incremental` |
| `upload_files` | 追加服务端可读文件（Compose 推荐 `/data/inbox/...`） | `kb_id`, `file_path`, `auto_update` |
| `query_knowledge` | 自然语言查询知识库 | `kb_id`, `question` |
| `search_files` | 全文搜索 | `kb_id`, `keyword` |
| `read_wiki_file` | 读取知识库中指定文件内容 | `kb_id`, `relative_path` |

### 典型 MCP 工作流

AI 客户端通过 MCP 可实现端到端知识库管理：

1. `create_kb` 创建空知识库
2. **上传文档**：文件对 wiki 进程可读时用 `upload_files` + `file_path`（Compose 推荐 `/data/inbox/...`）；本机 REST 可用 [Skill：llm-wiki](#skillllm-wiki)
3. `build_knowledge` 构建知识库（可传入 `instruction` 定制编译行为）
4. `query_knowledge` 对知识库提问
5. `read_wiki_file` 读取具体 Wiki 页面内容
6. `export_kb` 导出知识库（便于迁移/备份）
7. `delete_kb` 清理不需要的知识库

---

## Skill：llm-wiki

目录：[`skills/llm-wiki/`](skills/llm-wiki/)

通过 REST 对接知识库（CRUD、上传、构建、查询、导入导出等）。入口：

```bash
# 默认 http://127.0.0.1:5000；Compose 可设 LLM_WIKI_API=http://127.0.0.1:5173

python skills/llm-wiki/scripts/wiki.py kbs list
python skills/llm-wiki/scripts/wiki.py upload --kb-id 1 --file /path/to/doc.md --update
python skills/llm-wiki/scripts/wiki.py build --kb-id 1
python skills/llm-wiki/scripts/wiki.py query --kb-id 1 --question "核心概念是什么？"
python skills/llm-wiki/scripts/wiki.py export --kb-id 1 --out ./kb.zip
```

说明：[`skills/llm-wiki/SKILL.md`](skills/llm-wiki/SKILL.md)；接口对照：[`skills/llm-wiki/reference.md`](skills/llm-wiki/reference.md)。

---

## 前端 UI（ui-apple）

项目包含一个基于 Vue 3 + Vite 的现代化 Web 前端，采用 Apple 设计风格：

- **知识库管理**：创建、切换、删除知识库，查看构建状态
- **文件浏览**：树形目录结构浏览 raw/wiki/graph 文件内容
- **知识图谱可视化**：基于 vis-network 的交互式力导向图，支持社区检测着色
- **对话式查询**：内置聊天面板，支持自然语言查询知识库
- **文件编辑**：支持在线编辑 Wiki 页面内容

### 开发

```bash
cd ui-apple
npm install
npm run dev       # 开发服务器 http://localhost:5173
npm run build     # 生产构建
```

---

## Docker 部署（官方唯一路径）

**只用 Docker Compose 双容器**，不要使用已移除的根目录一体机 `Dockerfile`。

| 服务 | 镜像构建 | 对外 |
|------|----------|------|
| `frontend` | `ui-apple/Dockerfile`（nginx + 静态资源） | **仅** `5173→80` |
| `backend` | `Dockerfile.backend`（FastAPI + MCP） | 不映射；仅容器网内 `5000` / `8081` |

统一入口：

| 用途 | URL |
|------|-----|
| Web UI | `http://localhost:5173` |
| REST API | `http://localhost:5173/api/...` |
| MCP | `http://localhost:5173/mcp` |

### 启动

先配置 `server/.env`（至少 `OPENAI_API_KEY` / `OPENAI_API_BASE` / `LLM_MODEL` 等），然后：

```bash
docker compose up -d --build
```

数据卷：`wiki-storage`、`wiki-uploads`；另将宿主机 `./inbox` 挂到容器 `/data/inbox`，供 Agent 与 MCP `upload_files` 共享投递。

常用命令：

```bash
docker compose logs -f backend
docker compose ps
docker compose down          # 停容器，保留卷
```

---

## 技术栈

| 层级 | 技术 |
|------|------|
| **后端语言** | Python 3.10+ |
| **Web 框架** | FastAPI + uvicorn |
| **MCP 协议** | FastMCP（Streamable HTTP） |
| **数据存储** | SQLite（FTS5 全文搜索、WAL 模式） |
| **LLM 调用** | litellm（兼容 OpenAI 接口的任意 LLM 服务） |
| **文档转换** | markitdown（支持 PDF/DOCX/PPTX/XLSX 等 20+ 格式） |
| **前端框架** | Vue 3 + Vite |
| **图谱可视化** | vis-network（力导向图） |
| **包管理** | uv（Python）/ npm（前端） |
| **容器化** | Docker Compose（frontend nginx + backend） |

---

## 参考项目

本项目参考 [SamurAIGPT/llm-wiki-agent](https://github.com/SamurAIGPT/llm-wiki-agent) 的设计理念与核心架构，并在此基础上进行了以下增强：

- **存储层重构**：从文件系统存储升级为 SQLite 多知识库存储，支持 FTS5 全文搜索
- **多知识库支持**：从单一知识库扩展为多知识库隔离管理
- **MCP Server 集成**：新增 MCP Streamable HTTP 服务，支持 AI 客户端直接操作知识库
- **现代化前端**：新增 Vue 3 + Vite 前端（ui-apple），支持图谱可视化与对话式查询
- **图谱自愈**：新增自动检测并补全缺失实体页面的能力
- **多格式文档支持**：集成 markitdown，支持 20+ 文档格式自动转换
- **流式查询**：支持 SSE 流式输出查询结果
- **Docker 部署**：Compose 双容器，对外仅 `:5173`，nginx 反代 `/api` 与 `/mcp`

## 许可证

MIT License