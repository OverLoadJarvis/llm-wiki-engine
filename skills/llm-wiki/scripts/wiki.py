#!/usr/bin/env python3
"""LLM Wiki Engine REST CLI：知识库 CRUD / 上传 / 构建 / 查询等。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 同目录 client（脚本直接执行时）
sys.path.insert(0, str(Path(__file__).resolve().parent))
from client import (  # noqa: E402
    api_base,
    dump,
    encode_path,
    log,
    multipart,
    qs,
    request_bytes,
    request_json,
    request_text,
)


def cmd_kbs_list(args: argparse.Namespace) -> None:
    dump(request_json("GET", f"{args.api}/api/kbs"))


def cmd_kbs_create(args: argparse.Namespace) -> None:
    body = json.dumps({"name": args.name, "description": args.description or ""}).encode()
    dump(request_json("POST", f"{args.api}/api/kbs", data=body, content_type="application/json"))


def cmd_kbs_get(args: argparse.Namespace) -> None:
    dump(request_json("GET", f"{args.api}/api/kbs/{args.kb_id}"))


def cmd_kbs_delete(args: argparse.Namespace) -> None:
    if not args.confirm:
        raise SystemExit("删除需加 --confirm")
    dump(request_json("DELETE", f"{args.api}/api/kbs/{args.kb_id}"))


def cmd_kbs_stats(args: argparse.Namespace) -> None:
    dump(request_json("GET", f"{args.api}/api/kbs/{args.kb_id}/stats"))


def cmd_instruction_get(args: argparse.Namespace) -> None:
    dump(request_json("GET", f"{args.api}/api/kbs/{args.kb_id}/instruction"))


def cmd_instruction_set(args: argparse.Namespace) -> None:
    body = json.dumps({"instruction": args.instruction}).encode()
    dump(
        request_json(
            "PUT",
            f"{args.api}/api/kbs/{args.kb_id}/instruction",
            data=body,
            content_type="application/json",
        )
    )


def _resolve_files(paths: list[str]) -> list[Path]:
    out: list[Path] = []
    for f in paths:
        p = Path(f).expanduser().resolve()
        if not p.is_file():
            raise SystemExit(f"文件不存在: {p}")
        out.append(p)
    return out


def cmd_upload(args: argparse.Namespace) -> None:
    paths = _resolve_files(args.files or [])
    if not paths:
        raise SystemExit("请至少指定一个 --file")

    if args.kb_id is not None:
        combined = []
        for i, p in enumerate(paths):
            do_update = bool(args.update) and i == len(paths) - 1
            body, ctype = multipart({}, [("file", p)])
            url = f"{args.api}/api/kbs/{args.kb_id}/upload-file{qs(update=str(do_update).lower())}"
            log(f"[upload] kb_id={args.kb_id} file={p} update={do_update}")
            combined.append(request_json("POST", url, data=body, content_type=ctype))
        dump(combined if len(combined) > 1 else combined[0])
        return

    if args.kb_name:
        if args.update:
            log("[warn] --kb-name 模式忽略 --update；增量请用 --kb-id")
        files = [("files", p) for p in paths]
        body, ctype = multipart({"kb_name": args.kb_name}, files)
        log(f"[upload] kb_name={args.kb_name} files={', '.join(p.name for p in paths)}")
        dump(request_json("POST", f"{args.api}/api/external/upload", data=body, content_type=ctype))
        return

    raise SystemExit("请指定 --kb-id 或 --kb-name")


def cmd_build(args: argparse.Namespace) -> None:
    if args.instruction:
        body = json.dumps({"instruction": args.instruction}).encode()
        request_json(
            "PUT",
            f"{args.api}/api/kbs/{args.kb_id}/instruction",
            data=body,
            content_type="application/json",
        )
    payload = json.dumps({"stream": False}).encode()
    log(f"[build] kb_id={args.kb_id}")
    dump(
        request_json(
            "POST",
            f"{args.api}/api/kbs/{args.kb_id}/build",
            data=payload,
            content_type="application/json",
        )
    )


def cmd_update(args: argparse.Namespace) -> None:
    payload: dict = {"stream": False}
    if args.source_dir:
        payload["source_dir"] = args.source_dir
    log(f"[update] kb_id={args.kb_id}")
    dump(
        request_json(
            "POST",
            f"{args.api}/api/kbs/{args.kb_id}/update",
            data=json.dumps(payload).encode(),
            content_type="application/json",
        )
    )


def cmd_query(args: argparse.Namespace) -> None:
    payload = json.dumps({"question": args.question, "stream": False}).encode()
    log(f"[query] kb_id={args.kb_id}")
    dump(
        request_json(
            "POST",
            f"{args.api}/api/kbs/{args.kb_id}/query",
            data=payload,
            content_type="application/json",
        )
    )


def cmd_search(args: argparse.Namespace) -> None:
    dump(request_json("GET", f"{args.api}/api/kbs/{args.kb_id}/search{qs(q=args.keyword)}"))


def cmd_files_tree(args: argparse.Namespace) -> None:
    dump(request_json("GET", f"{args.api}/api/kbs/{args.kb_id}/tree"))


def cmd_files_list(args: argparse.Namespace) -> None:
    dump(
        request_json(
            "GET",
            f"{args.api}/api/kbs/{args.kb_id}/files{qs(prefix=args.prefix or '')}",
        )
    )


def cmd_files_get(args: argparse.Namespace) -> None:
    url = f"{args.api}/api/kbs/{args.kb_id}/files/{encode_path(args.path)}"
    text = request_text("GET", url)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        log(f"[files get] wrote {args.out}")
    else:
        print(text)


def cmd_files_put(args: argparse.Namespace) -> None:
    if args.file:
        content = Path(args.file).expanduser().resolve().read_text(encoding="utf-8")
    elif args.content is not None:
        content = args.content
    else:
        raise SystemExit("请指定 --file 或 --content")
    body = json.dumps({"content": content}).encode()
    dump(
        request_json(
            "PUT",
            f"{args.api}/api/kbs/{args.kb_id}/files/{encode_path(args.path)}",
            data=body,
            content_type="application/json",
        )
    )


def cmd_health(args: argparse.Namespace) -> None:
    dump(request_json("GET", f"{args.api}/api/kbs/{args.kb_id}/health"))


def cmd_lint(args: argparse.Namespace) -> None:
    dump(
        request_json(
            "POST",
            f"{args.api}/api/kbs/{args.kb_id}/lint",
            data=b"{}",
            content_type="application/json",
        )
    )


def cmd_graph_get(args: argparse.Namespace) -> None:
    url = f"{args.api}/api/kbs/{args.kb_id}/graph{qs(file=args.file)}"
    data = request_json("GET", url)
    if args.out:
        Path(args.out).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"[graph get] wrote {args.out}")
    else:
        dump(data)


def cmd_graph_build(args: argparse.Namespace) -> None:
    dump(
        request_json(
            "POST",
            f"{args.api}/api/kbs/{args.kb_id}/graph/build",
            data=b"{}",
            content_type="application/json",
        )
    )


def cmd_export(args: argparse.Namespace) -> None:
    out = Path(args.out).expanduser().resolve()
    raw = request_bytes("GET", f"{args.api}/api/kbs/{args.kb_id}/export")
    out.write_bytes(raw)
    log(f"[export] kb_id={args.kb_id} -> {out} ({len(raw)} bytes)")
    dump({"ok": True, "path": str(out), "bytes": len(raw)})


def cmd_import_zip(args: argparse.Namespace) -> None:
    p = Path(args.file).expanduser().resolve()
    if not p.is_file():
        raise SystemExit(f"文件不存在: {p}")
    body, ctype = multipart({}, [("file", p)])
    log(f"[import-zip] kb_id={args.kb_id} file={p}")
    dump(
        request_json(
            "POST",
            f"{args.api}/api/kbs/{args.kb_id}/import-zip",
            data=body,
            content_type=ctype,
        )
    )


def cmd_import_kb(args: argparse.Namespace) -> None:
    p = Path(args.file).expanduser().resolve()
    if not p.is_file():
        raise SystemExit(f"文件不存在: {p}")
    body, ctype = multipart({}, [("file", p)])
    log(f"[import-kb] file={p}")
    dump(
        request_json(
            "POST",
            f"{args.api}/api/kbs/import",
            data=body,
            content_type=ctype,
        )
    )


def cmd_import_dir(args: argparse.Namespace) -> None:
    payload = json.dumps({"source_dir": args.source_dir, "stream": False}).encode()
    log(f"[import-dir] kb_id={args.kb_id} source_dir={args.source_dir}")
    dump(
        request_json(
            "POST",
            f"{args.api}/api/kbs/{args.kb_id}/import",
            data=payload,
            content_type="application/json",
        )
    )


def _add_api(p: argparse.ArgumentParser) -> None:
    p.add_argument("--api", default=api_base(), help="API 根地址（或环境变量 LLM_WIKI_API）")


def _add_kb(p: argparse.ArgumentParser) -> None:
    p.add_argument("--kb-id", type=int, required=True, help="知识库 ID")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wiki.py",
        description="LLM Wiki Engine REST CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # kbs
    p_kbs = sub.add_parser("kbs", help="知识库 CRUD")
    kbs_sub = p_kbs.add_subparsers(dest="kbs_cmd", required=True)

    p = kbs_sub.add_parser("list", help="列出知识库")
    _add_api(p)
    p.set_defaults(func=cmd_kbs_list)

    p = kbs_sub.add_parser("create", help="创建空知识库")
    _add_api(p)
    p.add_argument("--name", required=True)
    p.add_argument("--description", default="")
    p.set_defaults(func=cmd_kbs_create)

    p = kbs_sub.add_parser("get", help="获取知识库详情")
    _add_api(p)
    _add_kb(p)
    p.set_defaults(func=cmd_kbs_get)

    p = kbs_sub.add_parser("delete", help="删除知识库")
    _add_api(p)
    _add_kb(p)
    p.add_argument("--confirm", action="store_true")
    p.set_defaults(func=cmd_kbs_delete)

    p = kbs_sub.add_parser("stats", help="知识库统计")
    _add_api(p)
    _add_kb(p)
    p.set_defaults(func=cmd_kbs_stats)

    # instruction
    p_ins = sub.add_parser("instruction", help="构建指令")
    ins_sub = p_ins.add_subparsers(dest="ins_cmd", required=True)
    p = ins_sub.add_parser("get", help="读取构建指令")
    _add_api(p)
    _add_kb(p)
    p.set_defaults(func=cmd_instruction_get)
    p = ins_sub.add_parser("set", help="写入构建指令")
    _add_api(p)
    _add_kb(p)
    p.add_argument("--instruction", required=True)
    p.set_defaults(func=cmd_instruction_set)

    # upload
    p = sub.add_parser("upload", help="本机文件 multipart 上传")
    _add_api(p)
    p.add_argument("--kb-id", type=int)
    p.add_argument("--kb-name")
    p.add_argument("--file", action="append", dest="files", default=[])
    p.add_argument("--update", action="store_true", help="上传后增量更新（仅 --kb-id）")
    p.set_defaults(func=cmd_upload)

    # workflows
    p = sub.add_parser("build", help="全量构建")
    _add_api(p)
    _add_kb(p)
    p.add_argument("--instruction", default="", help="可选：先写入构建指令")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("update", help="增量更新")
    _add_api(p)
    _add_kb(p)
    p.add_argument("--source-dir", default=None, help="可选：服务端目录")
    p.set_defaults(func=cmd_update)

    p = sub.add_parser("query", help="自然语言查询")
    _add_api(p)
    _add_kb(p)
    p.add_argument("--question", required=True)
    p.set_defaults(func=cmd_query)

    p = sub.add_parser("search", help="全文搜索")
    _add_api(p)
    _add_kb(p)
    p.add_argument("--keyword", required=True)
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("health", help="健康检查")
    _add_api(p)
    _add_kb(p)
    p.set_defaults(func=cmd_health)

    p = sub.add_parser("lint", help="内容质量检查")
    _add_api(p)
    _add_kb(p)
    p.set_defaults(func=cmd_lint)

    # files
    p_files = sub.add_parser("files", help="文件树 / 读写")
    files_sub = p_files.add_subparsers(dest="files_cmd", required=True)

    p = files_sub.add_parser("tree", help="目录树")
    _add_api(p)
    _add_kb(p)
    p.set_defaults(func=cmd_files_tree)

    p = files_sub.add_parser("list", help="按前缀列文件")
    _add_api(p)
    _add_kb(p)
    p.add_argument("--prefix", default="")
    p.set_defaults(func=cmd_files_list)

    p = files_sub.add_parser("get", help="读取文件内容")
    _add_api(p)
    _add_kb(p)
    p.add_argument("--path", required=True, help="相对路径，如 wiki/index.md")
    p.add_argument("--out", help="写入本地文件（默认打印）")
    p.set_defaults(func=cmd_files_get)

    p = files_sub.add_parser("put", help="更新文件内容")
    _add_api(p)
    _add_kb(p)
    p.add_argument("--path", required=True)
    p.add_argument("--file", help="本机文件路径")
    p.add_argument("--content", help="直接传文本")
    p.set_defaults(func=cmd_files_put)

    # graph
    p_graph = sub.add_parser("graph", help="知识图谱")
    graph_sub = p_graph.add_subparsers(dest="graph_cmd", required=True)
    p = graph_sub.add_parser("get", help="获取图谱 JSON")
    _add_api(p)
    _add_kb(p)
    p.add_argument("--file", default="graph/graph.json")
    p.add_argument("--out", help="写入本地文件")
    p.set_defaults(func=cmd_graph_get)
    p = graph_sub.add_parser("build", help="重建图谱")
    _add_api(p)
    _add_kb(p)
    p.set_defaults(func=cmd_graph_build)

    # import / export
    p = sub.add_parser("export", help="导出知识库 ZIP 到本机")
    _add_api(p)
    _add_kb(p)
    p.add_argument("--out", required=True, help="本机输出路径，如 ./kb.zip")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("import-zip", help="向已有知识库导入 ZIP")
    _add_api(p)
    _add_kb(p)
    p.add_argument("--file", required=True)
    p.set_defaults(func=cmd_import_zip)

    p = sub.add_parser("import-kb", help="从 ZIP 创建并导入知识库")
    _add_api(p)
    p.add_argument("--file", required=True)
    p.set_defaults(func=cmd_import_kb)

    p = sub.add_parser("import-dir", help="从服务端目录导入 raw（路径须对 API 进程可见）")
    _add_api(p)
    _add_kb(p)
    p.add_argument("--source-dir", required=True)
    p.set_defaults(func=cmd_import_dir)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.api = args.api.rstrip("/")
    args.func(args)


if __name__ == "__main__":
    main()
