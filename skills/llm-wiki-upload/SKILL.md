---
name: llm-wiki-upload
description: >-
  通过 REST multipart 将本机文档上传到 LLM Wiki Engine 知识库（避免 MCP base64）。
  在用户需要上传/导入文件到知识库、跨 Docker 向 llm-wiki 追加文档，或 MCP
  streamable_http 的 upload_files 不便使用时启用。触发词：上传知识库、导入文档、
  llm-wiki upload、upload to wiki。
---

# LLM Wiki 本地上传 Skill

## 解决什么问题

MCP Streamable HTTP 的 `upload_files` 跨容器时不好用：

- `file_path` 读的是 **MCP 服务端**路径，不是 Agent / QwenPaw 本机路径
- `content_base64` 体积膨胀、中文易乱码、大文件不现实

本 Skill 让 Agent（或人工）在 **能读本地文件的一侧** 调用 REST `multipart/form-data` 上传，二进制直传，无 Base64。

查询 / 构建仍可用 MCP（`list_kbs`、`query_knowledge`、`build_knowledge`）。

## API 基址

```text
环境变量 LLM_WIKI_API，默认 http://127.0.0.1:5000
```

跨 Docker（如 QwenPaw 容器访问宿主机）：`http://host.docker.internal:5000` 或 `http://<宿主机局域网IP>:5000`。

## 用法

在仓库根目录执行：

```bash
# 列出知识库
python skills/llm-wiki-upload/scripts/upload.py --list-kbs

# 按 ID 上传
python skills/llm-wiki-upload/scripts/upload.py --kb-id 1 --file /path/to/doc.md

# 多文件；仅最后一次触发增量更新
python skills/llm-wiki-upload/scripts/upload.py --kb-id 1 --file a.pdf --file b.docx --update

# 按名称上传（不存在则创建）
python skills/llm-wiki-upload/scripts/upload.py --kb-name wiki --file /path/to/doc.md
```

PowerShell：

```powershell
$env:LLM_WIKI_API = "http://127.0.0.1:5000"
python skills/llm-wiki-upload/scripts/upload.py --kb-id 1 --file C:\docs\a.md
```

等价 curl（单文件）：

```bash
curl -X POST "$LLM_WIKI_API/api/kbs/<kb_id>/upload-file?update=false" \
  -F "file=@/path/to/doc.md"
```

## 规则

1. 路径必须是 **运行脚本的机器** 上可读的本地路径，不是 MCP 容器内路径。
2. 仅在用户要求「上传后增量构建」时加 `--update`。
3. `/upload-file` 支持 ZIP（`-F file=@archive.zip`）。
4. 不知道 `kb_id` 时先 `--list-kbs`，或用 `--kb-name`。
5. 日常上传 **不要** 把文件体塞进 MCP `content_base64`。

## 上传之后

- 可选构建：MCP `build_knowledge`，或带 `--update` 的本脚本
- 查询：MCP `query_knowledge` 或前端对话

接口细节见 [reference.md](reference.md)。
