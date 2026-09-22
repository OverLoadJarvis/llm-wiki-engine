"""parse_json_from_response supports objects and arrays; validators enforce shape."""
from __future__ import annotations

import pytest

from tools.utils import (
    parse_json_from_response,
    require_json_object,
    require_string_list,
)


def test_parse_empty_array():
    assert parse_json_from_response("[]") == []


def test_parse_array_in_markdown_fence():
    assert parse_json_from_response('```json\n["concepts/Foo.md"]\n```') == [
        "concepts/Foo.md"
    ]


def test_parse_array_after_think_block():
    text = "<think>greeting only</think>\n\n```json\n[]\n```"
    assert parse_json_from_response(text) == []


def test_parse_object_still_works():
    assert parse_json_from_response('{"slug": "x", "entities": []}') == {
        "slug": "x",
        "entities": [],
    }


def test_no_json_raises():
    with pytest.raises(ValueError, match="No JSON"):
        parse_json_from_response("hello only")


def test_require_string_list_accepts_empty():
    require_string_list([])


def test_require_string_list_rejects_object():
    with pytest.raises(TypeError, match="array"):
        require_string_list({"paths": []})


def test_require_json_object_rejects_array():
    with pytest.raises(TypeError, match="object"):
        require_json_object([])
