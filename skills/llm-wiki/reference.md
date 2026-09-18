# LLM Wiki Skill — REST 对照

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LLM_WIKI_API` | `http://127.0.0.1:5000` | API 根地址。Compose 用 `http://127.0.0.1:5173` |

## CLI → REST

| `wiki.py` 命令 | HTTP |
|----------------|------|
| `kbs list` | `GET /api/kbs` |
| `kbs create` | `POST /api/kbs` JSON `{name, description}` |
| `kbs get` | `GET /api/kbs/{id}` |
| `kbs delete --confirm` | `DELETE /api/kbs/{id}` |
| `kbs stats` | `GET /api/kbs/{id}/stats` |
| `instruction get/set` | `GET/PUT /api/kbs/{id}/instruction` |
| `upload --kb-id` | `POST /api/kbs/{id}/upload-file?update=` multipart `file` |
| `upload --kb-name` | `POST /api/external/upload` multipart `kb_name` + `files` |
| `build` | `POST /api/kbs/{id}/build` `{stream:false}` |
| `update` | `POST /api/kbs/{id}/update` |
| `query` | `POST /api/kbs/{id}/query` `{question, stream:false}` |
| `search` | `GET /api/kbs/{id}/search?q=` |
| `files tree/list/get/put` | `/api/kbs/{id}/tree` · `/files` · `/files/{path}` |
| `health` | `GET /api/kbs/{id}/health` |
| `lint` | `POST /api/kbs/{id}/lint` |
| `graph get/build` | `GET /api/kbs/{id}/graph` · `POST .../graph/build` |
| `export` | `GET /api/kbs/{id}/export` → 本机 ZIP |
| `import-kb` | `POST /api/kbs/import` multipart |
| `import-zip` | `POST /api/kbs/{id}/import-zip` multipart |
| `import-dir` | `POST /api/kbs/{id}/import` JSON `{source_dir}`（服务端路径） |

一律非流式（`stream=false`），便于脚本解析 JSON。
