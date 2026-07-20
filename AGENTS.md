# LLM Wiki Engine

LLM 驱动的企业级知识库引擎：文档摄入 → 知识提取 → Wiki / 图谱构建 → 自然语言查询。

参考 [SamurAIGPT/llm-wiki-agent](https://github.com/SamurAIGPT/llm-wiki-agent)，在本地做了大量增强（SQLite 多知识库、MCP、Vue 前端、图谱自愈、多格式文档等）。

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.10+、Flask + Flask-CORS、FastMCP（Streamable HTTP） |
| 存储 | SQLite（FTS5 全文搜索、WAL） |
| LLM | litellm（兼容 OpenAI 接口的任意服务） |
| 文档转换 | markitdown（PDF/DOCX/PPTX/XLSX 等 20+ 格式） |
| 前端 | Vue 3 + Vite、vis-network |
| 包管理 | uv（Python）/ npm（前端） |
| 部署 | Docker 多阶段构建；`docker-compose.yml` 前后端双容器 |

## 核心功能

- **多格式摄入**：Markdown 直读；其它格式经 markitdown 转 Markdown
- **LLM 知识提取**：实体 / 概念 / 关系 → 结构化 Wiki 页面
- **知识图谱**：wikilink + 语义推理；社区检测与可视化
- **自然语言查询**：多页面综合回答，带引用；支持 SSE 流式输出
- **图谱自愈**：检测缺失实体页并生成定义，修复断链
- **健康检查**：结构检查（无 LLM）+ 内容质量检查（LLM）
- **多知识库**：SQLite 隔离存储，FTS5 搜索
- **REST API**：Flask，端口默认 `5000`
- **MCP Server**：Streamable HTTP，端口默认 `8081`，供 Cursor / Claude 等直接调知识库
- **Web UI（ui-apple）**：知识库管理、文件树、图谱、对话查询、在线编辑

## 目录结构（关键）

```
llm-wiki-engine/
├── server/                 # 后端
│   ├── api_server.py       # Flask REST + MCP 入口
│   ├── wiki_engine/        # 核心引擎（ingest/query/graph/heal/health/…）
│   ├── storage/            # SQLite（db.py + schema.sql）
│   ├── tools/              # 转换、日志、LLM 工具等
│   ├── .env.example        # 环境变量模板
│   └── requirements.txt
├── ui-apple/               # Vue 3 前端
├── docker-compose.yml
├── Dockerfile / Dockerfile.backend
└── README.md               # 完整 API / CLI / MCP / 部署说明
```

## 本地运行（速查）

**后端**

```bash
cd server
uv venv --python 3.13
# Windows: .venv\Scripts\Activate.ps1
uv pip install -r requirements.txt
# 复制 .env.example → .env，配置 OPENAI_API_KEY / OPENAI_API_BASE / LLM_MODEL 等
python api_server.py
```

- API：`http://localhost:5000`
- MCP：`http://localhost:8081/mcp`（非 debug 模式自动启动）

**前端开发**

```bash
# 终端 1：后端
cd server && python api_server.py

# 终端 2：前端
cd ui-apple && npm install && npm run dev   # http://localhost:5173
```

生产构建：`cd ui-apple && npm run build`，产物可由 Flask 托管（访问 `:5000`）。

**CLI 示例**

```bash
cd server
python -m wiki_engine build --kb "my-docs" --source ./local
python -m wiki_engine query --kb-id 1 --question "核心概念是什么？"
python -m wiki_engine health --kb-id 1
python -m wiki_engine graph --kb-id 1
python -m wiki_engine heal --kb-id 1
```

## 给 Agent 的注意点

- 详细 API 路由、MCP 工具表、工作流说明以根目录 `README.md` 为准
- 后端日志用 `tools.logger.get_logger`，不要用 `print`；外部调用需记日志（见 `.cursor/rules/logging.mdc`）
- 前端 API 封装在 `ui-apple/src/utils/`；日志用带模块前缀的 `console`
- 敏感配置在 `server/.env`，勿提交密钥
- 本地文档 `docs/孙子兵法/` 与 `ui-apple/.vite/` 已在 `.gitignore` 中
