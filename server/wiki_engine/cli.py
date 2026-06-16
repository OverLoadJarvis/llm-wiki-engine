"""命令行入口模块

提供 ``python -m wiki_engine`` 命令行接口，支持以下子命令：
- build: 构建知识库
- update: 更新知识库
- query: 查询知识库
- lint: 检查知识库
- health: 结构健康检查
- graph: 构建知识图谱
- list: 列出所有知识库
- stats: 知识库统计
- heal: 图谱自愈
"""

import json
import argparse

from wiki_engine.engine import LLMWikiEngine
from tools.logger import get_logger, setup_logging

logger = get_logger(__name__)


def main() -> None:
    """命令行入口函数。"""
    parser = argparse.ArgumentParser(description="LLM Wiki Engine — 企业知识库引擎")
    sub = parser.add_subparsers(dest="command", required=True)

    # build
    p_build = sub.add_parser("build", help="构建知识库")
    p_build.add_argument("--db", default="storage/wiki.db", help="SQLite 数据库路径")
    p_build.add_argument("--source", required=True, help="源文件目录")
    p_build.add_argument("--kb", required=True, help="知识库名称")
    p_build.add_argument("--no-convert", action="store_true", help="跳过文件格式转换")
    p_build.add_argument("--skip-graph", action="store_true", help="跳过图谱构建")

    # update
    p_update = sub.add_parser("update", help="更新知识库")
    p_update.add_argument("--db", default="storage/wiki.db")
    p_update.add_argument("--kb-id", type=int, required=True)
    p_update.add_argument("--source", default=None)

    # query
    p_query = sub.add_parser("query", help="查询知识库")
    p_query.add_argument("--db", default="storage/wiki.db")
    p_query.add_argument("--kb-id", type=int, required=True)
    p_query.add_argument("--question", required=True)
    p_query.add_argument("--save", action="store_true")

    # lint
    p_lint = sub.add_parser("lint", help="检查知识库")
    p_lint.add_argument("--db", default="storage/wiki.db")
    p_lint.add_argument("--kb-id", type=int, required=True)
    p_lint.add_argument("--save", action="store_true")

    # health
    p_health = sub.add_parser("health", help="结构健康检查")
    p_health.add_argument("--db", default="storage/wiki.db")
    p_health.add_argument("--kb-id", type=int, required=True)

    # graph
    p_graph = sub.add_parser("graph", help="构建知识图谱")
    p_graph.add_argument("--db", default="storage/wiki.db")
    p_graph.add_argument("--kb-id", type=int, required=True)

    # list
    p_list = sub.add_parser("list", help="列出所有知识库")
    p_list.add_argument("--db", default="storage/wiki.db")

    # stats
    p_stats = sub.add_parser("stats", help="知识库统计")
    p_stats.add_argument("--db", default="storage/wiki.db")
    p_stats.add_argument("--kb-id", type=int, required=True)

    # heal
    p_heal = sub.add_parser("heal", help="图谱自愈")
    p_heal.add_argument("--db", default="storage/wiki.db")
    p_heal.add_argument("--kb-id", type=int, required=True)
    p_heal.add_argument("--min-refs", type=int, default=3, help="最小引用次数阈值")
    p_heal.add_argument("--max-sources", type=int, default=15, help="最大引用来源数")
    p_heal.add_argument("--model", default="claude-3-5-haiku-latest", help="LLM 模型")

    args = parser.parse_args()
    setup_logging(level="INFO")
    engine = LLMWikiEngine(args.db)

    try:
        if args.command == "build":
            result = engine.quick_build(args.kb, args.source)
            if not args.skip_graph and result.get("ingested", 0) > 0:
                engine.build_graph(
                    engine.db.get_kb_by_name(args.kb)["id"]
                )
            logger.info(json.dumps(result, ensure_ascii=False, indent=2))

        elif args.command == "update":
            result = engine.update_knowledge_base(args.kb_id, args.source)
            logger.info(json.dumps(result, ensure_ascii=False, indent=2))

        elif args.command == "query":
            answer = engine.query(args.kb_id, args.question, save=args.save)
            logger.info(answer)

        elif args.command == "lint":
            report = engine.lint(args.kb_id, save=args.save)
            logger.info(report)

        elif args.command == "health":
            result = engine.health_check(args.kb_id)
            logger.info(json.dumps(result, ensure_ascii=False, indent=2))

        elif args.command == "graph":
            result = engine.build_graph(args.kb_id)
            logger.info(json.dumps(result, ensure_ascii=False, indent=2))

        elif args.command == "list":
            kbs = engine.list_kbs()
            for p in kbs:
                logger.info("  [%s] %s — %s (%s)", p['id'], p['name'], p.get('description', ''), p.get('updated_at', ''))

        elif args.command == "stats":
            stats = engine.get_kb_stats(args.kb_id)
            logger.info(json.dumps(stats, ensure_ascii=False, indent=2))

        elif args.command == "heal":
            result = engine.heal_graph(
                args.kb_id,
                min_refs=args.min_refs,
                max_sources=args.max_sources,
                model=args.model,
            )
            logger.info(json.dumps(result, ensure_ascii=False, indent=2))

    finally:
        engine.close()
