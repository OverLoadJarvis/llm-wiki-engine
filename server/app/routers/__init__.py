"""API routers for LLM Wiki Engine."""

from fastapi import APIRouter

from app.routers import files, import_export, kbs, settings, upload, workflows

api_router = APIRouter()
# import_export first so POST /api/kbs/import is registered before /{kb_id} routes
api_router.include_router(import_export.router)
api_router.include_router(kbs.router)
api_router.include_router(settings.router)
api_router.include_router(files.router)
api_router.include_router(workflows.router)
api_router.include_router(upload.router)

__all__ = ["api_router"]
