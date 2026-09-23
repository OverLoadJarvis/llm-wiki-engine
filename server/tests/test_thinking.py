"""Tests for tools.thinking split / strip."""
from __future__ import annotations

from tools.thinking import split_thinking, strip_thinking


def test_split_closed_think():
    content, thinking = split_thinking("<think>plan</think>\n\nHello")
    assert thinking == "plan"
    assert content == "Hello"


def test_split_thinking_tag_case_insensitive():
    content, thinking = split_thinking("<THINKING>x</THINKING>Body")
    assert thinking == "x"
    assert content == "Body"


def test_merge_multiple_blocks():
    content, thinking = split_thinking(
        "<think>a</think>mid<thinking>b</thinking>\n\nfinal"
    )
    assert thinking == "a\n\nb"
    assert content == "mid\n\nfinal"


def test_unclosed_open_is_all_thinking():
    content, thinking = split_thinking("intro\n<think>\nrest of draft")
    assert content == "intro"
    assert thinking == "rest of draft"


def test_empty_and_whitespace_thinking_omitted_from_parts():
    content, thinking = split_thinking("<think>  </think>ok")
    assert thinking == ""
    assert content == "ok"


def test_strip_thinking():
    assert strip_thinking("<think>x</think>y") == "y"
