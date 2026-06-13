#!/usr/bin/env python3
"""
LLM Wiki Web API — Flask 后端服务 + MCP Server
提供项目、文件树、文件内容、知识图谱等 REST API，
并附带一个 Streamable HTTP MCP 服务供 AI 客户端调用。
"""
from __future__ import annotations

import base64
import json
import os
import shutil
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any

import requests
from flask import Flask, Response, jsonify, request, send_from_directory
from flask_cors import CORS
from mcp.server.fastmcp import FastMCP

REPO_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = REPO_ROOT.parent
sys.path.insert(0, str(REPO_ROOT))

from storage.db import WikiStorage
from wiki_engine import LLMWikiEngine
from wiki_engine.constants import DEFAULT_UPLOAD_DIR

# 生产环境（Docker）使用构建产物，开发环境使用源码目录
_WEB_DIST = PROJECT_ROOT.parent / "web-dist"
_UI_DIST = PROJECT_ROOT.parent / "ui-dist"
if _WEB_DIST.exists():
    app = Flask(__name__, static_folder=str(_WEB_DIST), static_url_path="")
else:
    app = Flask(__name__, static_folder=str(PROJECT_ROOT / "web"), static_url_path="")
CORS(app)

DB_PATH = REPO_ROOT / "storage" / "wiki.db"


def get_db() -> WikiStorage:
    return WikiStorage(str(DB_PATH))


def get_engine() -> LLMWikiEngine:
    return LLMWikiEngine(str(DB_PATH))


# ── 静态页面 ──────────────────────────────────────────────────────────

@app.route("/")
def index():
    """提供 web 前端页面。"""
    if _WEB_DIST.exists():
        return send_from_directory(str(_WEB_DIST), "index.html")
    return send_from_directory(str(PROJECT_ROOT / "web"), "index.html")


@app.route("/ui/")
@app.route("/ui/<path:filename>")
def ui_frontend(filename="index.html"):
    """提供 ui 前端页面（端口 5174 的开发版 → /ui/ 路径）。"""
    if _UI_DIST.exists():
        return send_from_directory(str(_UI_DIST), filename)
    return send_from_directory(str(PROJECT_ROOT / "ui"), filename)


# ── 项目 API ──────────────────────────────────────────────────────────

@app.route("/api/projects", methods=["GET"])
def list_projects():
    """列出所有项目。

    GET /api/projects

    响应:
        200: 项目列表数组，每个项目包含 id, name, description, created_at, updated_at 等字段
    """
    db = get_db()
    try:
        projects = db.list_projects()
        return jsonify(projects)
    finally:
        db.close()


@app.route("/api/projects", methods=["POST"])
def create_project():
    """创建新项目。

    POST /api/projects

    请求体 (JSON):
        - name (str): 项目名称（可选，默认 "Untitled"）
        - description (str): 项目描述（可选，默认 ""）

    响应:
        201: {"id": <项目ID>, "name": "<项目名称>"}
    """
    data = request.get_json(force=True)
    name = data.get("name", "Untitled")
    desc = data.get("description", "")
    db = get_db()
    try:
        pid = db.create_project(name, desc)
        return jsonify({"id": pid, "name": name}), 201
    finally:
        db.close()


@app.route("/api/projects/<int:project_id>", methods=["GET"])
def get_project(project_id):
    """获取单个项目详情。

    GET /api/projects/<project_id>

    路径参数:
        - project_id (int): 项目 ID

    响应:
        200: 项目详情对象
        404: {"error": "项目不存在"}
    """
    db = get_db()
    try:
        proj = db.get_project(project_id)
        if not proj:
            return jsonify({"error": "项目不存在"}), 404
        return jsonify(proj)
    finally:
        db.close()


@app.route("/api/projects/<int:project_id>", methods=["DELETE"])
def delete_project(project_id):
    """删除项目及其所有关联数据。

    DELETE /api/projects/<project_id>

    路径参数:
        - project_id (int): 项目 ID

    响应:
        200: {"deleted": true/false}
    """
    db = get_db()
    try:
        ok = db.delete_project(project_id)
        return jsonify({"deleted": ok})
    finally:
        db.close()


@app.route("/api/projects/<int:project_id>/stats", methods=["GET"])
def project_stats(project_id):
    """获取项目统计信息。

    GET /api/projects/<project_id>/stats

    路径参数:
        - project_id (int): 项目 ID

    响应:
        200: 统计信息对象，包含文件数、各类别文件数量等
    """
    db = get_db()
    try:
        stats = db.project_stats(project_id)
        return jsonify(stats)
    finally:
        db.close()


# ── 构建指令 API ──────────────────────────────────────────────────────

@app.route("/api/projects/<int:project_id>/instruction", methods=["GET"])
def get_instruction(project_id):
    """获取项目构建指令。

    GET /api/projects/<project_id>/instruction
    """
    db = get_db()
    try:
        instruction = db.get_ingest_instruction(project_id)
        return jsonify({"instruction": instruction})
    finally:
        db.close()


@app.route("/api/projects/<int:project_id>/instruction", methods=["PUT"])
def set_instruction(project_id):
    """更新项目构建指令。

    PUT /api/projects/<project_id>/instruction
    请求体: {"instruction": "..."}
    """
    data = request.get_json(silent=True) or {}
    instruction = data.get("instruction", "")

    db = get_db()
    try:
        ok = db.set_ingest_instruction(project_id, instruction)
        if not ok:
            return jsonify({"error": "项目不存在"}), 404
        return jsonify({"instruction": instruction})
    finally:
        db.close()


# ── 文件树 API ────────────────────────────────────────────────────────

@app.route("/api/projects/<int:project_id>/tree", methods=["GET"])
def get_tree(project_id):
    """获取项目的文件目录树结构。

    GET /api/projects/<project_id>/tree

    路径参数:
        - project_id (int): 项目 ID

    响应:
        200: 嵌套的目录树结构（JSON 树形对象）
    """
    db = get_db()
    try:
        tree = db.get_directory_tree(project_id)
        return jsonify(tree)
    finally:
        db.close()


# ── 文件列表 API ──────────────────────────────────────────────────────

@app.route("/api/projects/<int:project_id>/files", methods=["GET"])
def list_files(project_id):
    """列出项目中的文件。

    GET /api/projects/<project_id>/files?prefix=<目录前缀>

    路径参数:
        - project_id (int): 项目 ID

    查询参数:
        - prefix (str, 可选): 目录前缀过滤，如 "wiki/" 或 "graph/"

    响应:
        200: 文件列表数组，每个文件包含 id, relative_path, file_name, file_size 等字段
    """
    db = get_db()
    try:
        prefix = request.args.get("prefix", "")
        files = db.list_files(project_id, prefix)
        return jsonify(files)
    finally:
        db.close()


# ── 文件内容 API ──────────────────────────────────────────────────────

@app.route("/api/projects/<int:project_id>/files/<path:rel_path>", methods=["GET"])
def get_file_content(project_id, rel_path):
    """获取指定文件的内容。

    GET /api/projects/<project_id>/files/<rel_path>

    路径参数:
        - project_id (int): 项目 ID
        - rel_path (str): 文件相对路径，如 "wiki/index.md"

    响应:
        200: 文件文本内容（text/plain）
        404: {"error": "文件不存在或内容为空"}
    """
    db = get_db()
    try:
        text = db.get_file_text_by_path(project_id, rel_path)
        if text is None:
            return jsonify({"error": "文件不存在或内容为空"}), 404
        return Response(text, mimetype="text/plain; charset=utf-8")
    finally:
        db.close()


@app.route("/api/projects/<int:project_id>/files/<path:rel_path>", methods=["PUT"])
def update_file_content(project_id, rel_path):
    """更新指定文件的内容。

    PUT /api/projects/<project_id>/files/<rel_path>

    路径参数:
        - project_id (int): 项目 ID
        - rel_path (str): 文件相对路径，如 "wiki/index.md"

    请求体 (JSON):
        - content (str): 新的文件内容

    响应:
        200: {"ok": true}
        400: {"error": "缺少 content 字段"}
        404: {"error": "文件不存在"}
    """
    data = request.get_json(force=True)
    content = data.get("content")
    if content is None:
        return jsonify({"error": "缺少 content 字段"}), 400
    db = get_db()
    try:
        ok = db.update_file_by_path(project_id, rel_path, content)
        if not ok:
            return jsonify({"error": "文件不存在"}), 404
        return jsonify({"ok": True})
    finally:
        db.close()


# ── 知识图谱 API ──────────────────────────────────────────────────────

@app.route("/api/projects/<int:project_id>/graph", methods=["GET"])
def get_graph(project_id):
    """获取知识图谱数据。

    GET /api/projects/<project_id>/graph?file=<图谱文件路径>

    路径参数:
        - project_id (int): 项目 ID

    查询参数:
        - file (str, 可选): 图谱文件路径，默认 "graph/graph.json"

    响应:
        200: 知识图谱 JSON 数据（包含 nodes 和 edges）
        404: {"error": "图谱数据不存在"}
    """
    db = get_db()
    try:
        graph_file = request.args.get("file", "graph/graph.json")
        graph_json = db.get_file_text_by_path(project_id, graph_file)
        if not graph_json:
            return jsonify({"error": "图谱数据不存在"}), 404
        try:
            data = json.loads(graph_json)
        except (json.JSONDecodeError, ValueError) as e:
            return jsonify({"error": f"图谱文件内容不是合法的 JSON: {e}"}), 500
        return jsonify(data)
    finally:
        db.close()


@app.route("/api/projects/<int:project_id>/graph/files", methods=["GET"])
def list_graph_files(project_id):
    """列出图谱目录下的所有文件。

    GET /api/projects/<project_id>/graph/files

    路径参数:
        - project_id (int): 项目 ID

    响应:
        200: graph/ 目录下的文件列表
    """
    db = get_db()
    try:
        files = db.list_files(project_id, "graph/")
        return jsonify(files)
    finally:
        db.close()


# ── 搜索 API ──────────────────────────────────────────────────────────

@app.route("/api/projects/<int:project_id>/search", methods=["GET"])
def search_files(project_id):
    """全文搜索文件。

    GET /api/projects/<project_id>/search?q=<关键词>

    路径参数:
        - project_id (int): 项目 ID

    查询参数:
        - q (str): 搜索关键词

    响应:
        200: 搜索结果列表，包含匹配的文件路径和内容片段
    """
    db = get_db()
    try:
        keyword = request.args.get("q", "")
        if not keyword:
            return jsonify([])
        results = db.search(project_id, keyword)
        return jsonify(results)
    finally:
        db.close()


# ── 引擎工作流 API ────────────────────────────────────────────────────

@app.route("/api/projects/<int:project_id>/build", methods=["POST"])
def build_knowledge_base(project_id):
    """构建知识库（完整流程：解析、索引、生成图谱等）。不会构建隐式边

    POST /api/projects/<project_id>/build

    路径参数:
        - project_id (int): 项目 ID

    行为:
        构建前将项目状态设为 building，构建完成后设为 completed。

    响应:
        200: 构建结果对象
    """
    db = get_db()
    try:
        db.set_project_state(project_id, "building")
    finally:
        db.close()

    engine = get_engine()
    try:
        result = engine.build_knowledge_base(project_id)

        db2 = get_db()
        try:
            db2.set_project_state(project_id, "completed")
        finally:
            db2.close()

        return jsonify(result)
    except Exception:
        db2 = get_db()
        try:
            db2.set_project_state(project_id, "unbuilt")
        finally:
            db2.close()
        raise
    finally:
        engine.close()


@app.route("/api/projects/<int:project_id>/update", methods=["POST"])
def update_knowledge_base(project_id):
    """增量更新知识库。

    POST /api/projects/<project_id>/update

    路径参数:
        - project_id (int): 项目 ID

    请求体 (JSON, 可选):
        - source_dir (str, 可选): 源文件目录路径，若提供则先导入新文件再增量摄入

    行为:
        更新前将项目状态设为 building，更新完成后设为 completed。

    响应:
        200: 更新结果对象，status 可能为 "up_to_date" 或 "completed"
    """
    data = request.get_json(silent=True) or {}
    source_dir = data.get("source_dir")

    db = get_db()
    try:
        db.set_project_state(project_id, "building")
    finally:
        db.close()

    engine = get_engine()
    try:
        result = engine.update_knowledge_base(project_id, source_dir)

        db2 = get_db()
        try:
            db2.set_project_state(project_id, "completed")
        finally:
            db2.close()

        return jsonify(result)
    except Exception:
        db2 = get_db()
        try:
            db2.set_project_state(project_id, "unbuilt")
        finally:
            db2.close()
        raise
    finally:
        engine.close()


@app.route("/api/projects/<int:project_id>/query", methods=["POST"])
def query_knowledge_base(project_id):
    """向知识库提问。

    POST /api/projects/<project_id>/query

    路径参数:
        - project_id (int): 项目 ID

    请求体 (JSON):
        - question (str): 用户问题

    响应:
        200: {"answer": "<LLM 生成的回答>"}
    """
    data = request.get_json(force=True)
    question = data.get("question", "")
    engine = get_engine()
    try:
        answer = engine.query(project_id, question)
        return jsonify({"answer": answer})
    finally:
        engine.close()


@app.route("/api/projects/<int:project_id>/health", methods=["GET"])
def health_check(project_id):
    """检查项目健康状态（缺失实体、孤立节点等）。

    GET /api/projects/<project_id>/health

    路径参数:
        - project_id (int): 项目 ID

    响应:
        200: 健康检查结果对象
    """
    engine = get_engine()
    try:
        result = engine.health_check(project_id)
        return jsonify(result)
    finally:
        engine.close()


@app.route("/api/projects/<int:project_id>/lint", methods=["POST"])
def lint_project(project_id):
    """对项目进行代码风格/结构检查。

    POST /api/projects/<project_id>/lint

    路径参数:
        - project_id (int): 项目 ID

    响应:
        200: {"report": "<检查报告文本>"}
    """
    engine = get_engine()
    try:
        report = engine.lint(project_id, save=True)
        return jsonify({"report": report})
    finally:
        engine.close()


@app.route("/api/projects/<int:project_id>/graph/build", methods=["POST"])
def build_graph(project_id):
    """构建/重建知识图谱。构建会构建隐式边（INFERRED / AMBIGUOUS）。

    POST /api/projects/<project_id>/graph/build

    路径参数:
        - project_id (int): 项目 ID

    响应:
        200: 图谱构建结果对象
    """
    engine = get_engine()
    try:
        result = engine.build_graph(project_id)
        return jsonify(result)
    finally:
        engine.close()


# ── 导入文件 API ──────────────────────────────────────────────────────

@app.route("/api/projects/<int:project_id>/import", methods=["POST"])
def import_files(project_id):
    """从本地目录导入文件到项目。

    POST /api/projects/<project_id>/import

    路径参数:
        - project_id (int): 项目 ID

    请求体 (JSON):
        - source_dir (str): 源文件目录的绝对或相对路径

    响应:
        200: {"imported": <成功数>, "skipped": <跳过数>, "errors": <错误数>}
        400: {"error": "缺少 source_dir 参数"}
    """
    data = request.get_json(force=True)
    source_dir = data.get("source_dir", "")
    if not source_dir:
        return jsonify({"error": "缺少 source_dir 参数"}), 400
    engine = get_engine()
    try:
        result = engine.import_raw_files(project_id, source_dir)
        return jsonify(result)
    finally:
        engine.close()


@app.route("/api/projects/<int:project_id>/import-zip", methods=["POST"])
def import_zip(project_id):
    """上传 ZIP 压缩包并导入到项目。

    POST /api/projects/<project_id>/import-zip

    路径参数:
        - project_id (int): 项目 ID

    请求体 (multipart/form-data):
        - file (file): ZIP 压缩包文件

    行为:
        1. 将 ZIP 文件保存到临时目录
        2. 解压缩到 ``uploads/<project_name>/`` 目录
        3. 将解压后的文件导入到 Wiki 引擎项目

    响应:
        200: {"imported": <成功数>, "skipped": <跳过数>, "errors": <错误数>}
        400: {"error": "..."}
        404: {"error": "项目不存在"}
    """
    import tempfile
    import zipfile

    file = request.files.get("file")
    if not file or file.filename == "":
        return jsonify({"error": "未提供文件"}), 400

    if not file.filename.lower().endswith(".zip"):
        return jsonify({"error": "仅支持 .zip 格式的压缩包"}), 400

    db = get_db()
    try:
        project = db.get_project(project_id)
        if not project:
            return jsonify({"error": "项目不存在"}), 404

        extract_dir = DEFAULT_UPLOAD_DIR / project["name"]
        extract_dir.mkdir(parents=True, exist_ok=True)

        # 将上传的 ZIP 写入临时文件，再解压
        import_result = {}
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            file.save(tmp.name)
            tmp_path = Path(tmp.name)

        try:
            with zipfile.ZipFile(str(tmp_path), "r") as zf:
                zf.extractall(str(extract_dir))

            engine = get_engine()
            try:
                print(f"Importing files from {extract_dir}")
                import_result = engine.import_raw_files(project_id, str(extract_dir))
            finally:
                engine.close()
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

        return jsonify(import_result)
    finally:
        db.close()


@app.route("/api/projects/<int:project_id>/export", methods=["GET"])
def export_project(project_id):
    """导出项目为 ZIP 压缩包。

    GET /api/projects/<project_id>/export

    路径参数:
        - project_id (int): 项目 ID

    行为:
        将项目中 raw/、wiki/、graph/ 三个目录下的所有文件打包为 ZIP 下载。

    响应:
        200: ZIP 文件流（Content-Type: application/zip）
        404: {"error": "项目不存在"}
    """
    import io
    import zipfile

    db = get_db()
    try:
        project = db.get_project(project_id)
        if not project:
            return jsonify({"error": "项目不存在"}), 404

        # 收集所有需要导出的文件
        prefixes = ("raw/", "wiki/", "graph/")
        all_files = []
        for prefix in prefixes:
            files = db.list_files(project_id, prefix)
            all_files.extend(files)

        if not all_files:
            return jsonify({"error": "项目没有可导出的文件"}), 404

        # 在内存中构建 ZIP
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in all_files:
                rel_path = f["relative_path"]
                # 直接读取二进制内容，兼容文本和非文本文件
                row = db.conn.execute(
                    "SELECT content FROM files WHERE project_id = ? AND relative_path = ?",
                    (project_id, rel_path),
                ).fetchone()
                content = row["content"] if row and row["content"] else b""
                zf.writestr(rel_path, content)

        buf.seek(0)
        from urllib.parse import quote

        project_name = project["name"]
        safe_name = f"project_{project_id}_export.zip"
        encoded_name = quote(project_name, safe="")
        return Response(
            buf,
            mimetype="application/zip",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{safe_name}"; '
                    f"filename*=UTF-8''{encoded_name}_export.zip"
                ),
            },
        )
    finally:
        db.close()


@app.route("/api/projects/import", methods=["POST"])
def import_project():
    """导入项目 ZIP 包，恢复完整项目。

    POST /api/projects/import

    请求体 (multipart/form-data):
        - file (file): 项目 ZIP 压缩包

    行为:
        1. 以 ZIP 文件名（不含扩展名）作为项目名称，创建新项目
        2. 将 ZIP 内所有文件直接写入数据库（raw/、wiki/、graph/ 等目录结构）
        3. 不触发知识库构建等引擎行为，纯数据落库

    响应:
        200: {"project_id": <ID>, "project_name": "<名称>", "file_count": <N>}
        400: {"error": "..."}
        409: {"error": "项目已存在"}
    """
    import tempfile
    import zipfile

    file = request.files.get("file")
    if not file or file.filename == "":
        return jsonify({"error": "未提供文件"}), 400

    if not file.filename.lower().endswith(".zip"):
        return jsonify({"error": "仅支持 .zip 格式的压缩包"}), 400

    # 以 ZIP 文件名（不含扩展名）作为项目名称
    project_name = Path(file.filename).stem

    db = get_db()
    try:
        # 检查项目名是否已存在
        existing = db.get_project_by_name(project_name)
        if existing:
            return jsonify({"error": f"项目 \"{project_name}\" 已存在"}), 409

        # 创建项目
        project_id = db.create_project(project_name)

        # 将 ZIP 写入临时文件
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            file.save(tmp.name)
            tmp_path = Path(tmp.name)

        try:
            with zipfile.ZipFile(str(tmp_path), "r") as zf:
                file_count = 0
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    rel_path = info.filename.replace("\\", "/")
                    content = zf.read(info.filename)
                    db.add_file(project_id, rel_path, content)
                    file_count += 1
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

        return jsonify({
            "project_id": project_id,
            "project_name": project_name,
            "file_count": file_count,
        }), 201
    finally:
        db.close()


@app.route("/api/projects/<int:project_id>/upload-file", methods=["POST"])
def upload_file_to_project(project_id):
    """外部系统向指定项目上传文件，支持单文件或 ZIP 压缩包，并可选择增量更新知识库。

    POST /api/projects/<project_id>/upload-file

    路径参数:
        - project_id (int): 项目 ID

    请求体 (multipart/form-data):
        - file (file): 单个文件或 .zip 压缩包

    查询参数:
        - update (bool, 可选): 是否在上传后增量更新知识库，默认 false

    行为:
        1. 若为 .zip 文件: 解压到临时目录，将所有文件导入到 Wiki 引擎项目
        2. 若为单文件: 保存到本地目录后导入
        3. 若 update=true，触发增量知识库更新

    响应:
        200: {"file_name": "<文件名>", "import_result": {"imported": N, "skipped": N, "errors": N},
              "file_count": <N>, "update_result": <更新结果或null>}
        400: {"error": "..."}
        404: {"error": "项目不存在"}
    """
    import tempfile
    import zipfile
    from werkzeug.utils import secure_filename

    file = request.files.get("file")
    if not file or file.filename == "":
        return jsonify({"error": "未提供文件"}), 400

    db = get_db()
    try:
        project = db.get_project(project_id)
        if not project:
            return jsonify({"error": "项目不存在"}), 404

        safe_name = secure_filename(file.filename)
        is_zip = safe_name.lower().endswith(".zip")

        upload_dir = DEFAULT_UPLOAD_DIR / project["name"]
        upload_dir.mkdir(parents=True, exist_ok=True)

        engine = get_engine()
        try:
            if is_zip:
                # ZIP 压缩包: 解压到临时目录后导入
                extract_dir = upload_dir / f"_tmp_{safe_name}"
                extract_dir.mkdir(parents=True, exist_ok=True)

                with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                    file.save(tmp.name)
                    tmp_path = Path(tmp.name)

                try:
                    with zipfile.ZipFile(str(tmp_path), "r") as zf:
                        zf.extractall(str(extract_dir))

                    import_result = engine.import_raw_files(project_id, str(extract_dir))
                    file_count = import_result.get("imported", 0)
                finally:
                    if tmp_path.exists():
                        tmp_path.unlink()
                    # 清理临时解压目录
                    if extract_dir.exists():
                        shutil.rmtree(str(extract_dir), ignore_errors=True)
            else:
                # 单文件: 直接保存后导入
                dest_path = upload_dir / safe_name
                file.save(str(dest_path))

                import_result = engine.import_raw_files(project_id, str(upload_dir))
                file_count = import_result.get("imported", 0)

                # 导入完成后清理本地临时文件
                if dest_path.exists():
                    dest_path.unlink()

            update_result = None
            if request.args.get("update", "").lower() == "true":
                update_result = engine.update_knowledge_base(project_id)

            return jsonify({
                "file_name": safe_name,
                "import_result": import_result,
                "file_count": file_count,
                "update_result": update_result,
            })
        finally:
            engine.close()
    finally:
        db.close()


# ── 外部文件上传 API ──────────────────────────────────────────────────

@app.route("/api/external/upload", methods=["POST"])
def external_upload():
    """外部系统上传文件到 Wiki 引擎。

    POST /api/external/upload

    请求体 (multipart/form-data):
        - project_name (str): 项目名称，文件将存储到 uploads/<project_name>/ 目录
        - files (file): 一个或多个文件

    行为:
        1. 将文件保存到 ``DEFAULT_UPLOAD_DIR / project_name /`` 本地目录
        2. 按项目名称查找或自动创建项目
        3. 将上传目录中的文件导入到 Wiki 引擎

    响应:
        200: {"project_id": <ID>, "project_name": "<名称>", "files": ["file1", ...],
              "import_result": {"imported": N, "skipped": N, "errors": N}}
        400: {"error": "..."}
    """
    project_name = request.form.get("project_name", "").strip()
    if not project_name:
        return jsonify({"error": "缺少 project_name 参数"}), 400

    uploaded_files = request.files.getlist("files")
    if not uploaded_files or all(f.filename == "" for f in uploaded_files):
        return jsonify({"error": "未提供任何文件"}), 400

    # 1. 保存文件到本地目录: uploads/<project_name>/
    from werkzeug.utils import secure_filename

    upload_dir = DEFAULT_UPLOAD_DIR / project_name
    upload_dir.mkdir(parents=True, exist_ok=True)

    saved_files = []
    for f in uploaded_files:
        if f.filename == "":
            continue
        safe_name = secure_filename(f.filename)
        dest_path = upload_dir / safe_name
        f.save(str(dest_path))
        saved_files.append(safe_name)

    if not saved_files:
        return jsonify({"error": "没有有效的文件被保存"}), 400

    # 2. 查找或创建项目
    db = get_db()
    try:
        project = db.get_project_by_name(project_name)
        if project:
            project_id = project["id"]
        else:
            project_id = db.create_project(project_name, f"外部上传: {project_name}")

        # 3. 导入文件到 Wiki 引擎
        engine = get_engine()
        try:
            import_result = engine.import_raw_files(project_id, str(upload_dir))
            return jsonify({
                "project_id": project_id,
                "project_name": project_name,
                "upload_dir": str(upload_dir),
                "files": saved_files,
                "import_result": import_result,
            })
        finally:
            engine.close()
            # 导入完成后清理本地临时文件
            for fname in saved_files:
                fp = upload_dir / fname
                if fp.exists():
                    fp.unlink()
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════
#  MCP Server（内嵌，与 Flask 同进程启动）
#  工具直调 LLMWikiEngine，不再通过 HTTP 中转
# ══════════════════════════════════════════════════════════════════════════

MCP_PORT = int(os.environ.get("MCP_PORT", "8081"))

mcp = FastMCP("llm-wiki-engine")


def _mcp_engine():
    """创建 MCP 工具专用的引擎实例。"""
    return LLMWikiEngine(str(DB_PATH))


def _mcp_db():
    """创建 MCP 工具专用的数据库实例。"""
    return WikiStorage(str(DB_PATH))


# ── 项目生命周期 ──────────────────────────────────────────────────────

@mcp.tool()
def list_projects() -> dict:
    """列出所有项目，返回每个项目的 ID、名称、状态（unbuilt/building/completed）和统计信息。"""
    db = _mcp_db()
    try:
        projects = db.list_projects()
        return {"projects": projects, "total": len(projects)}
    finally:
        db.close()


@mcp.tool()
def create_project(name: str = "Untitled", description: str = "") -> dict:
    """创建一个空项目（不导入文件）。

    Args:
        name: 项目名称，默认 "Untitled"
        description: 项目描述，可选
    """
    db = _mcp_db()
    try:
        pid = db.create_project(name, description)
        return {"project_id": pid, "name": name, "message": "项目创建成功"}
    finally:
        db.close()


@mcp.tool()
def import_project(
    zip_url: str = "",
    content_base64: str = "",
    file_path: str = "",
    project_name: str = "",
) -> dict:
    """从 ZIP 压缩包创建项目并导入所有文件。支持三种输入方式：

    1. zip_url       — 远程 ZIP 文件 URL（推荐，适用于远程 MCP 客户端）
    2. content_base64 — ZIP 文件的 Base64 编码内容（需配合 project_name）
    3. file_path     — 本地 ZIP 文件绝对路径（仅本地部署可用）

    ZIP 包结构（与 export_project 导出产物对应）：
        raw/   — 原始文件，导入后存入 raw/ 分类，用于后续编译
        wiki/  — 已编译的 wiki 页面，直接存入 wiki/ 分类
        graph/ — 知识图谱数据，直接存入 graph/ 分类

    若 wiki/ 或 graph/ 目录存在，导入后项目状态直接设为 completed。

    Args:
        zip_url: 远程 ZIP 文件的完整 URL（优先使用）
        content_base64: ZIP 文件的 Base64 编码内容
        file_path: 本地 ZIP 文件绝对路径
        project_name: 项目名称（使用 content_base64 时必填；zip_url 时可选，默认取文件名）
    """
    import zipfile
    import tempfile
    from urllib.parse import urlparse

    # 1. 获取 ZIP 内容到临时文件
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            tmp_path = Path(tmp.name)

            if zip_url:
                parsed = urlparse(zip_url)
                if parsed.scheme not in ("http", "https"):
                    return {"error": f"不支持的 URL 协议: {parsed.scheme}，仅支持 http/https"}
                try:
                    resp = requests.get(zip_url, timeout=120)
                    resp.raise_for_status()
                    tmp.write(resp.content)
                except requests.RequestException as e:
                    return {"error": f"下载 ZIP 失败: {e}"}
                if not project_name:
                    url_path = parsed.path.rstrip("/")
                    project_name = Path(url_path).stem if url_path else "imported"

            elif content_base64:
                if not project_name:
                    return {"error": "使用 content_base64 时必须提供 project_name"}
                tmp.write(base64.b64decode(content_base64))

            elif file_path:
                src = Path(file_path)
                if not src.exists():
                    return {"error": f"文件不存在: {file_path}"}
                if not src.suffix.lower() == ".zip":
                    return {"error": "仅支持 .zip 格式"}
                tmp.write(src.read_bytes())
                if not project_name:
                    project_name = src.stem

            else:
                return {"error": "必须提供 zip_url、content_base64 或 file_path 之一"}

            tmp.flush()

        # 2. 创建项目 + 解压 ZIP
        extract_dir = DEFAULT_UPLOAD_DIR / f"_mcp_import_{uuid.uuid4().hex[:8]}"
        extract_dir.mkdir(parents=True, exist_ok=True)

        try:
            with zipfile.ZipFile(str(tmp_path), "r") as zf:
                zf.extractall(str(extract_dir))

            # 3. 检测 ZIP 顶层结构
            children = [p for p in extract_dir.iterdir()]
            has_raw = any(p.name == "raw" and p.is_dir() for p in children)
            has_wiki = any(p.name == "wiki" and p.is_dir() for p in children)
            has_graph = any(p.name == "graph" and p.is_dir() for p in children)

            if not (has_raw or has_wiki or has_graph):
                return {
                    "error": "ZIP 包结构不正确",
                    "expected": "顶层需包含 raw/、wiki/、graph/ 中至少一个目录",
                    "found": [p.name for p in children if p.is_dir()] or ["(无子目录)"],
                }

            # 4. 创建项目
            db = _mcp_db()
            try:
                pid = db.create_project(project_name)
            finally:
                db.close()

            stats = {"raw_imported": 0, "wiki_imported": 0, "graph_imported": 0, "skipped": 0, "errors": 0}

            if has_raw:
                engine = _mcp_engine()
                try:
                    raw_result = engine.import_raw_files(pid, str(extract_dir / "raw"))
                    stats["raw_imported"] = raw_result.get("imported", 0)
                    stats["skipped"] += raw_result.get("skipped", 0)
                    stats["errors"] += raw_result.get("errors", 0)
                finally:
                    engine.close()

            if has_wiki:
                wiki_dir = extract_dir / "wiki"
                for f in wiki_dir.rglob("*"):
                    if f.is_file():
                        try:
                            rel = f"wiki/{f.relative_to(wiki_dir).as_posix()}"
                            content = f.read_bytes()
                            db2 = _mcp_db()
                            try:
                                db2.add_file(pid, rel, content)
                            finally:
                                db2.close()
                            stats["wiki_imported"] += 1
                        except Exception:
                            stats["errors"] += 1

            if has_graph:
                graph_dir = extract_dir / "graph"
                for f in graph_dir.rglob("*"):
                    if f.is_file():
                        try:
                            rel = f"graph/{f.relative_to(graph_dir).as_posix()}"
                            content = f.read_bytes()
                            db2 = _mcp_db()
                            try:
                                db2.add_file(pid, rel, content)
                            finally:
                                db2.close()
                            stats["graph_imported"] += 1
                        except Exception:
                            stats["errors"] += 1

            # 5. 设置项目状态
            db2 = _mcp_db()
            try:
                if has_wiki or has_graph:
                    db2.set_project_state(pid, "completed")
                else:
                    db2.set_project_state(pid, "unbuilt")
            finally:
                db2.close()

            return {
                "project_id": pid,
                "project_name": project_name,
                "raw_imported": stats["raw_imported"],
                "wiki_imported": stats["wiki_imported"],
                "graph_imported": stats["graph_imported"],
                "skipped": stats["skipped"],
                "errors": stats["errors"],
                "state": "completed" if (has_wiki or has_graph) else "unbuilt",
            }
        finally:
            if extract_dir.exists():
                shutil.rmtree(str(extract_dir), ignore_errors=True)
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


@mcp.tool()
def export_project(project_id: int) -> dict:
    """导出项目为 ZIP 压缩包，返回 Base64 编码的 ZIP 内容。

    包含 raw/、wiki/、graph/ 三个目录的完整文件结构。

    Args:
        project_id: 项目 ID
    """
    import io
    import zipfile

    db = _mcp_db()
    try:
        project = db.get_project(project_id)
        if not project:
            return {"error": "项目不存在"}

        prefixes = ("raw/", "wiki/", "graph/")
        all_files = []
        for prefix in prefixes:
            files = db.list_files(project_id, prefix)
            all_files.extend(files)

        if not all_files:
            return {"error": "项目没有可导出的文件"}

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in all_files:
                content = db.get_file_content_by_path(project_id, f["relative_path"])
                zf.writestr(f["relative_path"], content or b"")

        buf.seek(0)
        zip_base64 = base64.b64encode(buf.read()).decode("ascii")

        return {
            "project_id": project_id,
            "project_name": project["name"],
            "file_count": len(all_files),
            "content_base64": zip_base64,
            "format": "zip",
            "encoding": "base64",
        }
    finally:
        db.close()


@mcp.tool()
def delete_project(project_id: int, confirm: bool = False) -> dict:
    """删除项目及其所有缓存数据。此操作不可逆。

    Args:
        project_id: 项目 ID
        confirm: 必须设置为 true 才能执行删除
    """
    if not confirm:
        return {
            "error": "删除操作需要确认",
            "project_id": project_id,
            "hint": "请设置 confirm=true 后重试",
        }

    db = _mcp_db()
    try:
        project = db.get_project(project_id)
        if not project:
            return {"error": "项目不存在", "project_id": project_id}

        project_name = project["name"]
        deleted = db.delete_project(project_id)
        return {
            "deleted": deleted,
            "project_id": project_id,
            "project_name": project_name,
        }
    finally:
        db.close()


# ── 编译与更新 ────────────────────────────────────────────────────────

@mcp.tool()
def build_knowledge(project_id: int, instruction: str = "", incremental: bool = False) -> dict:
    """构建或增量更新项目知识库。

    流程：获取 raw 文件 → LLM 摄入生成 wiki 页面 → 构建知识图谱。

    Args:
        project_id: 项目 ID
        instruction: 用户自定义的构建指令（可选）。传入后将更新项目的构建指令，
                     构建时会使用新的指令。不传则保持现有指令不变。
        incremental: 是否增量更新（默认 false，全量构建）。
                     设为 true 时仅处理上次构建后新增或变更的 raw 文件，速度更快。
    """
    db = _mcp_db()
    try:
        project = db.get_project(project_id)
        if not project:
            return {"error": "项目不存在"}
        if instruction:
            db.set_ingest_instruction(project_id, instruction)
        db.set_project_state(project_id, "building")
    finally:
        db.close()

    engine = _mcp_engine()
    try:
        if incremental:
            result = engine.update_knowledge_base(project_id)
        else:
            result = engine.build_knowledge_base(project_id)
        db2 = _mcp_db()
        try:
            db2.set_project_state(project_id, "completed")
        finally:
            db2.close()
        return {
            "project_id": project_id,
            "state": "completed",
            "result": result,
        }
    except Exception as e:
        db2 = _mcp_db()
        try:
            db2.set_project_state(project_id, "unbuilt")
        finally:
            db2.close()
        return {
            "project_id": project_id,
            "state": "unbuilt",
            "error": str(e),
        }
    finally:
        engine.close()


@mcp.tool()
def upload_files(
    project_id: int,
    file_path: str = "",
    content_base64: str = "",
    file_name: str = "",
    auto_update: bool = False,
) -> dict:
    """向已有项目追加文件。支持单文件或 ZIP 压缩包。

    支持两种输入方式：
    1. file_path      — 本地文件绝对路径（仅本地部署可用）
    2. content_base64 — 文件内容的 Base64 编码（需配合 file_name）

    Args:
        project_id: 目标项目 ID
        file_path: 本地文件或 ZIP 包的绝对路径
        content_base64: 文件内容的 Base64 编码
        file_name: 文件名（使用 content_base64 时必填）
        auto_update: 上传后是否自动增量更新知识库，默认 false
    """
    import tempfile

    db = _mcp_db()
    try:
        project = db.get_project(project_id)
        if not project:
            return {"error": "项目不存在"}
    finally:
        db.close()

    # 获取文件内容
    tmp_path = None
    try:
        if content_base64:
            if not file_name:
                return {"error": "使用 content_base64 时必须提供 file_name"}
            with tempfile.NamedTemporaryFile(suffix=Path(file_name).suffix or ".bin",
                                             delete=False) as tmp:
                tmp.write(base64.b64decode(content_base64))
                tmp.flush()
                tmp_path = Path(tmp.name)
                src_path = tmp_path
                src_name = file_name
        elif file_path:
            src_path = Path(file_path)
            if not src_path.exists():
                return {"error": f"文件不存在: {file_path}"}
            src_name = src_path.name
        else:
            return {"error": "必须提供 file_path 或 content_base64"}

        is_zip = src_name.lower().endswith(".zip")

        if is_zip:
            import zipfile
            extract_dir = DEFAULT_UPLOAD_DIR / f"_mcp_upload_{project_id}"
            extract_dir.mkdir(parents=True, exist_ok=True)
            try:
                with zipfile.ZipFile(str(src_path), "r") as zf:
                    zf.extractall(str(extract_dir))

                engine = _mcp_engine()
                try:
                    import_result = engine.import_raw_files(project_id, str(extract_dir))
                finally:
                    engine.close()
            finally:
                if extract_dir.exists():
                    shutil.rmtree(str(extract_dir), ignore_errors=True)
        else:
            # 单文件：保存到上传目录后导入
            dest_dir = DEFAULT_UPLOAD_DIR / project["name"]
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path = dest_dir / src_name
            shutil.copy2(str(src_path), str(dest_path))

            engine = _mcp_engine()
            try:
                import_result = engine.import_raw_files(project_id, str(dest_dir))
            finally:
                engine.close()

            if dest_path.exists():
                dest_path.unlink()
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)

    result = {
        "project_id": project_id,
        "file_name": src_name,
        "imported": import_result.get("imported", 0),
        "skipped": import_result.get("skipped", 0),
        "errors": import_result.get("errors", 0),
    }

    # 可选：自动增量更新
    if auto_update:
        engine = _mcp_engine()
        try:
            db2 = _mcp_db()
            try:
                db2.set_project_state(project_id, "building")
            finally:
                db2.close()
            update_result = engine.update_knowledge_base(project_id)
            db2 = _mcp_db()
            try:
                db2.set_project_state(project_id, "completed")
            finally:
                db2.close()
            result["update_result"] = update_result
            result["state"] = "completed"
        except Exception as e:
            result["update_error"] = str(e)
        finally:
            engine.close()

    return result


# ── 查询与检索 ────────────────────────────────────────────────────────

@mcp.tool()
def query_knowledge(project_id: int, question: str) -> dict:
    """向已编译的知识库提出自然语言问题，返回 LLM 生成的回答。

    Args:
        project_id: 项目 ID
        question: 要查询的自然语言问题
    """
    engine = _mcp_engine()
    try:
        answer = engine.query(project_id, question)
        return {
            "project_id": project_id,
            "question": question,
            "answer": answer,
        }
    except Exception as e:
        return {
            "project_id": project_id,
            "question": question,
            "error": str(e),
        }
    finally:
        engine.close()


@mcp.tool()
def search_files(project_id: int, keyword: str) -> dict:
    """在项目文件中进行全文搜索，返回匹配的文件路径和内容片段。

    Args:
        project_id: 项目 ID
        keyword: 搜索关键词
    """
    db = _mcp_db()
    try:
        project = db.get_project(project_id)
        if not project:
            return {"error": "项目不存在"}
        results = db.search(project_id, keyword)
        return {
            "project_id": project_id,
            "keyword": keyword,
            "total": len(results),
            "results": results,
        }
    finally:
        db.close()


def _start_mcp_server():
    """在后台线程启动 MCP Streamable HTTP 服务。"""
    import uvicorn
    mcp_app = mcp.streamable_http_app()
    uvicorn.run(mcp_app, host="0.0.0.0", port=MCP_PORT, log_level="warning")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(REPO_ROOT, ".env"))

    api_port = int(os.environ.get("API_PORT", "5000"))

    print("LLM Wiki Web API 启动中...")
    print(f"数据库: {DB_PATH}")
    print(f"上传目录: {DEFAULT_UPLOAD_DIR}")
    print(f"访问地址: http://localhost:{api_port}")

    debug = os.environ.get("FLASK_DEBUG", "0") == "1"

    # MCP 服务仅在非 debug 模式下启动，避免 reloader 导致端口冲突
    if not debug:
        t = threading.Thread(target=_start_mcp_server, daemon=True)
        t.start()
        print(f"MCP 服务: http://localhost:{MCP_PORT}/mcp")
    else:
        print(f"MCP 服务: 已禁用（debug 模式）")

    app.run(host="0.0.0.0", port=api_port, debug=debug)
