"""
MCP Server — Streamable HTTP 服务，工具直调 LLMWikiEngine。
与 FastAPI API 同进程启动（daemon 线程）。
"""
from __future__ import annotations

import base64
import os
import shutil
import threading
import uuid
from pathlib import Path

import requests
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from tools.logger import get_logger
from storage.db import WikiStorage
from wiki_engine import LLMWikiEngine
from wiki_engine.constants import DEFAULT_UPLOAD_DIR

logger = get_logger(__name__)

# server/app/mcp_service.py → parent.parent = server/
REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "storage" / "wiki.db"

MCP_PORT = int(os.environ.get("MCP_PORT", "8081"))


def _build_mcp_transport_security() -> TransportSecuritySettings:
    """构建 MCP Host 白名单，避免局域网/Docker 跨容器访问被 DNS 重绑定防护拦截（421）。

    FastMCP 默认只允许 127.0.0.1/localhost；跨容器常用宿主机 IP、
    host.docker.internal 或 compose 服务名访问，需额外放行。
    """
    enable = os.environ.get("MCP_DNS_REBINDING_PROTECTION", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )
    allowed_hosts = [
        "127.0.0.1:*",
        "localhost:*",
        "[::1]:*",
        "host.docker.internal:*",
    ]
    # 逗号分隔：IP、主机名，或带端口 / 通配端口（如 192.168.7.203、backend:8081、backend:*）
    extra = os.environ.get("MCP_ALLOWED_HOSTS", "").strip()
    for item in extra.split(","):
        host = item.strip()
        if not host:
            continue
        if ":" not in host:
            host = f"{host}:*"
        if host not in allowed_hosts:
            allowed_hosts.append(host)

    allowed_origins = [
        "http://127.0.0.1:*",
        "http://localhost:*",
        "http://[::1]:*",
        "http://host.docker.internal:*",
    ]
    for host in allowed_hosts:
        base = host[:-2] if host.endswith(":*") else host.rsplit(":", 1)[0]
        if base.startswith("[") or base in ("127.0.0.1", "localhost", "::1"):
            continue
        for scheme_origin in (f"http://{base}:*", f"https://{base}:*"):
            if scheme_origin not in allowed_origins:
                allowed_origins.append(scheme_origin)

    logger.info(
        "MCP transport security: dns_rebinding=%s allowed_hosts=%s",
        enable,
        allowed_hosts,
    )
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=enable,
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )


mcp = FastMCP(
    "llm-wiki-engine",
    transport_security=_build_mcp_transport_security(),
)


def _mcp_engine():
    """创建 MCP 工具专用的引擎实例。"""
    return LLMWikiEngine(str(DB_PATH))


def _mcp_db():
    """创建 MCP 工具专用的数据库实例。"""
    return WikiStorage(str(DB_PATH))


# ── 知识库生命周期 ────────────────────────────────────────────────────

@mcp.tool()
def list_kbs() -> dict:
    """列出所有知识库，返回每个知识库的 ID、名称、状态（unbuilt/building/completed）和统计信息。"""
    db = _mcp_db()
    try:
        kbs = db.list_kbs()
        return {"kbs": kbs, "total": len(kbs)}
    finally:
        db.close()


@mcp.tool()
def create_kb(name: str = "Untitled", description: str = "") -> dict:
    """创建一个空知识库（不导入文件）。

    Args:
        name: 知识库名称，默认 "Untitled"
        description: 知识库描述，可选
    """
    db = _mcp_db()
    try:
        kid = db.create_kb(name, description)
        return {"kb_id": kid, "name": name, "message": "知识库创建成功"}
    finally:
        db.close()


@mcp.tool()
def import_kb(
    zip_url: str = "",
    file_path: str = "",
    kb_name: str = "",
) -> dict:
    """从 ZIP 压缩包创建知识库并导入所有文件。支持两种输入方式：

    1. zip_url   — 远程 ZIP 文件 URL（推荐，适用于远程 MCP 客户端）
    2. file_path — 服务端本地 ZIP 绝对路径（文件须已在 MCP 服务器磁盘上）

    本机调试请用 skills/llm-wiki（REST）；Agent 可将文件放入共享 inbox 后用 file_path（Compose 下为 /data/inbox/...）。

    ZIP 包结构（与 export_kb 导出产物对应）：
        raw/   — 原始文件，导入后存入 raw/ 分类，用于后续编译
        wiki/  — 已编译的 wiki 页面，直接存入 wiki/ 分类
        graph/ — 知识图谱数据，直接存入 graph/ 分类

    若 wiki/ 或 graph/ 目录存在，导入后知识库状态直接设为 completed。

    Args:
        zip_url: 远程 ZIP 文件的完整 URL（优先使用）
        file_path: 服务端本地 ZIP 文件绝对路径
        kb_name: 知识库名称（可选；默认取 URL/文件名）
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
                    logger.info("MCP import_kb: downloading ZIP url=%s", zip_url)
                    resp = requests.get(zip_url, timeout=120)
                    resp.raise_for_status()
                    tmp.write(resp.content)
                    logger.info(
                        "MCP import_kb: download ok status=%s size=%d",
                        resp.status_code,
                        len(resp.content),
                    )
                except requests.RequestException as e:
                    logger.exception("MCP import_kb: download failed url=%s", zip_url)
                    return {"error": f"下载 ZIP 失败: {e}"}
                if not kb_name:
                    url_path = parsed.path.rstrip("/")
                    kb_name = Path(url_path).stem if url_path else "imported"

            elif file_path:
                src = Path(file_path)
                if not src.exists():
                    return {"error": f"文件不存在: {file_path}"}
                if not src.suffix.lower() == ".zip":
                    return {"error": "仅支持 .zip 格式"}
                tmp.write(src.read_bytes())
                if not kb_name:
                    kb_name = src.stem

            else:
                return {
                    "error": "必须提供 zip_url 或 file_path 之一",
                    "hint": "Compose 共享目录用 /data/inbox/...；本机调试用 skills/llm-wiki",
                }

            tmp.flush()

        # 2. 创建知识库 + 解压 ZIP
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

            # 4. 创建知识库
            db = _mcp_db()
            try:
                kid = db.create_kb(kb_name)
            finally:
                db.close()

            stats = {"raw_imported": 0, "wiki_imported": 0, "graph_imported": 0, "skipped": 0, "errors": 0}

            if has_raw:
                engine = _mcp_engine()
                try:
                    raw_result = engine.import_raw_files(kid, str(extract_dir / "raw"))
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
                                db2.add_file(kid, rel, content)
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
                                db2.add_file(kid, rel, content)
                            finally:
                                db2.close()
                            stats["graph_imported"] += 1
                        except Exception:
                            stats["errors"] += 1

            # 5. 设置知识库状态
            db2 = _mcp_db()
            try:
                if has_wiki or has_graph:
                    db2.set_kb_state(kid, "completed")
                else:
                    db2.set_kb_state(kid, "unbuilt")
            finally:
                db2.close()

            return {
                "kb_id": kid,
                "kb_name": kb_name,
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
def export_kb(kb_id: int) -> dict:
    """导出知识库为 ZIP 压缩包，返回 Base64 编码的 ZIP 内容。

    包含 raw/、wiki/、graph/ 三个目录的完整文件结构。

    Args:
        kb_id: 知识库 ID
    """
    import io
    import zipfile

    db = _mcp_db()
    try:
        kb = db.get_kb(kb_id)
        if not kb:
            return {"error": "知识库不存在"}

        prefixes = ("raw/", "wiki/", "graph/")
        all_files = []
        for prefix in prefixes:
            files = db.list_files(kb_id, prefix)
            all_files.extend(files)

        if not all_files:
            return {"error": "知识库没有可导出的文件"}

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in all_files:
                content = db.get_file_content_by_path(kb_id, f["relative_path"])
                zf.writestr(f["relative_path"], content or b"")

        buf.seek(0)
        zip_base64 = base64.b64encode(buf.read()).decode("ascii")

        return {
            "kb_id": kb_id,
            "kb_name": kb["name"],
            "file_count": len(all_files),
            "content_base64": zip_base64,
            "format": "zip",
            "encoding": "base64",
        }
    finally:
        db.close()


@mcp.tool()
def delete_kb(kb_id: int, confirm: bool = False) -> dict:
    """删除知识库及其所有缓存数据。此操作不可逆。

    Args:
        kb_id: 知识库 ID
        confirm: 必须设置为 true 才能执行删除
    """
    if not confirm:
        return {
            "error": "删除操作需要确认",
            "kb_id": kb_id,
            "hint": "请设置 confirm=true 后重试",
        }

    db = _mcp_db()
    try:
        kb = db.get_kb(kb_id)
        if not kb:
            return {"error": "知识库不存在", "kb_id": kb_id}

        kb_name = kb["name"]
        deleted = db.delete_kb(kb_id)
        return {
            "deleted": deleted,
            "kb_id": kb_id,
            "kb_name": kb_name,
        }
    finally:
        db.close()


# ── 编译与更新 ────────────────────────────────────────────────────────

@mcp.tool()
def build_knowledge(kb_id: int, instruction: str = "", incremental: bool = False) -> dict:
    """构建或增量更新知识库。

    流程：获取 raw 文件 → LLM 摄入生成 wiki 页面 → 构建知识图谱。

    Args:
        kb_id: 知识库 ID
        instruction: 用户自定义的构建指令（可选）。传入后将更新知识库的构建指令，
                     构建时会使用新的指令。不传则保持现有指令不变。
        incremental: 是否增量更新（默认 false，全量构建）。
                     设为 true 时仅处理上次构建后新增或变更的 raw 文件，速度更快。
    """
    db = _mcp_db()
    try:
        kb = db.get_kb(kb_id)
        if not kb:
            return {"error": "知识库不存在"}
        if instruction:
            db.set_ingest_instruction(kb_id, instruction)
        db.set_kb_state(kb_id, "building")
    finally:
        db.close()

    engine = _mcp_engine()
    try:
        if incremental:
            result = engine.update_knowledge_base(kb_id)
        else:
            result = engine.build_knowledge_base(kb_id)
        db2 = _mcp_db()
        try:
            db2.set_kb_state(kb_id, "completed")
        finally:
            db2.close()
        return {
            "kb_id": kb_id,
            "state": "completed",
            "result": result,
        }
    except Exception as e:
        db2 = _mcp_db()
        try:
            db2.set_kb_state(kb_id, "unbuilt")
        finally:
            db2.close()
        return {
            "kb_id": kb_id,
            "state": "unbuilt",
            "error": str(e),
        }
    finally:
        engine.close()


@mcp.tool()
def upload_files(
    kb_id: int,
    file_path: str = "",
    auto_update: bool = False,
) -> dict:
    """向已有知识库追加文件。支持单文件或 ZIP 压缩包。

    仅接受对 MCP 进程可读的本地路径 ``file_path``。
    Compose 推荐把文件放到共享投递目录后传 ``/data/inbox/<filename>``。
    无共享盘的本机调试用 skills/llm-wiki（REST multipart）。

    Args:
        kb_id: 目标知识库 ID
        file_path: 服务端可读的文件或 ZIP 绝对路径（如 /data/inbox/doc.pdf）
        auto_update: 上传后是否自动增量更新知识库，默认 false
    """
    db = _mcp_db()
    try:
        kb = db.get_kb(kb_id)
        if not kb:
            return {"error": "知识库不存在"}
    finally:
        db.close()

    if not file_path:
        return {
            "error": "必须提供 file_path（服务端路径）",
            "hint": "Compose 用 /data/inbox/...；本机调试用 skills/llm-wiki/scripts/wiki.py upload",
        }

    src_path = Path(file_path)
    if not src_path.exists():
        return {"error": f"文件不存在: {file_path}"}
    src_name = src_path.name

    is_zip = src_name.lower().endswith(".zip")

    if is_zip:
        import zipfile
        extract_dir = DEFAULT_UPLOAD_DIR / f"_mcp_upload_{kb_id}"
        extract_dir.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(str(src_path), "r") as zf:
                zf.extractall(str(extract_dir))

            engine = _mcp_engine()
            try:
                import_result = engine.import_raw_files(kb_id, str(extract_dir))
            finally:
                engine.close()
        finally:
            if extract_dir.exists():
                shutil.rmtree(str(extract_dir), ignore_errors=True)
    else:
        # 单文件：保存到上传目录后导入
        dest_dir = DEFAULT_UPLOAD_DIR / kb["name"]
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / src_name
        shutil.copy2(str(src_path), str(dest_path))

        engine = _mcp_engine()
        try:
            import_result = engine.import_raw_files(kb_id, str(dest_dir))
        finally:
            engine.close()

        if dest_path.exists():
            dest_path.unlink()

    result = {
        "kb_id": kb_id,
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
                db2.set_kb_state(kb_id, "building")
            finally:
                db2.close()
            update_result = engine.update_knowledge_base(kb_id)
            db2 = _mcp_db()
            try:
                db2.set_kb_state(kb_id, "completed")
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
def query_knowledge(kb_id: int, question: str) -> dict:
    """向已编译的知识库提出自然语言问题，返回 LLM 生成的回答。

    Args:
        kb_id: 知识库 ID
        question: 要查询的自然语言问题
    """
    engine = _mcp_engine()
    try:
        answer = engine.query(kb_id, question)
        return {
            "kb_id": kb_id,
            "question": question,
            "answer": answer,
        }
    except Exception as e:
        return {
            "kb_id": kb_id,
            "question": question,
            "error": str(e),
        }
    finally:
        engine.close()


@mcp.tool()
def search_files(kb_id: int, keyword: str) -> dict:
    """在知识库文件中进行全文搜索，返回匹配的文件路径和内容片段。

    Args:
        kb_id: 知识库 ID
        keyword: 搜索关键词
    """
    db = _mcp_db()
    try:
        kb = db.get_kb(kb_id)
        if not kb:
            return {"error": "知识库不存在"}
        results = db.search(kb_id, keyword)
        return {
            "kb_id": kb_id,
            "keyword": keyword,
            "total": len(results),
            "results": results,
        }
    finally:
        db.close()


@mcp.tool()
def read_wiki_file(kb_id: int, relative_path: str) -> dict:
    """读取知识库中指定路径的文件全文内容。

    Args:
        kb_id: 知识库 ID
        relative_path: 文件相对路径，如 "wiki/index.md"、"wiki/sources/database.md"
    """
    db = _mcp_db()
    try:
        kb = db.get_kb(kb_id)
        if not kb:
            return {"error": "知识库不存在", "kb_id": kb_id}

        text = db.get_file_text_by_path(kb_id, relative_path)
        if text is None:
            return {
                "error": "文件不存在或内容为空",
                "kb_id": kb_id,
                "relative_path": relative_path,
            }

        return {
            "kb_id": kb_id,
            "relative_path": relative_path,
            "content": text,
        }
    finally:
        db.close()


def _run_mcp_uvicorn():
    """在当前线程运行 MCP Streamable HTTP 服务（uvicorn）。"""
    import uvicorn

    mcp_app = mcp.streamable_http_app()
    uvicorn.run(mcp_app, host="0.0.0.0", port=MCP_PORT, log_level="warning")


def start_mcp_server_thread() -> threading.Thread:
    """在后台 daemon 线程启动 MCP Streamable HTTP 服务。"""
    t = threading.Thread(target=_run_mcp_uvicorn, daemon=True, name="mcp-server")
    t.start()
    logger.info("MCP 服务: http://localhost:%d/mcp", MCP_PORT)
    return t
