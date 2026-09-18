---
name: llm-wiki
description: >-
  通过 REST 对接 LLM Wiki Engine：知识库 CRUD、本机上传、构建/增量、查询、搜索、
  文件读写、图谱、健康检查、导入导出。
  触发词：llm-wiki、知识库 API、wiki CLI、上传知识库、对接 wiki。
---

# LLM Wiki 对接 Skill

用本目录脚本调用 LLM Wiki Engine 的 REST API。

## API 基址

```text
环境变量 LLM_WIKI_API，默认 http://127.0.0.1:5000
```

- 直连后端：`http://127.0.0.1:5000`
- Docker Compose（经 nginx）：`http://127.0.0.1:5173`
- 其他容器访问宿主机：`http://host.docker.internal:5173`

## 入口

在仓库根目录：

```bash
python skills/llm-wiki/scripts/wiki.py <command> ...
```

### 知识库

```bash
python skills/llm-wiki/scripts/wiki.py kbs list
python skills/llm-wiki/scripts/wiki.py kbs create --name demo --description "test"
python skills/llm-wiki/scripts/wiki.py kbs get --kb-id 1
python skills/llm-wiki/scripts/wiki.py kbs stats --kb-id 1
python skills/llm-wiki/scripts/wiki.py kbs delete --kb-id 1 --confirm
```

### 上传

```bash
python skills/llm-wiki/scripts/wiki.py upload --kb-id 1 --file ./doc.md
python skills/llm-wiki/scripts/wiki.py upload --kb-id 1 --file a.pdf --file b.docx --update
python skills/llm-wiki/scripts/wiki.py upload --kb-name wiki --file ./doc.md
```

`--file` 为运行脚本机器上的本地路径。`--update` 仅在 `--kb-id` 模式下，于最后一次上传后触发增量更新。

### 构建 / 增量 / 查询 / 搜索

```bash
python skills/llm-wiki/scripts/wiki.py build --kb-id 1
python skills/llm-wiki/scripts/wiki.py build --kb-id 1 --instruction "侧重技术架构"
python skills/llm-wiki/scripts/wiki.py update --kb-id 1
python skills/llm-wiki/scripts/wiki.py query --kb-id 1 --question "核心概念是什么？"
python skills/llm-wiki/scripts/wiki.py search --kb-id 1 --keyword "图谱"
```

### 文件 / 图谱 / 健康

```bash
python skills/llm-wiki/scripts/wiki.py files tree --kb-id 1
python skills/llm-wiki/scripts/wiki.py files list --kb-id 1 --prefix wiki/
python skills/llm-wiki/scripts/wiki.py files get --kb-id 1 --path wiki/index.md
python skills/llm-wiki/scripts/wiki.py files put --kb-id 1 --path wiki/index.md --file ./index.md
python skills/llm-wiki/scripts/wiki.py graph get --kb-id 1 --out graph.json
python skills/llm-wiki/scripts/wiki.py graph build --kb-id 1
python skills/llm-wiki/scripts/wiki.py health --kb-id 1
python skills/llm-wiki/scripts/wiki.py lint --kb-id 1
```

### 导入 / 导出

```bash
python skills/llm-wiki/scripts/wiki.py export --kb-id 1 --out ./kb.zip
python skills/llm-wiki/scripts/wiki.py import-kb --file ./kb.zip
python skills/llm-wiki/scripts/wiki.py import-zip --kb-id 1 --file ./extra.zip
python skills/llm-wiki/scripts/wiki.py import-dir --kb-id 1 --source-dir /path/on/server
```

`import-dir` 的 `--source-dir` 必须是 **API 进程可读** 的服务端路径。

### 构建指令

```bash
python skills/llm-wiki/scripts/wiki.py instruction get --kb-id 1
python skills/llm-wiki/scripts/wiki.py instruction set --kb-id 1 --instruction "用中文输出"
```

## 规则

1. 删除知识库必须加 `--confirm`
2. 仅在需要「上传后增量构建」时加 `--update`
3. 命令默认非流式，输出 JSON（`files get` 除外为纯文本）

接口对照见 [reference.md](reference.md)。
