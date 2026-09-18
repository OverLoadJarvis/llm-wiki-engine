"""FastAPI application entrypoint."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.deps import init_llm_config_cache, resolve_frontend_dist
from app.mcp_service import MCP_PORT, start_mcp_server_thread
from app.routers import files, import_export, kbs, settings, upload, workflows
from tools.logger import get_logger

logger = get_logger(__name__)


def _cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ORIGINS", "").strip()
    if not raw:
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_llm_config_cache()
    debug = os.environ.get("DEBUG", "0") == "1"
    if not debug:
        start_mcp_server_thread()
        logger.info("MCP 服务: http://localhost:%d/mcp", MCP_PORT)
    else:
        logger.info("MCP 服务: 已禁用（debug 模式）")
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="LLM Wiki Engine", lifespan=lifespan)

    origins = _cors_origins()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=origins != ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register leaf routers directly (FastAPI 0.140 nested IncludeRouter is opaque).
    # import_export first so POST /api/kbs/import wins over /{kb_id} patterns.
    app.include_router(import_export.router)
    app.include_router(kbs.router)
    app.include_router(settings.router)
    app.include_router(files.router)
    app.include_router(workflows.router)
    app.include_router(upload.router)

    frontend_dist = resolve_frontend_dist()
    if frontend_dist:
        assets_dir = frontend_dist / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        @app.get("/")
        def spa_index():
            return FileResponse(frontend_dist / "index.html")

        @app.get("/ui/")
        @app.get("/ui/{filename:path}")
        def spa_ui_legacy(filename: str = "index.html"):
            target = frontend_dist / filename
            if target.is_file():
                return FileResponse(target)
            return FileResponse(frontend_dist / "index.html")

        @app.get("/{full_path:path}")
        def spa_catch_all(full_path: str):
            if full_path.startswith("api/") or full_path.startswith("mcp"):
                return JSONResponse({"error": "Not found"}, status_code=404)
            candidate = frontend_dist / full_path
            if candidate.is_file():
                return FileResponse(candidate)
            index = frontend_dist / "index.html"
            if index.is_file():
                return FileResponse(index)
            return JSONResponse({"error": "Not found"}, status_code=404)
    else:
        @app.get("/")
        def frontend_unavailable():
            return JSONResponse(
                {
                    "message": "前端未构建。请先运行: cd ui-apple && npm install && npm run build",
                    "dev_hint": "开发模式请同时启动后端与 Vite: cd ui-apple && npm run dev",
                },
                status_code=503,
            )

    return app


app = create_app()
