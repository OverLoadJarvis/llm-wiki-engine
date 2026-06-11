#!/usr/bin/env python3
"""
LLM Wiki Engine MCP Server — 为外部系统 API 提供 MCP 协议封装。

以 Streamable HTTP 形式对外暴露 MCP 服务，AI 客户端可通过 HTTP 端点调用。

暴露的工具:
    list_projects      — 列出所有项目及状态
    get_project_state  — 查看单个项目状态
    import_project     — 上传 ZIP 创建项目，可选自动编译
    upload_files       — 向已有项目上传文件（单文件或 ZIP），可选自动更新
    update_knowledge   — 触发增量知识库更新
    query_knowledge    — 自然语言查询知识库
    health_check       — 项目健康检查报告
    lint_project       — 项目质量检查报告
    export_project     — 导出项目 ZIP 包
    delete_project     — 删除项目及缓存

使用方式:
    python mcp_server.py
    # 或指定 API 地址和端口:
    LLM_WIKI_API=http://localhost:5000/api python mcp_server.py --port 8080

依赖:
    pip install mcp requests
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests
from mcp.server.fastmcp import FastMCP

# ── 配置 ──────────────────────────────────────────────────────────────

API_BASE = os.environ.get("LLM_WIKI_API", "http://localhost:5000/api")
API_TIMEOUT = int(os.environ.get("LLM_WIKI_TIMEOUT", "300"))


def _api_url(path: str) -> str:
    return f"{API_BASE}{path}"


def _request(method: str, path: str, **kwargs) -> dict[str, Any] | bytes:
    """向 LLM Wiki API 发送请求，返回 JSON 或 bytes。"""
    url = _api_url(path)
    try:
        resp = requests.request(method, url, timeout=API_TIMEOUT, **kwargs)
        resp.raise_for_status()
        ct = resp.headers.get("content-type", "")
        if "application/json" in ct:
            return resp.json()
        return resp.content
    except requests.exceptions.ConnectionError:
        raise RuntimeError(f"无法连接到 LLM Wiki API: {url}")
    except requests.exceptions.HTTPError as e:
        detail = ""
        try:
            detail = e.response.json().get("error", "")
        except Exception:
            detail = e.response.text[:200]
        raise RuntimeError(f"API 错误 {e.response.status_code}: {detail}")


# ── FastMCP 实例 ──────────────────────────────────────────────────────

mcp = FastMCP("llm-wiki-engine")


# ── Tools ──────────────────────────────────────────────────────────────

@mcp.tool()
def list_projects() -> str:
    """列出所有项目，返回每个项目的 ID、名称、状态（unbuilt/building/completed）。"""
    projects = _request("GET", "/projects")
    if not projects:
        return "暂无项目"
    lines = [f"共 {len(projects)} 个项目:"]
    for p in projects:
        state = p.get("state", "unknown")
        lines.append(f"  #{p['id']:>3}  {p['name']:<20}  [{state}]")
    return "\n".join(lines)


@mcp.tool()
def get_project_state(project_id: int) -> str:
    """查看指定项目的完整状态和详细信息。

    Args:
        project_id: 项目 ID
    """
    project = _request("GET", f"/projects/{project_id}")
    return json.dumps(project, ensure_ascii=False, indent=2, default=str)


@mcp.tool()
def import_project(zip_path: str, build: bool = False) -> str:
    """上传一个 ZIP 压缩包，创建新项目并导入所有文件。
    项目名称取自 ZIP 文件名（不含 .zip 后缀）。
    可选自动触发知识库编译。

    Args:
        zip_path: 本地 ZIP 文件的绝对路径
        build: 导入后是否自动编译知识库，默认 false
    """
    zip_path = Path(zip_path)
    if not zip_path.exists():
        return f"错误: 文件不存在: {zip_path}"
    if not zip_path.suffix.lower() == ".zip":
        return "错误: 仅支持 .zip 格式"

    with open(zip_path, "rb") as f:
        result = _request("POST", "/projects/import",
                          files={"file": (zip_path.name, f, "application/zip")})

    lines = [
        "项目导入成功:",
        f"  ID:     {result['project_id']}",
        f"  名称:   {result['project_name']}",
        f"  文件数: {result['file_count']}",
    ]

    if build:
        _request("POST", f"/projects/{result['project_id']}/build")
        lines.append("  已触发编译")

    return "\n".join(lines)


@mcp.tool()
def upload_files(project_id: int, file_path: str, update: bool = False) -> str:
    """向已有项目追加文件。支持单文件或 ZIP 压缩包。
    可选在上传后自动触发增量知识库更新。

    Args:
        project_id: 目标项目 ID
        file_path: 本地文件或 ZIP 包的绝对路径
        update: 上传后是否自动增量更新知识库，默认 false
    """
    file_path = Path(file_path)
    if not file_path.exists():
        return f"错误: 文件不存在: {file_path}"

    update_qs = "?update=true" if update else ""
    mime = "application/zip" if file_path.suffix.lower() == ".zip" else "application/octet-stream"
    with open(file_path, "rb") as f:
        result = _request("POST", f"/projects/{project_id}/upload-file{update_qs}",
                          files={"file": (file_path.name, f, mime)})

    lines = [
        "文件上传完成:",
        f"  文件名: {result['file_name']}",
        f"  导入:   {result['import_result'].get('imported', 0)} 个",
        f"  跳过:   {result['import_result'].get('skipped', 0)} 个",
        f"  错误:   {result['import_result'].get('errors', 0)} 个",
    ]
    if result.get("update_result"):
        lines.append(f"  更新结果: {json.dumps(result['update_result'], ensure_ascii=False)}")

    return "\n".join(lines)


@mcp.tool()
def update_knowledge(project_id: int) -> str:
    """对指定项目触发增量知识库更新。
    如果项目有未处理的新文件，会增量摄入新的知识。

    Args:
        project_id: 项目 ID
    """
    result = _request("POST", f"/projects/{project_id}/update")
    return f"知识库更新完成:\n{json.dumps(result, ensure_ascii=False, indent=2)}"


@mcp.tool()
def query_knowledge(project_id: int, question: str) -> str:
    """向已编译的知识库提出自然语言问题，返回 LLM 生成的回答。

    Args:
        project_id: 项目 ID
        question: 要查询的自然语言问题
    """
    result = _request("POST", f"/projects/{project_id}/query",
                      json={"question": question})
    return result.get("answer", str(result))


@mcp.tool()
def health_check(project_id: int) -> str:
    """检查项目健康状态，返回缺失实体、孤立节点、断链等问题。

    Args:
        project_id: 项目 ID
    """
    result = _request("GET", f"/projects/{project_id}/health")
    return f"健康检查报告:\n{json.dumps(result, ensure_ascii=False, indent=2)}"


@mcp.tool()
def lint_project(project_id: int) -> str:
    """对项目进行质量检查，从结构、内容、一致性等维度生成报告。

    Args:
        project_id: 项目 ID
    """
    result = _request("POST", f"/projects/{project_id}/lint")
    if isinstance(result, list):
        summary = f"共 {len(result)} 个问题"
    elif isinstance(result, dict):
        summary = json.dumps(result, ensure_ascii=False, indent=2)
    else:
        summary = str(result)
    return f"质量检查完成:\n{summary}"


@mcp.tool()
def export_project(project_id: int, output_dir: str) -> str:
    """导出项目为 ZIP 压缩包，保存到本地路径。
    包含 raw/、wiki/、graph/ 等完整目录结构。

    Args:
        project_id: 项目 ID
        output_dir: 导出 ZIP 的输出目录（绝对路径），文件名自动为 <项目名>.zip
    """
    output_dir = Path(output_dir)

    # 先获取项目名称
    project = _request("GET", f"/projects/{project_id}")
    project_name = project.get("name", f"project-{project_id}")

    # 下载 ZIP
    content = _request("GET", f"/projects/{project_id}/export")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{project_name}.zip"
    output_path.write_bytes(content)

    file_size = output_path.stat().st_size
    return f"项目导出成功:\n  路径: {output_path}\n  大小: {file_size:,} bytes"


@mcp.tool()
def delete_project(project_id: int, confirm: bool) -> str:
    """删除项目及其所有缓存数据。此操作不可逆。

    Args:
        project_id: 项目 ID
        confirm: 必须设置为 true 才能执行删除
    """
    if not confirm:
        return f"删除操作需要确认。请设置 confirm=true 后重试。\n  目标项目 ID: {project_id}"

    project = _request("GET", f"/projects/{project_id}")
    project_name = project.get("name", str(project_id))
    _request("DELETE", f"/projects/{project_id}")
    return f"项目已删除: #{project_id} \"{project_name}\""


# ── 入口 ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

    import argparse

    parser = argparse.ArgumentParser(description="LLM Wiki Engine MCP Server (Streamable HTTP)")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址 (默认: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("MCP_PORT", "8081")), help="监听端口 (默认: 8081)")
    args = parser.parse_args()

    import uvicorn
    mcp_app = mcp.streamable_http_app()
    uvicorn.run(mcp_app, host=args.host, port=args.port, log_level="info")