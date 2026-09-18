#!/usr/bin/env python3
"""LLM Wiki Engine REST 客户端（仅标准库）。"""

from __future__ import annotations

import json
import mimetypes
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

DEFAULT_API = "http://127.0.0.1:5000"


def api_base(override: str | None = None) -> str:
    if override:
        return override.rstrip("/")
    return os.environ.get("LLM_WIKI_API", DEFAULT_API).rstrip("/")


def multipart(
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


def request_json(
    method: str,
    url: str,
    *,
    data: bytes | None = None,
    content_type: str | None = None,
    timeout: int = 600,
) -> Any:
    headers = {"Accept": "application/json"}
    if content_type:
        headers["Content-Type"] = content_type
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            if not raw:
                return {}
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"raw": raw}
    except HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {e.code} {url}\n{detail}") from e
    except URLError as e:
        raise SystemExit(f"请求失败: {url}\n{e}") from e


def request_text(
    method: str,
    url: str,
    *,
    data: bytes | None = None,
    content_type: str | None = None,
    timeout: int = 600,
) -> str:
    headers = {"Accept": "*/*"}
    if content_type:
        headers["Content-Type"] = content_type
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {e.code} {url}\n{detail}") from e
    except URLError as e:
        raise SystemExit(f"请求失败: {url}\n{e}") from e


def request_bytes(
    method: str,
    url: str,
    *,
    timeout: int = 600,
) -> bytes:
    req = Request(url, method=method, headers={"Accept": "*/*"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {e.code} {url}\n{detail}") from e
    except URLError as e:
        raise SystemExit(f"请求失败: {url}\n{e}") from e


def dump(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def qs(**kwargs: Any) -> str:
    items = {k: v for k, v in kwargs.items() if v is not None}
    if not items:
        return ""
    return "?" + urlencode(items)


def encode_path(rel: str) -> str:
    return "/".join(quote(part, safe="") for part in rel.replace("\\", "/").split("/") if part)
