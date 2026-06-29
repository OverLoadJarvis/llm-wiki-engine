# LLM Wiki Engine API 接口文档

> 本文档基于 CodeGraph 对 `server/api_server.py` 的完整扫描生成，所有接口说明均附真实代码证据来源。

---

## 一、静态页面

### 1. 首页

| 属性 | 值 |
|------|-----|
| **URL** | `/` |
| **方法** | GET |
| **说明** | 提供 Web 前端页面（Docker 环境用构建产物，开发环境用源码目录） |
| **响应** | `text/html` — index.html |
| **证据** | [api_server.py:57-62](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L57-L62) |

```python
@app.route("/")
def index():
    """提供 web 前端页面。"""
```

### 2. UI 前端

| 属性 | 值 |
|------|-----|
| **URL** | `/ui/` 或 `/ui/<path:filename>` |
| **方法** | GET |
| **说明** | 提供 ui-apple 前端页面 |
| **路径参数** | `filename` (str, 可选) — 默认 `"index.html"` |
| **响应** | `text/html` — 对应静态文件 |
| **证据** | [api_server.py:65-71](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L65-L71) |

```python
@app.route("/ui/")
@app.route("/ui/<path:filename>")
def ui_frontend(filename="index.html"):
    """提供 ui 前端页面（端口 5174 的开发版 → /ui/ 路径）。"""
```

---

## 二、知识库 API

### 3. 列出所有知识库

| 属性 | 值 |
|------|-----|
| **URL** | `/api/kbs` |
| **方法** | GET |
| **说明** | 列出所有知识库 |
| **响应** | `200` — 知识库列表数组，每个包含 `id`, `name`, `description`, `created_at`, `updated_at` 等字段 |
| **证据** | [api_server.py:76-90](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L76-L90) |

```python
@app.route("/api/kbs", methods=["GET"])
def list_kbs():
    """列出所有知识库。"""
```

### 4. 创建知识库

| 属性 | 值 |
|------|-----|
| **URL** | `/api/kbs` |
| **方法** | POST |
| **说明** | 创建新知识库 |
| **请求体 (JSON)** | `name` (str, 可选, 默认 `"Untitled"`) — 知识库名称<br>`description` (str, 可选, 默认 `""`) — 知识库描述 |
| **响应** | `201` — `{"id": <知识库ID>, "name": "<知识库名称>"}` |
| **证据** | [api_server.py:93-114](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L93-L114) |

```python
@app.route("/api/kbs", methods=["POST"])
def create_kb():
    """创建新知识库。"""
    data = request.get_json(force=True)
    name = data.get("name", "Untitled")
    desc = data.get("description", "")
```

### 5. 获取知识库详情

| 属性 | 值 |
|------|-----|
| **URL** | `/api/kbs/<kb_id>` |
| **方法** | GET |
| **说明** | 获取单个知识库详情 |
| **路径参数** | `kb_id` (int) — 知识库 ID |
| **响应** | `200` — 知识库详情对象<br>`404` — `{"error": "知识库不存在"}` |
| **证据** | [api_server.py:117-137](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L117-L137) |

```python
@app.route("/api/kbs/<int:kb_id>", methods=["GET"])
def get_kb(kb_id):
    """获取单个知识库详情。"""
```

### 6. 删除知识库

| 属性 | 值 |
|------|-----|
| **URL** | `/api/kbs/<kb_id>` |
| **方法** | DELETE |
| **说明** | 删除知识库及其所有关联数据 |
| **路径参数** | `kb_id` (int) — 知识库 ID |
| **响应** | `200` — `{"deleted": true/false}` |
| **证据** | [api_server.py:140-157](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L140-L157) |

```python
@app.route("/api/kbs/<int:kb_id>", methods=["DELETE"])
def delete_kb(kb_id):
    """删除知识库及其所有关联数据。"""
```

### 7. 获取知识库统计

| 属性 | 值 |
|------|-----|
| **URL** | `/api/kbs/<kb_id>/stats` |
| **方法** | GET |
| **说明** | 获取知识库统计信息 |
| **路径参数** | `kb_id` (int) — 知识库 ID |
| **响应** | `200` — 统计对象，包含文件数、各类别文件数量等 |
| **证据** | [api_server.py:160-177](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L160-L177) |

```python
@app.route("/api/kbs/<int:kb_id>/stats", methods=["GET"])
def kb_stats(kb_id):
    """获取知识库统计信息。"""
```

---

## 三、构建指令 API

### 8. 获取构建指令

| 属性 | 值 |
|------|-----|
| **URL** | `/api/kbs/<kb_id>/instruction` |
| **方法** | GET |
| **说明** | 获取知识库构建指令 |
| **路径参数** | `kb_id` (int) — 知识库 ID |
| **响应** | `200` — `{"instruction": "<指令文本>"}` |
| **证据** | [api_server.py:182-193](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L182-L193) |

```python
@app.route("/api/kbs/<int:kb_id>/instruction", methods=["GET"])
def get_instruction(kb_id):
    """获取知识库构建指令。"""
```

### 9. 更新构建指令

| 属性 | 值 |
|------|-----|
| **URL** | `/api/kbs/<kb_id>/instruction` |
| **方法** | PUT |
| **说明** | 更新知识库构建指令 |
| **路径参数** | `kb_id` (int) — 知识库 ID |
| **请求体 (JSON)** | `instruction` (str) — 新的构建指令文本 |
| **响应** | `200` — `{"instruction": "<指令文本>"}`<br>`404` — `{"error": "知识库不存在"}` |
| **证据** | [api_server.py:196-213](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L196-L213) |

```python
@app.route("/api/kbs/<int:kb_id>/instruction", methods=["PUT"])
def set_instruction(kb_id):
    """更新知识库构建指令。"""
```

---

## 四、文件 API

### 10. 获取文件目录树

| 属性 | 值 |
|------|-----|
| **URL** | `/api/kbs/<kb_id>/tree` |
| **方法** | GET |
| **说明** | 获取知识库的文件目录树结构 |
| **路径参数** | `kb_id` (int) — 知识库 ID |
| **响应** | `200` — 嵌套的目录树结构（JSON 树形对象） |
| **证据** | [api_server.py:218-235](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L218-L235) |

```python
@app.route("/api/kbs/<int:kb_id>/tree", methods=["GET"])
def get_tree(kb_id):
    """获取知识库的文件目录树结构。"""
```

### 11. 列出文件

| 属性 | 值 |
|------|-----|
| **URL** | `/api/kbs/<kb_id>/files` |
| **方法** | GET |
| **说明** | 列出知识库中的文件，支持目录前缀过滤 |
| **路径参数** | `kb_id` (int) — 知识库 ID |
| **查询参数** | `prefix` (str, 可选) — 目录前缀过滤，如 `"wiki/"` 或 `"graph/"` |
| **响应** | `200` — 文件列表数组，每个包含 `id`, `relative_path`, `file_name`, `file_size` 等字段 |
| **证据** | [api_server.py:240-261](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L240-L261) |

```python
@app.route("/api/kbs/<int:kb_id>/files", methods=["GET"])
def list_files(kb_id):
    """列出知识库中的文件。"""
    prefix = request.args.get("prefix", "")
```

### 12. 获取文件内容

| 属性 | 值 |
|------|-----|
| **URL** | `/api/kbs/<kb_id>/files/<path:rel_path>` |
| **方法** | GET |
| **说明** | 获取指定文件的内容 |
| **路径参数** | `kb_id` (int) — 知识库 ID<br>`rel_path` (str) — 文件相对路径，如 `"wiki/index.md"` |
| **响应** | `200` — 文件文本内容（`text/plain; charset=utf-8`）<br>`404` — `{"error": "文件不存在或内容为空"}` |
| **证据** | [api_server.py:266-287](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L266-L287) |

```python
@app.route("/api/kbs/<int:kb_id>/files/<path:rel_path>", methods=["GET"])
def get_file_content(kb_id, rel_path):
    """获取指定文件的内容。"""
```

### 13. 更新文件内容

| 属性 | 值 |
|------|-----|
| **URL** | `/api/kbs/<kb_id>/files/<path:rel_path>` |
| **方法** | PUT |
| **说明** | 更新指定文件的内容 |
| **路径参数** | `kb_id` (int) — 知识库 ID<br>`rel_path` (str) — 文件相对路径，如 `"wiki/index.md"` |
| **请求体 (JSON)** | `content` (str, 必填) — 新的文件内容 |
| **响应** | `200` — `{"ok": true}`<br>`400` — `{"error": "缺少 content 字段"}`<br>`404` — `{"error": "文件不存在"}` |
| **证据** | [api_server.py:290-319](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L290-L319) |

```python
@app.route("/api/kbs/<int:kb_id>/files/<path:rel_path>", methods=["PUT"])
def update_file_content(kb_id, rel_path):
    """更新指定文件的内容。"""
```

---

## 五、知识图谱 API

### 14. 获取知识图谱数据

| 属性 | 值 |
|------|-----|
| **URL** | `/api/kbs/<kb_id>/graph` |
| **方法** | GET |
| **说明** | 获取知识图谱 JSON 数据 |
| **路径参数** | `kb_id` (int) — 知识库 ID |
| **查询参数** | `file` (str, 可选, 默认 `"graph/graph.json"`) — 图谱文件路径 |
| **响应** | `200` — 知识图谱 JSON 数据（包含 `nodes` 和 `edges`）<br>`404` — `{"error": "图谱数据不存在"}`<br>`500` — `{"error": "图谱文件内容不是合法的 JSON: ..."}` |
| **证据** | [api_server.py:324-352](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L324-L352) |

```python
@app.route("/api/kbs/<int:kb_id>/graph", methods=["GET"])
def get_graph(kb_id):
    """获取知识图谱数据。"""
    graph_file = request.args.get("file", "graph/graph.json")
```

### 15. 列出图谱文件

| 属性 | 值 |
|------|-----|
| **URL** | `/api/kbs/<kb_id>/graph/files` |
| **方法** | GET |
| **说明** | 列出图谱目录下的所有文件 |
| **路径参数** | `kb_id` (int) — 知识库 ID |
| **响应** | `200` — `graph/` 目录下的文件列表 |
| **证据** | [api_server.py:355-372](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L355-L372) |

```python
@app.route("/api/kbs/<int:kb_id>/graph/files", methods=["GET"])
def list_graph_files(kb_id):
    """列出图谱目录下的所有文件。"""
```

---

## 六、搜索 API

### 16. 全文搜索

| 属性 | 值 |
|------|-----|
| **URL** | `/api/kbs/<kb_id>/search` |
| **方法** | GET |
| **说明** | 全文搜索文件（基于 SQLite FTS5） |
| **路径参数** | `kb_id` (int) — 知识库 ID |
| **查询参数** | `q` (str) — 搜索关键词 |
| **响应** | `200` — 搜索结果列表，包含匹配的文件路径和内容片段<br>空关键词时返回 `[]` |
| **证据** | [api_server.py:377-400](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L377-L400) |

```python
@app.route("/api/kbs/<int:kb_id>/search", methods=["GET"])
def search_files(kb_id):
    """全文搜索文件。"""
    keyword = request.args.get("q", "")
```

---

## 七、引擎工作流 API

### 17. 构建知识库

| 属性 | 值 |
|------|-----|
| **URL** | `/api/kbs/<kb_id>/build` |
| **方法** | POST |
| **说明** | 构建知识库（完整流程：解析、索引、生成图谱等）。不会构建隐式边。构建前将状态设为 `building`，完成后设为 `completed`；异常时恢复为 `unbuilt` |
| **路径参数** | `kb_id` (int) — 知识库 ID |
| **响应** | `200` — 构建结果对象 |
| **证据** | [api_server.py:405-445](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L405-L445) |

```python
@app.route("/api/kbs/<int:kb_id>/build", methods=["POST"])
def build_knowledge_base(kb_id):
    """构建知识库（完整流程：解析、索引、生成图谱等）。不会构建隐式边"""
```

### 18. 增量更新知识库

| 属性 | 值 |
|------|-----|
| **URL** | `/api/kbs/<kb_id>/update` |
| **方法** | POST |
| **说明** | 增量更新知识库。若提供 `source_dir`，先导入新文件再增量摄入。构建前状态设为 `building`，完成后设为 `completed`；异常时恢复为 `unbuilt` |
| **路径参数** | `kb_id` (int) — 知识库 ID |
| **请求体 (JSON, 可选)** | `source_dir` (str, 可选) — 源文件目录路径 |
| **响应** | `200` — 更新结果对象，`status` 可能为 `"up_to_date"` 或 `"completed"` |
| **证据** | [api_server.py:448-494](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L448-L494) |

```python
@app.route("/api/kbs/<int:kb_id>/update", methods=["POST"])
def update_knowledge_base(kb_id):
    """增量更新知识库。"""
    data = request.get_json(silent=True) or {}
    source_dir = data.get("source_dir")
```

### 19. 查询知识库

| 属性 | 值 |
|------|-----|
| **URL** | `/api/kbs/<kb_id>/query` |
| **方法** | POST |
| **说明** | 向知识库提问，支持流式和非流式两种模式 |
| **路径参数** | `kb_id` (int) — 知识库 ID |
| **请求体 (JSON)** | `question` (str) — 用户问题<br>`stream` (bool, 可选, 默认 `false`) — 是否启用 SSE 流式输出 |
| **响应** | 非流式 `200` — `{"answer": "<LLM 生成的回答>"}`<br>流式 `200` — `text/event-stream` (SSE)，每块 `data: {"chunk": "..."}`，结束 `data: {"done": true}` |
| **证据** | [api_server.py:497-543](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L497-L543) |

```python
@app.route("/api/kbs/<int:kb_id>/query", methods=["POST"])
def query_knowledge_base(kb_id):
    """向知识库提问。"""
    data = request.get_json(force=True)
    question = data.get("question", "")
    stream = data.get("stream", False)
```

### 20. 健康检查

| 属性 | 值 |
|------|-----|
| **URL** | `/api/kbs/<kb_id>/health` |
| **方法** | GET |
| **说明** | 检查知识库健康状态（缺失实体、孤立节点等），纯结构检查，零 LLM 调用 |
| **路径参数** | `kb_id` (int) — 知识库 ID |
| **响应** | `200` — 健康检查结果对象 |
| **证据** | [api_server.py:546-563](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L546-L563) |

```python
@app.route("/api/kbs/<int:kb_id>/health", methods=["GET"])
def health_check(kb_id):
    """检查知识库健康状态（缺失实体、孤立节点等）。"""
```

### 21. 内容质量检查

| 属性 | 值 |
|------|-----|
| **URL** | `/api/kbs/<kb_id>/lint` |
| **方法** | POST |
| **说明** | 对知识库进行内容质量检查，含 LLM 语义分析，结果保存到 `wiki/lint-report.md` |
| **路径参数** | `kb_id` (int) — 知识库 ID |
| **响应** | `200` — `{"report": "<检查报告文本>"}` |
| **证据** | [api_server.py:566-583](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L566-L583) |

```python
@app.route("/api/kbs/<int:kb_id>/lint", methods=["POST"])
def lint_kb(kb_id):
    """对知识库进行代码风格/结构检查。"""
```

### 22. 构建知识图谱

| 属性 | 值 |
|------|-----|
| **URL** | `/api/kbs/<kb_id>/graph/build` |
| **方法** | POST |
| **说明** | 构建/重建知识图谱。会构建隐式边（INFERRED / AMBIGUOUS） |
| **路径参数** | `kb_id` (int) — 知识库 ID |
| **响应** | `200` — 图谱构建结果对象 |
| **证据** | [api_server.py:586-603](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L586-L603) |

```python
@app.route("/api/kbs/<int:kb_id>/graph/build", methods=["POST"])
def build_graph(kb_id):
    """构建/重建知识图谱。构建会构建隐式边（INFERRED / AMBIGUOUS）。"""
```

---

## 八、文件导入导出 API

### 23. 从本地目录导入

| 属性 | 值 |
|------|-----|
| **URL** | `/api/kbs/<kb_id>/import` |
| **方法** | POST |
| **说明** | 从本地目录导入文件到知识库，自动转换格式 |
| **路径参数** | `kb_id` (int) — 知识库 ID |
| **请求体 (JSON)** | `source_dir` (str, 必填) — 源文件目录的绝对或相对路径 |
| **响应** | `200` — `{"imported": <成功数>, "skipped": <跳过数>, "errors": <错误数>}`<br>`400` — `{"error": "缺少 source_dir 参数"}` |
| **证据** | [api_server.py:608-633](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L608-L633) |

```python
@app.route("/api/kbs/<int:kb_id>/import", methods=["POST"])
def import_files(kb_id):
    """从本地目录导入文件到知识库。"""
```

### 24. 上传 ZIP 导入

| 属性 | 值 |
|------|-----|
| **URL** | `/api/kbs/<kb_id>/import-zip` |
| **方法** | POST |
| **说明** | 上传 ZIP 压缩包并导入到知识库。解压到 `uploads/<kb_name>/` 目录后导入 |
| **路径参数** | `kb_id` (int) — 知识库 ID |
| **请求体** | `multipart/form-data` — `file` (file, 必填) — ZIP 压缩包 |
| **响应** | `200` — `{"imported": N, "skipped": N, "errors": N}`<br>`400` — `{"error": "未提供文件"}` 或 `{"error": "仅支持 .zip 格式的压缩包"}`<br>`404` — `{"error": "知识库不存在"}` |
| **证据** | [api_server.py:636-699](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L636-L699) |

```python
@app.route("/api/kbs/<int:kb_id>/import-zip", methods=["POST"])
def import_zip(kb_id):
    """上传 ZIP 压缩包并导入到知识库。"""
```

### 25. 导出知识库为 ZIP

| 属性 | 值 |
|------|-----|
| **URL** | `/api/kbs/<kb_id>/export` |
| **方法** | GET |
| **说明** | 导出知识库为 ZIP 压缩包下载，包含 `raw/`、`wiki/`、`graph/` 三个目录 |
| **路径参数** | `kb_id` (int) — 知识库 ID |
| **响应** | `200` — ZIP 文件流（`Content-Type: application/zip`）<br>`404` — `{"error": "知识库不存在"}` 或 `{"error": "知识库没有可导出的文件"}` |
| **证据** | [api_server.py:702-767](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L702-L767) |

```python
@app.route("/api/kbs/<int:kb_id>/export", methods=["GET"])
def export_kb(kb_id):
    """导出知识库为 ZIP 压缩包。"""
```

### 26. 导入知识库 ZIP 包

| 属性 | 值 |
|------|-----|
| **URL** | `/api/kbs/import` |
| **方法** | POST |
| **说明** | 导入知识库 ZIP 包恢复完整知识库。以 ZIP 文件名（不含扩展名）作为知识库名称，将 ZIP 内所有文件直接写入数据库，不触发构建 |
| **请求体** | `multipart/form-data` — `file` (file, 必填) — 知识库 ZIP 压缩包 |
| **响应** | `201` — `{"kb_id": <ID>, "kb_name": "<名称>", "file_count": <N>}`<br>`400` — `{"error": "未提供文件"}` 或 `{"error": "仅支持 .zip 格式的压缩包"}`<br>`409` — `{"error": "知识库 \"<name>\" 已存在"}` |
| **证据** | [api_server.py:770-837](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L770-L837) |

```python
@app.route("/api/kbs/import", methods=["POST"])
def import_kb():
    """导入知识库 ZIP 包，恢复完整知识库。"""
```

### 27. 上传文件到知识库

| 属性 | 值 |
|------|-----|
| **URL** | `/api/kbs/<kb_id>/upload-file` |
| **方法** | POST |
| **说明** | 向指定知识库上传文件，支持单文件或 ZIP 压缩包。可选在上传后增量更新知识库 |
| **路径参数** | `kb_id` (int) — 知识库 ID |
| **查询参数** | `update` (bool, 可选, 默认 `false`) — 是否在上传后增量更新知识库 |
| **请求体** | `multipart/form-data` — `file` (file, 必填) — 单个文件或 .zip 压缩包 |
| **响应** | `200` — `{"file_name": "<文件名>", "import_result": {...}, "file_count": N, "update_result": <更新结果或null>}`<br>`400` — `{"error": "未提供文件"}`<br>`404` — `{"error": "知识库不存在"}` |
| **证据** | [api_server.py:840-934](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L840-L934) |

```python
@app.route("/api/kbs/<int:kb_id>/upload-file", methods=["POST"])
def upload_file_to_kb(kb_id):
    """外部系统向指定知识库上传文件，支持单文件或 ZIP 压缩包，并可选择增量更新知识库。"""
```

### 28. 外部系统上传

| 属性 | 值 |
|------|-----|
| **URL** | `/api/external/upload` |
| **方法** | POST |
| **说明** | 外部系统上传文件到 Wiki 引擎。按知识库名称查找或自动创建知识库，导入完成后清理本地临时文件 |
| **请求体** | `multipart/form-data`<br>`kb_name` (str, 必填) — 知识库名称<br>`files` (file[], 必填) — 一个或多个文件 |
| **响应** | `200` — `{"kb_id": <ID>, "kb_name": "<名称>", "upload_dir": "<路径>", "files": ["file1", ...], "import_result": {"imported": N, "skipped": N, "errors": N}}`<br>`400` — `{"error": "缺少 kb_name 参数"}` 或 `{"error": "未提供任何文件"}` 或 `{"error": "没有有效的文件被保存"}` |
| **证据** | [api_server.py:939-1013](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L939-L1013) |

```python
@app.route("/api/external/upload", methods=["POST"])
def external_upload():
    """外部系统上传文件到 Wiki 引擎。"""
```

---

## 九、MCP Server 工具

MCP Server 以 Streamable HTTP 方式运行，默认端口 `8081`，端点 `http://localhost:8081/mcp`。以下工具供 AI 客户端（Claude Code、Cursor、Trae 等）调用。

### MCP-1. list_kbs

| 属性 | 值 |
|------|-----|
| **工具名** | `list_kbs` |
| **说明** | 列出所有知识库，返回每个知识库的 ID、名称、状态（unbuilt/building/completed）和统计信息 |
| **参数** | 无 |
| **返回** | `{"kbs": [...], "total": N}` |
| **证据** | [api_server.py:1038-1046](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L1038-L1046) |

```python
@mcp.tool()
def list_kbs() -> dict:
    """列出所有知识库，返回每个知识库的 ID、名称、状态（unbuilt/building/completed）和统计信息。"""
```

### MCP-2. create_kb

| 属性 | 值 |
|------|-----|
| **工具名** | `create_kb` |
| **说明** | 创建一个空知识库（不导入文件） |
| **参数** | `name` (str, 可选, 默认 `"Untitled"`) — 知识库名称<br>`description` (str, 可选, 默认 `""`) — 知识库描述 |
| **返回** | `{"kb_id": <ID>, "name": "<名称>", "message": "知识库创建成功"}` |
| **证据** | [api_server.py:1049-1062](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L1049-L1062) |

```python
@mcp.tool()
def create_kb(name: str = "Untitled", description: str = "") -> dict:
    """创建一个空知识库（不导入文件）。"""
```

### MCP-3. import_kb

| 属性 | 值 |
|------|-----|
| **工具名** | `import_kb` |
| **说明** | 从 ZIP 压缩包创建知识库并导入所有文件。支持三种输入方式：`zip_url`（远程 URL）、`content_base64`（Base64 编码）、`file_path`（本地路径）。ZIP 顶层需包含 `raw/`、`wiki/`、`graph/` 中至少一个目录 |
| **参数** | `zip_url` (str, 可选) — 远程 ZIP 文件 URL（优先使用）<br>`content_base64` (str, 可选) — ZIP 文件的 Base64 编码内容<br>`file_path` (str, 可选) — 本地 ZIP 文件绝对路径<br>`kb_name` (str, 可选) — 知识库名称（使用 content_base64 时必填；zip_url 时默认取文件名） |
| **返回** | `{"kb_id": <ID>, "kb_name": "<名称>", "raw_imported": N, "wiki_imported": N, "graph_imported": N, "skipped": N, "errors": N, "state": "<completed|unbuilt>"}` |
| **证据** | [api_server.py:1065-1232](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L1065-L1232) |

```python
@mcp.tool()
def import_kb(zip_url: str = "", content_base64: str = "", file_path: str = "", kb_name: str = "") -> dict:
    """从 ZIP 压缩包创建知识库并导入所有文件。"""
```

### MCP-4. export_kb

| 属性 | 值 |
|------|-----|
| **工具名** | `export_kb` |
| **说明** | 导出知识库为 ZIP 压缩包，返回 Base64 编码的 ZIP 内容。包含 `raw/`、`wiki/`、`graph/` 三个目录 |
| **参数** | `kb_id` (int) — 知识库 ID |
| **返回** | `{"kb_id": <ID>, "kb_name": "<名称>", "file_count": N, "content_base64": "<Base64>", "format": "zip", "encoding": "base64"}` |
| **证据** | [api_server.py:1235-1280](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L1235-L1280) |

```python
@mcp.tool()
def export_kb(kb_id: int) -> dict:
    """导出知识库为 ZIP 压缩包，返回 Base64 编码的 ZIP 内容。"""
```

### MCP-5. delete_kb

| 属性 | 值 |
|------|-----|
| **工具名** | `delete_kb` |
| **说明** | 删除知识库及其所有缓存数据。此操作不可逆，需显式确认 |
| **参数** | `kb_id` (int) — 知识库 ID<br>`confirm` (bool, 必填) — 必须设置为 `true` 才能执行删除 |
| **返回** | `{"deleted": true, "kb_id": <ID>, "kb_name": "<名称>"}`<br>未确认时 `{"error": "删除操作需要确认", "kb_id": <ID>, "hint": "请设置 confirm=true 后重试"}` |
| **证据** | [api_server.py:1283-1312](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L1283-L1312) |

```python
@mcp.tool()
def delete_kb(kb_id: int, confirm: bool = False) -> dict:
    """删除知识库及其所有缓存数据。此操作不可逆。"""
```

### MCP-6. build_knowledge

| 属性 | 值 |
|------|-----|
| **工具名** | `build_knowledge` |
| **说明** | 构建或增量更新知识库。流程：获取 raw 文件 → LLM 摄入生成 wiki 页面 → 构建知识图谱 |
| **参数** | `kb_id` (int) — 知识库 ID<br>`instruction` (str, 可选, 默认 `""`) — 用户自定义构建指令，传入后更新知识库构建指令<br>`incremental` (bool, 可选, 默认 `false`) — 是否增量更新，`true` 时仅处理新增/变更的 raw 文件 |
| **返回** | `{"kb_id": <ID>, "state": "completed", "result": {...}}`<br>异常时 `{"kb_id": <ID>, "state": "unbuilt", "error": "..."}` |
| **证据** | [api_server.py:1317-1369](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L1317-L1369) |

```python
@mcp.tool()
def build_knowledge(kb_id: int, instruction: str = "", incremental: bool = False) -> dict:
    """构建或增量更新知识库。"""
```

### MCP-7. upload_files

| 属性 | 值 |
|------|-----|
| **工具名** | `upload_files` |
| **说明** | 向已有知识库追加文件。支持单文件或 ZIP 压缩包。支持两种输入方式：`file_path`（本地路径）或 `content_base64` + `file_name`（Base64 编码） |
| **参数** | `kb_id` (int) — 目标知识库 ID<br>`file_path` (str, 可选) — 本地文件或 ZIP 包的绝对路径<br>`content_base64` (str, 可选) — 文件内容的 Base64 编码<br>`file_name` (str, 可选) — 文件名（使用 content_base64 时必填）<br>`auto_update` (bool, 可选, 默认 `false`) — 上传后是否自动增量更新知识库 |
| **返回** | `{"kb_id": <ID>, "file_name": "<名称>", "imported": N, "skipped": N, "errors": N, "update_result": {...}, "state": "completed"}` |
| **证据** | [api_server.py:1372-1491](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L1372-L1491) |

```python
@mcp.tool()
def upload_files(kb_id: int, file_path: str = "", content_base64: str = "", file_name: str = "", auto_update: bool = False) -> dict:
    """向已有知识库追加文件。支持单文件或 ZIP 压缩包。"""
```

### MCP-8. query_knowledge

| 属性 | 值 |
|------|-----|
| **工具名** | `query_knowledge` |
| **说明** | 向已编译的知识库提出自然语言问题，返回 LLM 生成的回答 |
| **参数** | `kb_id` (int) — 知识库 ID<br>`question` (str) — 要查询的自然语言问题 |
| **返回** | `{"kb_id": <ID>, "question": "<问题>", "answer": "<LLM 回答>"}`<br>异常时 `{"kb_id": <ID>, "question": "<问题>", "error": "..."}` |
| **证据** | [api_server.py:1496-1519](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L1496-L1519) |

```python
@mcp.tool()
def query_knowledge(kb_id: int, question: str) -> dict:
    """向已编译的知识库提出自然语言问题，返回 LLM 生成的回答。"""
```

### MCP-9. search_files

| 属性 | 值 |
|------|-----|
| **工具名** | `search_files` |
| **说明** | 在知识库文件中进行全文搜索（基于 SQLite FTS5），返回匹配的文件路径和内容片段 |
| **参数** | `kb_id` (int) — 知识库 ID<br>`keyword` (str) — 搜索关键词 |
| **返回** | `{"kb_id": <ID>, "keyword": "<关键词>", "total": N, "results": [...]}` |
| **证据** | [api_server.py:1522-1543](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L1522-L1543) |

```python
@mcp.tool()
def search_files(kb_id: int, keyword: str) -> dict:
    """在知识库文件中进行全文搜索，返回匹配的文件路径和内容片段。"""
```

### MCP-10. read_wiki_file

| 属性 | 值 |
|------|-----|
| **工具名** | `read_wiki_file` |
| **说明** | 读取知识库中指定路径的文件全文内容 |
| **参数** | `kb_id` (int) — 知识库 ID<br>`relative_path` (str) — 文件相对路径，如 `"wiki/index.md"`、`"wiki/sources/database.md"` |
| **返回** | `{"kb_id": <ID>, "relative_path": "<路径>", "content": "<文件内容>"}`<br>`{"error": "知识库不存在", "kb_id": <ID>}`<br>`{"error": "文件不存在或内容为空", ...}` |
| **证据** | [api_server.py:1546-1574](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L1546-L1574) |

```python
@mcp.tool()
def read_wiki_file(kb_id: int, relative_path: str) -> dict:
    """读取知识库中指定路径的文件全文内容。"""
```

---

## 附录：接口总览

| # | 方法 | URL | 说明 | 证据 |
|---|------|-----|------|------|
| 1 | GET | `/` | 首页 | [api_server.py:57](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L57) |
| 2 | GET | `/ui/` `/ui/<path>` | UI 前端 | [api_server.py:65](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L65) |
| 3 | GET | `/api/kbs` | 列出所有知识库 | [api_server.py:76](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L76) |
| 4 | POST | `/api/kbs` | 创建知识库 | [api_server.py:93](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L93) |
| 5 | GET | `/api/kbs/<kb_id>` | 获取知识库详情 | [api_server.py:117](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L117) |
| 6 | DELETE | `/api/kbs/<kb_id>` | 删除知识库 | [api_server.py:140](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L140) |
| 7 | GET | `/api/kbs/<kb_id>/stats` | 知识库统计 | [api_server.py:160](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L160) |
| 8 | GET | `/api/kbs/<kb_id>/instruction` | 获取构建指令 | [api_server.py:182](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L182) |
| 9 | PUT | `/api/kbs/<kb_id>/instruction` | 更新构建指令 | [api_server.py:196](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L196) |
| 10 | GET | `/api/kbs/<kb_id>/tree` | 文件目录树 | [api_server.py:218](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L218) |
| 11 | GET | `/api/kbs/<kb_id>/files` | 列出文件 | [api_server.py:240](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L240) |
| 12 | GET | `/api/kbs/<kb_id>/files/<path>` | 获取文件内容 | [api_server.py:266](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L266) |
| 13 | PUT | `/api/kbs/<kb_id>/files/<path>` | 更新文件内容 | [api_server.py:290](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L290) |
| 14 | GET | `/api/kbs/<kb_id>/graph` | 获取知识图谱 | [api_server.py:324](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L324) |
| 15 | GET | `/api/kbs/<kb_id>/graph/files` | 列出图谱文件 | [api_server.py:355](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L355) |
| 16 | GET | `/api/kbs/<kb_id>/search` | 全文搜索 | [api_server.py:377](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L377) |
| 17 | POST | `/api/kbs/<kb_id>/build` | 构建知识库 | [api_server.py:405](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L405) |
| 18 | POST | `/api/kbs/<kb_id>/update` | 增量更新知识库 | [api_server.py:448](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L448) |
| 19 | POST | `/api/kbs/<kb_id>/query` | 查询知识库 | [api_server.py:497](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L497) |
| 20 | GET | `/api/kbs/<kb_id>/health` | 健康检查 | [api_server.py:546](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L546) |
| 21 | POST | `/api/kbs/<kb_id>/lint` | 内容质量检查 | [api_server.py:566](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L566) |
| 22 | POST | `/api/kbs/<kb_id>/graph/build` | 构建知识图谱 | [api_server.py:586](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L586) |
| 23 | POST | `/api/kbs/<kb_id>/import` | 从本地目录导入 | [api_server.py:608](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L608) |
| 24 | POST | `/api/kbs/<kb_id>/import-zip` | 上传 ZIP 导入 | [api_server.py:636](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L636) |
| 25 | GET | `/api/kbs/<kb_id>/export` | 导出知识库为 ZIP | [api_server.py:702](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L702) |
| 26 | POST | `/api/kbs/import` | 导入知识库 ZIP 包 | [api_server.py:770](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L770) |
| 27 | POST | `/api/kbs/<kb_id>/upload-file` | 上传文件到知识库 | [api_server.py:840](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L840) |
| 28 | POST | `/api/external/upload` | 外部系统上传 | [api_server.py:939](file:///c:/Users/ChengCihang/VSCode/llm-wiki-engine/server/api_server.py#L939) |

共 **28 个 REST API 端点** + **10 个 MCP 工具**。