#!/usr/bin/env python3
"""
LLM Wiki Web API — Flask 后端服务
提供项目、文件树、文件内容、知识图谱等 REST API
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory
from flask_cors import CORS

REPO_ROOT = Path(__file__).parent
sys.path.insert(0, str(REPO_ROOT))

from storage.db import WikiStorage
from wiki_engine import LLMWikiEngine
from wiki_engine.constants import DEFAULT_UPLOAD_DIR

app = Flask(__name__, static_folder="web", static_url_path="")
CORS(app)

DB_PATH = REPO_ROOT / "storage" / "wiki.db"


def get_db() -> WikiStorage:
    return WikiStorage(str(DB_PATH))


def get_engine() -> LLMWikiEngine:
    return LLMWikiEngine(str(DB_PATH))


# ── 静态页面 ──────────────────────────────────────────────────────────

@app.route("/")
def index():
    """提供前端页面。

    GET /
    返回 web/index.html 静态页面。
    """
    return send_from_directory("web", "index.html")


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
        if graph_json is None:
            return jsonify({"error": "图谱数据不存在"}), 404
        data = json.loads(graph_json)
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
    """构建知识库（完整流程：解析、索引、生成图谱等）。

    POST /api/projects/<project_id>/build

    路径参数:
        - project_id (int): 项目 ID

    响应:
        200: 构建结果对象
    """
    engine = get_engine()
    try:
        result = engine.build_knowledge_base(project_id)
        return jsonify(result)
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

    响应:
        200: 更新结果对象，status 可能为 "up_to_date" 或 "completed"
    """
    data = request.get_json(silent=True) or {}
    source_dir = data.get("source_dir")
    engine = get_engine()
    try:
        result = engine.update_knowledge_base(project_id, source_dir)
        return jsonify(result)
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
        report = engine.lint(project_id)
        return jsonify({"report": report})
    finally:
        engine.close()


@app.route("/api/projects/<int:project_id>/graph/build", methods=["POST"])
def build_graph(project_id):
    """构建/重建知识图谱。

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


@app.route("/api/projects/<int:project_id>/upload-file", methods=["POST"])
def upload_file_to_project(project_id):
    """外部系统向指定项目上传单个文件，并可选择增量更新知识库。

    POST /api/projects/<project_id>/upload-file

    路径参数:
        - project_id (int): 项目 ID

    请求体 (multipart/form-data):
        - file (file): 单个文件

    查询参数:
        - update (bool, 可选): 是否在上传后增量更新知识库，默认 false

    行为:
        1. 将文件保存到 ``uploads/<project_name>/`` 本地目录
        2. 将文件导入到 Wiki 引擎项目的 raw/ 目录
        3. 若 update=true，触发增量知识库更新

    响应:
        200: {"file_name": "<文件名>", "file_id": <ID>, "imported": true,
              "update_result": <更新结果或null>}
        400: {"error": "..."}
        404: {"error": "项目不存在"}
    """
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
        upload_dir = DEFAULT_UPLOAD_DIR / project["name"]
        upload_dir.mkdir(parents=True, exist_ok=True)
        dest_path = upload_dir / safe_name
        file.save(str(dest_path))

        engine = get_engine()
        try:
            engine.import_raw_files(project_id, str(upload_dir))

            update_result = None
            if request.args.get("update", "").lower() == "true":
                update_result = engine.update_knowledge_base(project_id)

            return jsonify({
                "file_name": safe_name,
                "upload_path": str(dest_path),
                "imported": True,
                "update_result": update_result,
            })
        finally:
            engine.close()
            # 导入完成后清理本地临时文件
            if dest_path.exists():
                dest_path.unlink()
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


if __name__ == "__main__":
    print("LLM Wiki Web API 启动中...")
    print(f"数据库: {DB_PATH}")
    print(f"上传目录: {DEFAULT_UPLOAD_DIR}")
    print("访问地址: http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
