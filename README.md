# LLM Wiki Engine

一个由 LLM 驱动的企业级知识库引擎，支持文档自动摄入、知识图谱构建、自然语言查询与图谱自愈。

## 特性

- **多格式文档摄入**：支持 Markdown 直接读取，PDF/DOCX/PPTX/XLSX 等 20+ 格式通过 markitdown 自动转换
- **LLM 驱动的知识提取**：自动提取实体、概念、关系，生成结构化 Wiki 页面
- **知识图谱**：基于 wikilink 和语义推理构建交互式图谱，支持社区检测与可视化
- **自然语言查询**：对知识库进行自然语言提问，LLM 综合多页面生成带引用的答案
- **图谱自愈**：自动检测缺失的实体页面并生成定义，修复断裂链接
- **健康检查**：结构检查（零 LLM 调用）+ 内容质量检查（LLM 语义分析）
- **REST API**：完整的 Flask 后端服务，支持前端 Web 界面与外部系统集成
- **多项目管理**：基于 SQLite 的多项目隔离存储

## 快速开始

### 环境配置

1. 创建虚拟环境：
```bash
uv venv --python 3.13.3
```

2. 激活虚拟环境：
```bash
# Windows PowerShell
.venv\Scripts\Activate.ps1

# Windows CMD
.venv\Scripts\activate.bat
```

3. 安装依赖：
```bash
uv pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
```

4. 配置环境变量：
创建 `.env` 文件，配置 LLM API：
```env
LLM_MODEL=claude-3-5-sonnet-latest
OPENAI_API_KEY=your_api_key
OPENAI_API_BASE=https://api.openai.com/v1
```

---

## 项目文件结构

```
llm-wiki/
├── wiki_engine/              # 核心引擎模块
│   ├── __init__.py           # 模块初始化
│   ├── __main__.py           # 支持 python -m wiki_engine 运行
│   ├── cli.py                # 命令行入口（build/update/query/lint/health/graph/heal 等子命令）
│   ├── constants.py          # 全局常量（文件扩展名、图谱颜色方案、默认路径）
│   ├── engine.py             # 主引擎 LLMWikiEngine（组装所有功能模块的统一接口）
│   ├── projects.py           # 项目管理（ProjectManager）与文件导入（FileImporter）
│   ├── ingest.py             # 知识库构建与摄入工作流（IngestWorkflow）
│   ├── query.py              # 知识库查询工作流（QueryWorkflow）
│   ├── health.py             # 健康检查与内容质量检查（HealthWorkflow）
│   ├── graph.py              # 知识图谱构建（GraphWorkflow）
│   ├── heal.py               # 图谱自愈（HealWorkflow）
│   └── export.py             # 项目导出与全文搜索（ExportManager）
│
├── storage/                  # 数据存储层
│   ├── __init__.py           # 模块初始化
│   ├── db.py                 # SQLite 数据库封装（WikiStorage 类，项目 CRUD、文件 CRUD、全文搜索、目录树）
│   ├── schema.sql            # 数据库表结构定义
│   └── wiki.db               # SQLite 数据库文件（运行时生成）
│
├── tools/                    # 独立工具脚本
│   ├── file_to_md.py         # 批量文件格式转换（任意格式 → Markdown）
│   ├── pdf2md.py             # PDF/arXiv 专用转换（支持 marker/pymupdf4llm/arxiv2md 后端）
│   ├── refresh.py            # 源文档刷新（基于 SHA-256 哈希检测变化）
│   ├── utils.py              # 通用工具函数
│   └── health.py             # 独立健康检查脚本
│
├── web/                      # 前端资源
│   └── index.html            # Web UI 单页应用
│
├── test/                     # 测试脚本
│   ├── __init__.py
│   ├── llm_chat.py           # LLM 对话测试
│   ├── llm_connection_test.py # LLM 连接测试
│   ├── llm_simple_chat.py    # 简单对话测试
│   └── test_call_llm.py      # LLM 调用测试
│
├── local/                    # 本地示例文档（孙子兵法）
├── tmp/                      # 临时调试文件
│
├── api_server.py             # Flask REST API 后端服务
├── requirements.txt          # Python 依赖
├── pyproject.toml            # 项目配置（PEP 621）
├── .env.example              # 环境变量示例
├── FORMATS.md                # 格式规范文档
├── Dockerfile                # Docker 镜像构建
└── .dockerignore             # Docker 忽略文件
```

---

## 核心模块说明

### wiki_engine/engine.py — 主引擎

`LLMWikiEngine` 类提供统一的对外接口，内部委托给各专业模块：

| 方法 | 说明 |
|------|------|
| `create_project(name, description)` | 创建项目，返回项目 ID |
| `list_projects()` | 列出所有项目 |
| `delete_project(project_id)` | 删除项目 |
| `import_raw_files(project_id, source_dir)` | 导入本地目录的原始文件 |
| `add_raw_content(project_id, filename, content)` | 添加单个原始文件 |
| `build_knowledge_base(project_id)` | 完整构建知识库（摄入 + 可选图谱） |
| `update_knowledge_base(project_id, source_dir)` | 增量更新知识库 |
| `query(project_id, question, save=False)` | 查询知识库，返回 LLM 生成的答案 |
| `health_check(project_id)` | 结构健康检查（零 LLM 调用） |
| `lint(project_id, save=False)` | 内容质量检查（含 LLM 语义分析） |
| `build_graph(project_id)` | 构建知识图谱 |
| `heal_graph(project_id)` | 图谱自愈，补全缺失实体页面 |
| `export_project(project_id, output_dir)` | 导出项目到磁盘 |
| `search(project_id, keyword)` | 全文搜索 |
| `get_project_stats(project_id)` | 获取项目统计 |
| `quick_build(project_name, source_dir)` | 一键构建（创建项目 → 导入 → 构建） |

### wiki_engine/cli.py — 命令行接口

通过 `python -m wiki_engine` 调用，支持以下子命令：

| 命令 | 说明 | 关键参数 |
|------|------|----------|
| `build` | 构建知识库 | `--project`, `--source`, `--no-convert`, `--skip-graph` |
| `update` | 增量更新知识库 | `--project-id`, `--source` |
| `query` | 查询知识库 | `--project-id`, `--question`, `--save` |
| `lint` | 内容质量检查 | `--project-id`, `--save` |
| `health` | 结构健康检查 | `--project-id` |
| `graph` | 构建知识图谱 | `--project-id` |
| `list` | 列出所有项目 | — |
| `stats` | 项目统计 | `--project-id` |
| `heal` | 图谱自愈 | `--project-id`, `--min-refs`, `--max-sources`, `--model` |

### storage/db.py — 数据存储

`WikiStorage` 类封装 SQLite 操作：

| 方法 | 说明 |
|------|------|
| `create_project(name, description)` | 创建项目 |
| `delete_project(project_id)` | 删除项目及关联文件 |
| `get_project(project_id)` / `get_project_by_name(name)` | 获取项目信息 |
| `list_projects()` | 列出所有项目 |
| `add_file(project_id, relative_path, content)` | 添加/替换文件 |
| `get_file_text_by_path(project_id, relative_path)` | 获取文件文本内容 |
| `list_files(project_id, prefix)` | 列出文件（支持目录前缀过滤） |
| `get_directory_tree(project_id)` | 获取嵌套目录树结构 |
| `search(project_id, keyword)` | 全文搜索（FTS5） |
| `export_project(project_id, output_dir)` | 导出项目到磁盘目录 |
| `import_directory(project_id, dir_path)` | 从磁盘导入目录 |
| `project_stats(project_id)` | 项目统计（文件数、大小、分类分布） |

---

## REST API 接口

启动服务：`python api_server.py`，访问 `http://localhost:5000`

### 项目 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/projects` | 列出所有项目 |
| POST | `/api/projects` | 创建项目（body: `{name, description}`） |
| GET | `/api/projects/<id>` | 获取项目详情 |
| DELETE | `/api/projects/<id>` | 删除项目 |
| GET | `/api/projects/<id>/stats` | 获取项目统计 |

### 文件 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/projects/<id>/tree` | 获取文件目录树 |
| GET | `/api/projects/<id>/files?prefix=` | 列出文件（支持 prefix 过滤） |
| GET | `/api/projects/<id>/files/<path>` | 获取文件内容 |

### 知识图谱 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/projects/<id>/graph?file=` | 获取知识图谱 JSON 数据 |
| GET | `/api/projects/<id>/graph/files` | 列出图谱目录下的文件 |

### 搜索 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/projects/<id>/search?q=` | 全文搜索 |

### 引擎工作流 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/projects/<id>/build` | 构建知识库（完整流程） |
| POST | `/api/projects/<id>/update` | 增量更新知识库（body: `{source_dir}` 可选） |
| POST | `/api/projects/<id>/query` | 查询知识库（body: `{question}`） |
| GET | `/api/projects/<id>/health` | 健康检查 |
| POST | `/api/projects/<id>/lint` | 内容质量检查 |
| POST | `/api/projects/<id>/graph/build` | 构建知识图谱 |

### 文件上传 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/projects/<id>/import` | 从本地目录导入（body: `{source_dir}`） |
| POST | `/api/projects/<id>/upload-file` | 上传单个文件到项目（multipart/form-data，query: `update=true` 可选增量更新） |
| POST | `/api/external/upload` | 外部系统上传（multipart/form-data，form: `project_name`, `files[]`） |

---

## 工作流说明

### 典型使用流程

```bash
# 1. 命令行一键构建
python -m wiki_engine build --project "my-docs" --source ./local

# 2. 查询知识
python -m wiki_engine query --project-id 1 --question "核心概念是什么？"

# 3. 健康检查
python -m wiki_engine health --project-id 1

# 4. 构建知识图谱
python -m wiki_engine graph --project-id 1

# 5. 图谱自愈
python -m wiki_engine heal --project-id 1 --min-refs 3
```

### API 调用示例

```bash
# 创建项目
curl -X POST http://localhost:5000/api/projects \
  -H "Content-Type: application/json" \
  -d '{"name": "my-project", "description": "测试项目"}'

# 构建知识库
curl -X POST http://localhost:5000/api/projects/1/build

# 查询
curl -X POST http://localhost:5000/api/projects/1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "项目的主要内容是什么？"}'

# 外部上传文件
curl -X POST http://localhost:5000/api/external/upload \
  -F "project_name=my-project" \
  -F "files=@document.pdf"
```

---

## Docker 部署

### 构建镜像

```bash
docker build -t llm-wiki .
```

### 运行容器

```bash
docker run -d -p 5000:5000 \
  -e LLM_MODEL=deepseek-v4-flash \
  -e OPENAI_API_KEY=your-api-key \
  -e OPENAI_API_BASE=https://api.deepseek.com/v1 \
  --name llm-wiki \
  llm-wiki
```

### 挂载持久化数据

```bash
docker run -d -p 5000:5000 \
  -v $(pwd)/storage:/app/storage \
  -v $(pwd)/uploads:/app/uploads \
  -e LLM_MODEL=deepseek-v4-flash \
  -e OPENAI_API_KEY=your-api-key \
  -e OPENAI_API_BASE=https://api.deepseek.com/v1 \
  --name llm-wiki \
  llm-wiki
```

---

## 技术栈

- **Python 3.13+** — 主语言
- **SQLite** — 数据存储（支持 FTS5 全文搜索）
- **Flask + Flask-CORS** — REST API 后端
- **markitdown** — 多格式文档转换
- **LLM API** — 兼容 OpenAI 接口的任意 LLM 服务
- **uv** — 虚拟环境与包管理

## 许可证

MIT License
