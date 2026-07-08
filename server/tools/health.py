#!/usr/bin/env python3
from __future__ import annotations

"""
结构健康检查 CLI — 委托给 wiki_engine.health 工作流（SQLite 多知识库）。

与 lint 的区别：
  health = 结构完整性，确定性检查，零 LLM 调用，适合每次会话
  lint   = 内容质量，含 LLM 语义分析，适合定期运行

Usage:
    python -m tools.health --kb-id 1
    python -m tools.health --kb-id 1 --json
    python -m tools.health --kb-id 1 --save
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from wiki_engine import LLMWikiEngine
from tools.logger import get_logger, setup_logging

logger = get_logger(__name__)


def format_report(results: dict) -> str:
    lines = [
        f"# Health Report — {results['date']}",
        f"知识库: {results.get('kb_name', '')}",
        f"总页面数: {results['total_pages']}",
        "",
        "## 空/存根文件",
        "",
    ]

    if results["empty_files"]:
        for ef in results["empty_files"]:
            lines.append(
                f"- `{ef['path']}` — {ef['status']} "
                f"({ef['body_bytes']} body bytes / {ef['total_bytes']} total)"
            )
    else:
        lines.append("无空文件或存根文件。✅")

    lines.extend(["", "## 索引同步", ""])
    sync = results["index_sync"]
    if sync["in_index_not_on_disk"]:
        lines.append("**索引中有但库中缺失:**")
        for p in sync["in_index_not_on_disk"]:
            lines.append(f"- `{p}`")
        lines.append("")
    if sync["on_disk_not_in_index"]:
        lines.append("**库中有但索引缺失:**")
        for p in sync["on_disk_not_in_index"]:
            lines.append(f"- `{p}`")
        lines.append("")
    if not sync["in_index_not_on_disk"] and not sync["on_disk_not_in_index"]:
        lines.append("索引与页面完全同步。✅")
        lines.append("")

    lines.extend(["", "## 日志覆盖", ""])
    if results["log_coverage"]:
        lines.append("**缺少 ingest 日志条目的源页面:**")
        for lm in results["log_coverage"]:
            title = lm.get("title") or lm.get("slug", "")
            lines.append(f"- `{lm['path']}` — {title}")
    else:
        lines.append("所有源页面均有对应日志条目。✅")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="结构健康检查（确定性，无 LLM 调用）"
    )
    parser.add_argument("--db", default="storage/wiki.db", help="SQLite 数据库路径")
    parser.add_argument("--kb-id", type=int, required=True, help="知识库 ID")
    parser.add_argument("--save", action="store_true", help="保存报告到 wiki/health-report.md")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    setup_logging(level="INFO")

    engine = LLMWikiEngine(args.db)
    try:
        results = engine.health_check(args.kb_id)
    finally:
        engine.close()

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        report = format_report(results)
        print(report)

        if args.save:
            from storage.db import WikiStorage

            db = WikiStorage(args.db)
            try:
                db.add_file(args.kb_id, "wiki/health-report.md", report)
            finally:
                db.close()
            logger.info("已保存: wiki/health-report.md")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
