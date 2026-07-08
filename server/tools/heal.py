#!/usr/bin/env python3
from __future__ import annotations

"""
图谱自愈 CLI — 委托给 wiki_engine.heal 工作流。

Usage:
    python -m tools.heal --kb-id 1
    python -m tools.heal --kb-id 1 --min-refs 3 --max-sources 15
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


def main() -> int:
    parser = argparse.ArgumentParser(description="图谱自愈：补全缺失实体页面")
    parser.add_argument("--db", default="storage/wiki.db", help="SQLite 数据库路径")
    parser.add_argument("--kb-id", type=int, required=True, help="知识库 ID")
    parser.add_argument("--min-refs", type=int, default=3, help="最小引用次数阈值")
    parser.add_argument("--max-sources", type=int, default=15, help="最大引用来源数")
    parser.add_argument("--model", default="claude-3-5-haiku-latest", help="LLM 模型")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    setup_logging(level="INFO")

    engine = LLMWikiEngine(args.db)
    try:
        result = engine.heal_graph(
            args.kb_id,
            min_refs=args.min_refs,
            max_sources=args.max_sources,
            model=args.model,
        )
    finally:
        engine.close()

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        logger.info(
            "补全实体: %d/%d",
            result.get("healed", 0),
            result.get("total_missing", 0),
        )
        for entity in result.get("entities_created", []):
            logger.info("  - %s", entity)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
