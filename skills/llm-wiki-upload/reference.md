# LLM Wiki 上传 — API 说明

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LLM_WIKI_API` | `http://127.0.0.1:5000` | Flask API 根地址（不是 MCP 的 `:8081`） |

## 本 Skill 使用的接口

### 列出知识库

```http
GET /api/kbs
```

### 向已有知识库上传单文件或 ZIP

```http
POST /api/kbs/<kb_id>/upload-file?update=false
Content-Type: multipart/form-data

file=<二进制>
```

- `update=true`：导入后触发增量更新
- `.zip`：服务端解压后导入全部成员

### 按知识库名称上传（不存在则创建）

```http
POST /api/external/upload
Content-Type: multipart/form-data

kb_name=<字符串>
files=<一个或多个文件>
```

表单字段名是 `files`（可重复），不是 `file`。

## MCP 与 REST 怎么选

| 任务 | 优先方式 |
|------|----------|
| 上传本机文件 | 本 Skill / REST multipart |
| 列表 / 查询 / 构建 | MCP Streamable HTTP `:8081/mcp` |
| 文件已在 MCP 服务端磁盘 | MCP `upload_files` + `file_path` |

## 跨 Docker 注意

- Agent 在容器 A、API 在宿主机映射端口：设置 `LLM_WIKI_API` 为网关或局域网 IP
- 文件路径是 Agent 侧本地路径；文档需挂载进 Agent 容器才可读
- MCP 的 `MCP_ALLOWED_HOSTS` 与本 REST 上传无关
