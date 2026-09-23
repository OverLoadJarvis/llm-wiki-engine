"""Unit tests for chat librarian path safety and persona loading."""
from __future__ import annotations

import pytest

from wiki_engine.chat_agent import (
    _normalize_rel_path,
    _tools_openai_schema,
    load_persona,
)


def test_normalize_allows_wiki_and_raw():
    assert _normalize_rel_path("wiki/concepts/Foo.md") == "wiki/concepts/Foo.md"
    assert _normalize_rel_path("/raw/a.md") == "raw/a.md"


def test_normalize_rejects_traversal_and_other_roots():
    with pytest.raises(ValueError):
        _normalize_rel_path("wiki/../raw/x.md")
    with pytest.raises(ValueError):
        _normalize_rel_path("graph/x.json")


def test_load_persona_default(tmp_path, monkeypatch):
    persona = tmp_path / "librarian.md"
    persona.write_text("DEFAULT PERSONA", encoding="utf-8")
    monkeypatch.setattr("wiki_engine.chat_agent.DEFAULT_PERSONA_PATH", persona)

    class FakeDb:
        def get_file_text_by_path(self, kb_id, path):
            return None

    assert load_persona(FakeDb(), 1) == "DEFAULT PERSONA"


def test_load_persona_override(tmp_path, monkeypatch):
    persona = tmp_path / "librarian.md"
    persona.write_text("DEFAULT", encoding="utf-8")
    monkeypatch.setattr("wiki_engine.chat_agent.DEFAULT_PERSONA_PATH", persona)

    class FakeDb:
        def get_file_text_by_path(self, kb_id, path):
            if path == "wiki/agent.md":
                return "---\ntitle: x\n---\nOVERRIDE"
            return None

    assert load_persona(FakeDb(), 1) == "OVERRIDE"


def test_tools_openai_schema_handles_pydantic_tool_call_schema():
    """tool_call_schema may be a Pydantic model class, not a dict."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    class Args(BaseModel):
        question: str = Field(description="q")

    tool = StructuredTool.from_function(
        lambda question: question,
        name="query_kb",
        description="answer",
        args_schema=Args,
    )
    # Simulate newer langchain exposing tool_call_schema as model class
    if not hasattr(tool, "tool_call_schema"):
        tool.tool_call_schema = Args  # type: ignore[attr-defined]

    schemas = _tools_openai_schema([tool])
    assert len(schemas) == 1
    params = schemas[0]["function"]["parameters"]
    assert isinstance(params, dict)
    assert params.get("type") == "object"
    assert "title" not in params
    assert "question" in params.get("properties", {})
