"""Langfuse tracing is enabled only when host and both keys are present."""
from __future__ import annotations

import tools.utils as utils


class _LiteLLM:
    success_callback = None
    failure_callback = None


def test_base_url_alias_enables_langfuse(monkeypatch):
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)
    monkeypatch.setenv("LANGFUSE_BASE_URL", "http://192.168.226.58:3000/")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.setattr(utils, "_langfuse_configured", False)
    monkeypatch.setattr(utils, "_langfuse_skip_logged", False)
    monkeypatch.setitem(__import__("sys").modules, "litellm", _LiteLLM)

    utils.configure_langfuse_tracing()

    assert __import__("os").environ["LANGFUSE_HOST"] == "http://192.168.226.58:3000"
    assert _LiteLLM.success_callback == ["langfuse_otel"]
    assert _LiteLLM.failure_callback == ["langfuse_otel"]
    assert utils._langfuse_configured is True


def test_missing_keys_skips_langfuse(monkeypatch):
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)
    monkeypatch.delenv("LANGFUSE_BASE_URL", raising=False)
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.setattr(utils, "_langfuse_configured", False)
    monkeypatch.setattr(utils, "_langfuse_skip_logged", False)

    utils.configure_langfuse_tracing()

    assert utils._langfuse_configured is False
    assert utils._langfuse_skip_logged is True
