"""API smoke tests (no LLM calls). Run from server/: python -m pytest tests/test_api_smoke.py -q"""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app
from app.sse import format_sse, iter_dict_events

client = TestClient(app)


def test_list_kbs():
    r = client.get("/api/kbs")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_create_and_delete_kb():
    r = client.post("/api/kbs", json={"name": "_smoke_kb", "description": "smoke"})
    assert r.status_code == 201
    body = r.json()
    assert "id" in body
    kid = body["id"]

    r2 = client.get(f"/api/kbs/{kid}")
    assert r2.status_code == 200
    assert r2.json()["name"] == "_smoke_kb"

    r3 = client.delete(f"/api/kbs/{kid}")
    assert r3.status_code == 200
    assert r3.json().get("deleted") is True


def test_llm_settings_get():
    r = client.get("/api/settings/llm")
    assert r.status_code == 200
    data = r.json()
    assert "api_key_set" in data
    assert "api_key" not in data


def test_search_empty_query():
    r = client.post("/api/kbs", json={"name": "_smoke_search"})
    kid = r.json()["id"]
    try:
        s = client.get(f"/api/kbs/{kid}/search")
        assert s.status_code == 200
        assert s.json() == []
    finally:
        client.delete(f"/api/kbs/{kid}")


def test_sse_format_helper():
    frame = format_sse("done", {"result": {"ok": True}})
    assert frame.startswith("event: done\n")
    assert 'data: {"result": {"ok": true}}' in frame.replace(" ", "") or '"ok": true' in frame

    lines = list(iter_dict_events(iter([{"event": "start", "total": 2}])))
    assert lines[0].startswith("event: start\n")
    assert '"total": 2' in lines[0]
    assert '"event"' not in json.loads(lines[0].split("data: ", 1)[1].strip())


def test_openapi_has_core_paths():
    paths = client.get("/openapi.json").json()["paths"]
    for p in (
        "/api/kbs",
        "/api/settings/llm",
        "/api/kbs/{kb_id}/build",
        "/api/kbs/{kb_id}/query",
        "/api/kbs/{kb_id}/upload-file",
        "/api/external/upload",
    ):
        assert p in paths
