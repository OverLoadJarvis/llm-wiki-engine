"""Chat librarian agent: persona, tools, LangGraph ReAct, SSE event stream."""
from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Annotated, Literal, Sequence, TypedDict

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import StructuredTool
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from storage.db import WikiStorage
from tools.llm_config import get_resolved
from tools.logger import get_logger
from tools.thinking import split_thinking, strip_thinking
from tools.utils import configure_langfuse_tracing

logger = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PERSONA_PATH = REPO_ROOT / "prompts" / "librarian.md"
PAGE_CONTENT_LIMIT = 6000
SEARCH_RESULT_LIMIT = 20
MAX_AGENT_STEPS = 12  # ~5 tool loops

ALLOWED_PREFIXES = ("wiki/", "raw/")


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def _normalize_rel_path(path: str) -> str:
    p = (path or "").replace("\\", "/").strip().lstrip("/")
    while "//" in p:
        p = p.replace("//", "/")
    parts = [x for x in p.split("/") if x and x != "."]
    if ".." in parts:
        raise ValueError("path must not contain '..'")
    p = "/".join(parts)
    if not p.startswith(ALLOWED_PREFIXES):
        raise ValueError(f"path must start with wiki/ or raw/, got: {path!r}")
    return p


def load_persona(db: WikiStorage, kb_id: int) -> str:
    """Global librarian.md, overridden by wiki/agent.md when present."""
    base = ""
    if DEFAULT_PERSONA_PATH.is_file():
        base = DEFAULT_PERSONA_PATH.read_text(encoding="utf-8").strip()
    override = db.get_file_text_by_path(kb_id, "wiki/agent.md")
    if override and override.strip():
        # Strip simple frontmatter if present
        text = override.strip()
        if text.startswith("---"):
            end = text.find("\n---", 3)
            if end != -1:
                text = text[end + 4 :].strip()
        logger.info("Chat persona: using wiki/agent.md override for kb_id=%s", kb_id)
        return text
    if base:
        logger.info("Chat persona: using default librarian.md for kb_id=%s", kb_id)
        return base
    return (
        "你是该知识库的管理员。需要事实时使用工具查阅 wiki/ 与 raw/；"
        "问候与闲聊可直接回复，不要编造库中不存在的内容。"
    )


def _truncate(text: str, limit: int = PAGE_CONTENT_LIMIT) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n\n…(truncated, total {len(text)} chars)"


def build_tools(db: WikiStorage, kb_id: int) -> list[StructuredTool]:
    """Read-only tools scoped to one knowledge base."""

    def query_kb(question: str) -> str:
        """综合检索知识库并生成带依据的答案。适合需要跨多页总结的问题。"""
        from wiki_engine.query import QueryWorkflow

        q = (question or "").strip()
        if not q:
            return "错误：question 不能为空"
        logger.info("chat tool query_kb: kb_id=%s, question_len=%d", kb_id, len(q))
        try:
            answer = QueryWorkflow(db).query(kb_id, q, save=False)
            return _truncate(answer or "(空回答)", PAGE_CONTENT_LIMIT)
        except Exception as e:
            logger.exception("query_kb failed: kb_id=%s", kb_id)
            return f"查询失败: {e}"

    def get_overview() -> str:
        """读取知识库总览 wiki/overview.md。"""
        content = db.get_file_text_by_path(kb_id, "wiki/overview.md")
        if not content:
            return "wiki/overview.md 不存在或为空。知识库可能尚未构建。"
        return _truncate(content)

    def get_page(path: str) -> str:
        """读取本知识库中 wiki/ 或 raw/ 下的指定文件内容。path 示例：wiki/concepts/Foo.md 或 raw/doc.md"""
        try:
            rel = _normalize_rel_path(path)
        except ValueError as e:
            return f"非法路径: {e}"
        content = db.get_file_text_by_path(kb_id, rel)
        if content is None:
            return f"未找到文件: {rel}"
        return _truncate(content)

    def list_index() -> str:
        """返回 wiki/index.md 索引内容，用于了解知识库有哪些主题与页面。"""
        content = db.get_file_text_by_path(kb_id, "wiki/index.md")
        if not content:
            # Fallback: list wiki/ paths
            files = db.list_files(kb_id, "wiki/")
            if not files:
                return "索引为空，且 wiki/ 下没有文件。请先构建知识库。"
            lines = [f"- {f['relative_path']}" for f in files[:100]]
            return "wiki/index.md 缺失，文件列表：\n" + "\n".join(lines)
        return _truncate(content)

    def search_pages(keyword: str) -> str:
        """在本知识库的 wiki/ 与 raw/ 中按关键词全文搜索，返回路径与摘要。"""
        kw = (keyword or "").strip()
        if not kw:
            return "错误：keyword 不能为空"
        try:
            hits = db.search(kb_id, kw)
        except Exception as e:
            logger.warning("search_pages failed: %s", e)
            return f"搜索失败: {e}"
        filtered = [
            h
            for h in hits
            if str(h.get("relative_path") or "").startswith(ALLOWED_PREFIXES)
        ][:SEARCH_RESULT_LIMIT]
        if not filtered:
            return f"未找到与 {kw!r} 相关的 wiki/ 或 raw/ 页面。"
        lines = []
        for h in filtered:
            path = h.get("relative_path") or ""
            snip = (h.get("snippet") or "").replace("<mark>", "").replace("</mark>", "")
            lines.append(f"- {path}: {snip}")
        return "\n".join(lines)

    return [
        StructuredTool.from_function(query_kb, name="query_kb"),
        StructuredTool.from_function(get_overview, name="get_overview"),
        StructuredTool.from_function(get_page, name="get_page"),
        StructuredTool.from_function(list_index, name="list_index"),
        StructuredTool.from_function(search_pages, name="search_pages"),
    ]


def _tool_params_schema(tool: StructuredTool) -> dict[str, Any]:
    """Build OpenAI-compatible JSON Schema for a StructuredTool."""
    schema: Any = None
    if getattr(tool, "args_schema", None) is not None:
        schema = tool.args_schema
    elif hasattr(tool, "tool_call_schema"):
        schema = tool.tool_call_schema

    if schema is None:
        params: dict[str, Any] = {"type": "object", "properties": {}}
    elif isinstance(schema, dict):
        params = dict(schema)
    elif hasattr(schema, "model_json_schema"):
        params = schema.model_json_schema()
    else:
        params = {"type": "object", "properties": {}}

    # OpenAI tools expect JSON Schema without some pydantic extras
    params.pop("title", None)
    return params


def _tools_openai_schema(tools: Sequence[StructuredTool]) -> list[dict[str, Any]]:
    out = []
    for t in tools:
        out.append(
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description or t.name,
                    "parameters": _tool_params_schema(t),
                },
            }
        )
    return out


def _lc_to_openai_messages(messages: Sequence[BaseMessage]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for m in messages:
        if isinstance(m, SystemMessage):
            result.append({"role": "system", "content": m.content})
        elif isinstance(m, HumanMessage):
            result.append({"role": "user", "content": m.content})
        elif isinstance(m, AIMessage):
            item: dict[str, Any] = {"role": "assistant", "content": m.content or ""}
            if m.tool_calls:
                item["tool_calls"] = [
                    {
                        "id": tc.get("id") or f"call_{tc['name']}",
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc.get("args") or {}, ensure_ascii=False),
                        },
                    }
                    for tc in m.tool_calls
                ]
            result.append(item)
        elif isinstance(m, ToolMessage):
            result.append(
                {
                    "role": "tool",
                    "tool_call_id": m.tool_call_id,
                    "content": m.content if isinstance(m.content, str) else json.dumps(m.content),
                }
            )
        else:
            result.append({"role": "user", "content": str(getattr(m, "content", m))})
    return result


def _call_agent_llm(
    messages: Sequence[BaseMessage],
    tools: Sequence[StructuredTool],
) -> AIMessage:
    """One agent turn via litellm (Langfuse callbacks apply)."""
    from litellm import completion

    configure_langfuse_tracing()
    cfg = get_resolved()
    model = cfg["model"]
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": _lc_to_openai_messages(messages),
        "tools": _tools_openai_schema(tools),
        "tool_choice": "auto",
        "extra_body": {"enable_thinking": False},
        "headers": {"Accept-Encoding": "identity"},
        "metadata": {
            "trace_name": "chat_librarian",
            "generation_name": "librarian_agent",
            "tags": ["chat_agent"],
        },
    }
    if cfg.get("base_url"):
        kwargs["api_base"] = cfg["base_url"]
    if cfg.get("api_key"):
        kwargs["api_key"] = cfg["api_key"]

    logger.info(
        "Librarian agent LLM: model=%s, messages=%d, tools=%d",
        model,
        len(messages),
        len(tools),
    )
    resp = completion(**kwargs)
    choice = resp.choices[0].message
    content = choice.content or ""
    tool_calls = []
    raw_tcs = getattr(choice, "tool_calls", None) or []
    for tc in raw_tcs:
        fn = tc.function
        try:
            args = json.loads(fn.arguments or "{}")
        except json.JSONDecodeError:
            args = {"_raw": fn.arguments}
        tool_calls.append(
            {
                "id": getattr(tc, "id", None) or f"call_{fn.name}",
                "name": fn.name,
                "args": args,
                "type": "tool_call",
            }
        )
    return AIMessage(content=content, tool_calls=tool_calls)


def build_graph(db: WikiStorage, kb_id: int):
    tools = build_tools(db, kb_id)
    tool_node = ToolNode(tools)
    persona = load_persona(db, kb_id)
    kb = db.get_kb(kb_id)
    kb_name = (kb or {}).get("name") or str(kb_id)
    system = (
        f"{persona}\n\n"
        f"当前知识库：id={kb_id}, name={kb_name}。\n"
        f"你只能访问该知识库的 wiki/ 与 raw/ 路径。"
    )

    def agent_node(state: AgentState) -> dict[str, Any]:
        msgs = list(state["messages"])
        if not msgs or not isinstance(msgs[0], SystemMessage):
            msgs = [SystemMessage(content=system)] + msgs
        else:
            msgs[0] = SystemMessage(content=system)
        ai = _call_agent_llm(msgs, tools)
        raw = ai.content if isinstance(ai.content, str) else ""
        body, thinking = split_thinking(raw)
        kwargs: dict[str, Any] = {}
        if thinking:
            kwargs["thinking"] = thinking
        return {
            "messages": [
                AIMessage(
                    content=body,
                    tool_calls=ai.tool_calls,
                    additional_kwargs=kwargs,
                )
            ]
        }

    def should_continue(state: AgentState) -> Literal["tools", "end"]:
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "tools"
        return "end"

    g = StateGraph(AgentState)
    g.add_node("agent", agent_node)
    g.add_node("tools", tool_node)
    g.set_entry_point("agent")
    g.add_conditional_edges("agent", should_continue, {"tools": "tools", "end": END})
    g.add_edge("tools", "agent")
    return g.compile()


def _client_messages_to_lc(messages: list[dict[str, str]]) -> list[BaseMessage]:
    out: list[BaseMessage] = []
    for m in messages:
        role = (m.get("role") or "user").lower()
        # Defense: strip think tags even if a client sent raw model output
        content = strip_thinking(m.get("content") or "")
        if role == "system":
            continue  # persona injected by server
        if role == "assistant":
            out.append(AIMessage(content=content))
        else:
            out.append(HumanMessage(content=content))
    return out


def stream_librarian_events(
    db: WikiStorage,
    kb_id: int,
    messages: list[dict[str, str]],
) -> Iterator[dict[str, Any]]:
    """Yield SSE-oriented dict events: token | tool_start | tool_end | done | error."""
    kb = db.get_kb(kb_id)
    if not kb:
        yield {"event": "error", "error": f"知识库不存在: {kb_id}"}
        yield {"event": "done"}
        return

    graph = build_graph(db, kb_id)
    lc_messages = _client_messages_to_lc(messages)
    if not lc_messages:
        yield {"event": "error", "error": "messages 不能为空"}
        yield {"event": "done"}
        return

    logger.info(
        "Chat librarian start: kb_id=%s, history_msgs=%d",
        kb_id,
        len(lc_messages),
    )

    try:
        for update in graph.stream(
            {"messages": lc_messages},
            stream_mode="updates",
            config={"recursion_limit": MAX_AGENT_STEPS},
        ):
            if not isinstance(update, dict):
                continue
            for node_name, payload in update.items():
                if not isinstance(payload, dict):
                    continue
                new_msgs = payload.get("messages") or []
                for msg in new_msgs:
                    if isinstance(msg, AIMessage):
                        if msg.tool_calls:
                            for tc in msg.tool_calls:
                                yield {
                                    "event": "tool_start",
                                    "name": tc.get("name"),
                                    "input": tc.get("args") or {},
                                }
                        text = msg.content if isinstance(msg.content, str) else ""
                        thinking = ""
                        extra = getattr(msg, "additional_kwargs", None) or {}
                        if isinstance(extra, dict):
                            thinking = extra.get("thinking") or ""
                        # Fallback if tags somehow remained in content
                        if not thinking and text:
                            text, thinking = split_thinking(text)
                        if text or thinking:
                            yield {
                                "event": "token",
                                "content": text,
                                "thinking": thinking,
                            }
                    elif isinstance(msg, ToolMessage):
                        preview = msg.content if isinstance(msg.content, str) else str(msg.content)
                        if len(preview) > 500:
                            preview = preview[:500] + "…"
                        yield {
                            "event": "tool_end",
                            "name": msg.name or "tool",
                            "output_preview": preview,
                        }
        yield {"event": "done"}
        logger.info("Chat librarian done: kb_id=%s", kb_id)
    except Exception as e:
        logger.exception("Chat librarian failed: kb_id=%s", kb_id)
        yield {"event": "error", "error": str(e)}
        yield {"event": "done"}
