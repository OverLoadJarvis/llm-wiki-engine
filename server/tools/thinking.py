"""Split / strip model <think> and <thinking> blocks from assistant text."""
from __future__ import annotations

import re

# Closed pairs first; tag name must match on close.
_THINK_PAIR = re.compile(
    r"<(think|thinking)>([\s\S]*?)</\1>",
    re.IGNORECASE,
)
_THINK_OPEN = re.compile(r"<(think|thinking)>", re.IGNORECASE)
_THINK_CLOSE = re.compile(r"</(?:think|thinking)>", re.IGNORECASE)


def split_thinking(text: str) -> tuple[str, str]:
    """Split assistant text into (content, thinking).

    - Recognizes ``<think>`` and ``<thinking>`` (case-insensitive).
    - Merges all think blocks into one string (joined by blank lines).
    - Unclosed open tag: everything after it is treated as thinking (not content).
    """
    if not text:
        return "", ""

    parts: list[str] = []

    def _collect(match: re.Match[str]) -> str:
        chunk = (match.group(2) or "").strip()
        if chunk:
            parts.append(chunk)
        return ""

    content = _THINK_PAIR.sub(_collect, text)
    open_m = _THINK_OPEN.search(content)
    if open_m:
        rest = content[open_m.end() :].strip()
        if rest:
            parts.append(rest)
        content = content[: open_m.start()]
    content = _THINK_CLOSE.sub("", content).strip()
    thinking = "\n\n".join(parts)
    return content, thinking


def strip_thinking(text: str) -> str:
    """Return content only (thinking discarded)."""
    return split_thinking(text)[0]
