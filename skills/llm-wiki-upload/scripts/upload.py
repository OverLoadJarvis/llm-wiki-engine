#!/usr/bin/env python3
"""通过 REST multipart 将本机文件上传到 LLM Wiki Engine（仅标准库）。"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import uuid
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_API = "http://127.0.0.1:5000"


def _api_base() -> str:
    return os.environ.get("LLM_WIKI_API", DEFAULT_API).rstrip("/")


def _multipart(
    fields: dict[str, str],
    files: Iterable[tuple[str, Path]],
) -> tuple[bytes, str]:
    boundary = f"----llmwiki{uuid.uuid4().hex}"
    body = bytearray()

    for name, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.extend(value.encode("utf-8"))
        body.extend(b"\r\n")

    for field_name, path in files:
        raw = path.read_bytes()
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(
            (
                f'Content-Disposition: form-data; name="{field_name}"; '
                f'filename="{path.name}"\r\n'
            ).encode("utf-8")
        )
        body.extend(f"Content-Type: {ctype}\r\n\r\n".encode())
        body.extend(raw)
        body.extend(b"\r\n")

    body.extend(f"--{boundary}--\r\n".encode())
    return bytes(body), f"multipart/form-data; boundary={boundary}"


def _request(
    method: str,
    url: str,
    data: bytes | None = None,
    content_type: str | None = None,
) -> dict:
    headers = {"Accept": "application/json"}
    if content_type:
        headers["Content-Type"] = content_type
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=300) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw else {}
    except HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {e.code} {url}\n{detail}") from e
    except URLError as e:
        raise SystemExit(f"请求失败: {url}\n{e}") from e


def list_kbs(base: str) -> None:
    result = _request("GET", f"{base}/api/kbs")
    print(json.dumps(result, ensure_ascii=False, indent=2))


def upload_by_id(base: str, kb_id: int, paths: list[Path], update: bool) -> None:
    # 接口每次只收一个 file；多文件循环上传，仅最后一次带增量更新。
    combined = []
    for i, p in enumerate(paths):
        do_update = update and i == len(paths) - 1
        body, ctype = _multipart({}, [("file", p)])
        qs = "true" if do_update else "false"
        url = f"{base}/api/kbs/{kb_id}/upload-file?update={qs}"
        print(f"[upload] kb_id={kb_id} file={p} update={do_update}", file=sys.stderr)
        combined.append(_request("POST", url, data=body, content_type=ctype))
    print(json.dumps(combined if len(combined) > 1 else combined[0], ensure_ascii=False, indent=2))


def upload_by_name(base: str, kb_name: str, paths: list[Path]) -> None:
    files = [("files", p) for p in paths]
    body, ctype = _multipart({"kb_name": kb_name}, files)
    url = f"{base}/api/external/upload"
    names = ", ".join(p.name for p in paths)
    print(f"[upload] kb_name={kb_name} files={names}", file=sys.stderr)
    print(json.dumps(_request("POST", url, data=body, content_type=ctype), ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="将本机文件上传到 LLM Wiki Engine")
    parser.add_argument("--api", default=_api_base(), help="API 根地址（或环境变量 LLM_WIKI_API）")
    parser.add_argument("--list-kbs", action="store_true", help="列出知识库后退出")
    parser.add_argument("--kb-id", type=int, help="目标知识库 ID")
    parser.add_argument("--kb-name", help="目标知识库名称（不存在则创建；走 /api/external/upload）")
    parser.add_argument("--file", action="append", dest="files", default=[], help="本机文件路径（可重复）")
    parser.add_argument("--update", action="store_true", help="上传后增量更新（仅 --kb-id 模式）")
    args = parser.parse_args()

    base = args.api.rstrip("/")

    if args.list_kbs:
        list_kbs(base)
        return

    paths = [Path(f).expanduser().resolve() for f in args.files]
    if not paths:
        parser.error("请至少指定一个 --file，或使用 --list-kbs")
    for p in paths:
        if not p.is_file():
            raise SystemExit(f"文件不存在: {p}")

    if args.kb_id is not None:
        upload_by_id(base, args.kb_id, paths, args.update)
    elif args.kb_name:
        if args.update:
            print("[warn] --kb-name 模式忽略 --update；增量更新请用 --kb-id", file=sys.stderr)
        upload_by_name(base, args.kb_name, paths)
    else:
        parser.error("请指定 --kb-id 或 --kb-name")


if __name__ == "__main__":
    main()
