#!/usr/bin/env python3
"""兼容入口：启动 FastAPI（uvicorn）。推荐直接使用：

    uvicorn app.main:app --host 0.0.0.0 --port 5000
"""
from __future__ import annotations

import os

from dotenv import load_dotenv

from tools.logger import setup_logging

if __name__ == "__main__":
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    setup_logging(level="INFO")

    import uvicorn

    api_port = int(os.environ.get("API_PORT", "5000"))
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=api_port,
        log_level="info",
    )
