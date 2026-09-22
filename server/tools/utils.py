import os
import sys
import re
import hashlib
from collections.abc import Callable
from pathlib import Path
from collections import defaultdict
from typing import Any

from tools.logger import get_logger

logger = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env", override=True)
except ImportError:
    pass
WIKI_DIR = REPO_ROOT / "wiki"
LOG_FILE = WIKI_DIR / "log.md"
INDEX_FILE = WIKI_DIR / "index.md"
OVERVIEW_FILE = WIKI_DIR / "overview.md"

_langfuse_configured = False
_langfuse_skip_logged = False


def configure_langfuse_tracing() -> None:
    """Turn on LiteLLM → Langfuse OTEL when public/secret keys and a host are set.

    LiteLLM 1.88 reads LANGFUSE_HOST (or LANGFUSE_OTEL_HOST). LANGFUSE_BASE_URL
    is accepted as an alias and copied into LANGFUSE_HOST when that is unset.
    """
    global _langfuse_configured, _langfuse_skip_logged
    if _langfuse_configured:
        return

    host = (os.getenv("LANGFUSE_HOST") or os.getenv("LANGFUSE_BASE_URL") or "").strip().rstrip("/")
    public_key = (os.getenv("LANGFUSE_PUBLIC_KEY") or "").strip()
    secret_key = (os.getenv("LANGFUSE_SECRET_KEY") or "").strip()
    if not host or not public_key or not secret_key:
        if not _langfuse_skip_logged:
            logger.info(
                "Langfuse tracing skipped: host_set=%s, public_key_set=%s, secret_key_set=%s",
                bool(host),
                bool(public_key),
                bool(secret_key),
            )
            _langfuse_skip_logged = True
        return

    if not (os.getenv("LANGFUSE_HOST") or "").strip():
        os.environ["LANGFUSE_HOST"] = host

    try:
        import litellm

        litellm.success_callback = ["langfuse_otel"]
        litellm.failure_callback = ["langfuse_otel"]
    except Exception:
        logger.exception("Failed to enable Langfuse tracing: host=%s", host)
        return

    _langfuse_configured = True
    logger.info("Langfuse tracing enabled: host=%s, callback=langfuse_otel", host)


def call_llm(
    prompt: str,
    model_env: str = "LLM_MODEL",
    default_model: str = "claude-3-5-sonnet-latest",
    max_tokens: int = 4096,
    validate_json: bool = False,
    validate_parsed: Callable[[Any], None] | None = None,
) -> str:
    """
    调用LLM模型，返回模型回复
    
    Args:
        prompt: 提示词
        model_env: 环境变量名称，用于获取模型名称
        default_model: 默认模型名称
        max_tokens: 最大生成token数
        validate_json: 是否校验返回内容为合法JSON，若校验失败则自动重试（最多5次；
            未提供 validate_parsed 时，最后一次跳过校验直接返回）
        validate_parsed: 可选；对 parse_json_from_response 结果做业务校验，失败则重试。
            提供时隐含 JSON 校验；全部重试仍失败则抛出 RuntimeError（不返回坏内容）
    
    Returns:
        模型回复内容

    Raises:
        RuntimeError: 提供了 validate_parsed 且重试耗尽仍校验失败
    """
    try:
        from litellm import completion
    except ImportError:
        logger.error("litellm not installed. Run: pip install litellm")
        sys.exit(1)

    configure_langfuse_tracing()

    from tools.llm_config import get_resolved

    cfg = get_resolved(default_model=default_model)
    if model_env == "LLM_MODEL_FAST":
        model = cfg["model_fast"] or default_model
    else:
        model = cfg["model"] or default_model

    kwargs = {
        "model": model,
        "extra_body": {"enable_thinking": False},
    }
    
    if max_tokens:
        kwargs["max_tokens"] = max_tokens
    
    api_base = cfg["base_url"]
    api_key = cfg["api_key"]
    
    if api_base:
        kwargs["api_base"] = api_base
    if api_key:
        kwargs["api_key"] = api_key
    
    # 设置 Accept-Encoding: identity 告诉服务器不要返回压缩响应
    # 绕过某些服务器 Content-Encoding 头与实际数据不匹配的问题
    kwargs["headers"] = {"Accept-Encoding": "identity"}
    
    import json
    
    current_prompt = prompt
    max_retries = 5
    need_validate = validate_json or validate_parsed is not None
    content = ""
    
    logger.info("Calling LLM: model=%s, prompt_len=%d, api_base=%s", model, len(prompt), api_base or "(default)")
    for attempt in range(1, max_retries + 1):
        kwargs["messages"] = [{"role": "system", "content": current_prompt}]
        try:
            response = completion(**kwargs)
            content = response.choices[0].message.content
        except Exception:
            logger.exception("LLM call failed: model=%s, attempt=%d", model, attempt)
            raise
        
        if not need_validate:
            return content

        # 未提供业务校验时，最后一次保持历史行为：跳过校验直接返回
        if validate_parsed is None and attempt == max_retries:
            logger.debug("Last attempt, not validating JSON: %s", content[:200])
            return content
        
        try:
            data = parse_json_from_response(content)
            if validate_parsed is not None:
                validate_parsed(data)
            return content
        except (ValueError, json.JSONDecodeError, TypeError) as e:
            logger.warning(
                "LLM response validation failed: model=%s, attempt=%d/%d, error=%s",
                model,
                attempt,
                max_retries,
                e,
            )
            if attempt == max_retries:
                if validate_parsed is not None:
                    raise RuntimeError(
                        f"LLM 响应校验失败（已重试 {max_retries} 次）: {e}"
                    ) from e
                return content
            current_prompt = (
                f"{prompt}\n\n"
                f"【上次生成的JSON校验失败，请修正】\n"
                f"错误信息：{e}\n"
                f"你的上次回复：\n{content}\n\n"
                f"请重新生成，确保输出合法的JSON，并满足全部必填字段要求。"
            )
            logger.debug("LLM Attempt %d: %s", attempt, current_prompt[:200])
    
    return content  # 兜底，理论上不会走到这里


def call_llm_stream(prompt: str, model_env: str = "LLM_MODEL", default_model: str = "claude-3-5-sonnet-latest", max_tokens: int = 4096):
    """
    流式调用LLM模型，逐块yield模型回复

    Args:
        prompt: 提示词
        model_env: 环境变量名称，用于获取模型名称
        default_model: 默认模型名称
        max_tokens: 最大生成token数

    Yields:
        str: 模型回复的文本块
    """
    try:
        from litellm import completion
    except ImportError:
        logger.error("litellm not installed. Run: pip install litellm")
        sys.exit(1)

    configure_langfuse_tracing()

    from tools.llm_config import get_resolved

    cfg = get_resolved(default_model=default_model)
    if model_env == "LLM_MODEL_FAST":
        model = cfg["model_fast"] or default_model
    else:
        model = cfg["model"] or default_model

    kwargs = {
        "model": model,
        "messages": [{"role": "system", "content": prompt}],
        "stream": True,
        "extra_body": {"enable_thinking": False},
    }

    if max_tokens:
        kwargs["max_tokens"] = max_tokens

    api_base = cfg["base_url"]
    api_key = cfg["api_key"]

    if api_base:
        kwargs["api_base"] = api_base
    if api_key:
        kwargs["api_key"] = api_key

    kwargs["headers"] = {"Accept-Encoding": "identity"}

    logger.info("Calling LLM stream: model=%s, prompt_len=%d, api_base=%s", model, len(prompt), api_base or "(default)")
    try:
        response = completion(**kwargs)
        for chunk in response:
            if hasattr(chunk, 'choices') and chunk.choices:
                if hasattr(chunk.choices[0], 'delta') and chunk.choices[0].delta:
                    content = chunk.choices[0].delta.content or ""
                    if content:
                        yield content
    except Exception:
        logger.exception("LLM stream failed: model=%s", model)
        raise


def read_file(path: Path) -> str:
    """读取文件内容，如果文件不存在返回空字符串"""
    return path.read_text(encoding="utf-8") if path.exists() else ""


def write_file(path: Path, content: str, verbose: bool = False):
    """写入文件内容，自动创建父目录"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if verbose:
        logger.debug("  wrote: %s", path.relative_to(REPO_ROOT))


def sha256(text: str, truncate: int | None = None) -> str:
    """
    计算字符串的SHA-256哈希值
    
    Args:
        text: 输入文本
        truncate: 如果指定，返回哈希值的前N位
    
    Returns:
        哈希值字符串
    """
    hash_value = hashlib.sha256(text.encode()).hexdigest()
    if truncate:
        return hash_value[:truncate]
    return hash_value


def all_wiki_pages(exclude: set[str] | None = None) -> list[Path]:
    """
    获取所有wiki页面路径
    
    Args:
        exclude: 要排除的文件名集合，默认为 {"index.md", "log.md", "lint-report.md"}
    
    Returns:
        wiki目录下所有.md文件路径列表
    """
    if exclude is None:
        exclude = {"index.md", "log.md", "lint-report.md"}
    return [p for p in WIKI_DIR.rglob("*.md") if p.name not in exclude]


def extract_wikilinks(content: str) -> list[str]:
    """从页面内容中提取所有[[WikiLink]]"""
    return re.findall(r'\[\[([^\]]+)\]\]', content)


def append_log(entry: str):
    """追加日志条目到日志文件"""
    existing = read_file(LOG_FILE)
    write_file(LOG_FILE, entry.strip() + "\n\n" + existing)


def strip_frontmatter(content: str) -> str:
    """移除YAML frontmatter (--- ... ---)"""
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            return content[end + 3:].strip()
    return content.strip()


def extract_frontmatter_type(content: str) -> str:
    """从frontmatter中提取type字段"""
    match = re.search(r'^type:\s*(\S+)', content, re.MULTILINE)
    return match.group(1).strip('"\'') if match else "unknown"


def page_id(path: Path) -> str:
    """将wiki页面路径转换为页面ID（相对路径，不含.md扩展名）"""
    return path.relative_to(WIKI_DIR).as_posix().replace(".md", "")


def parse_json_from_response(text: str) -> dict:
    """
    从模型回复中解析JSON对象
    
    Args:
        text: 模型回复文本
    
    Returns:
        解析后的字典
    
    Raises:
        ValueError: 如果没有找到JSON对象
        json.JSONDecodeError: 如果JSON格式无效
    """
    import json
    
    # 移除markdown 代码围栏
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text.strip())

    # 查找最外层的JSON对象
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError("No JSON object found in response")
    return json.loads(match.group())


def build_wiki_context() -> str:
    """
    构建Wiki上下文，包含index、overview和最近的source页面
    
    Returns:
        合并后的wiki上下文字符串
    """
    parts = []
    if INDEX_FILE.exists():
        parts.append(f"## wiki/index.md\n{read_file(INDEX_FILE)}")
    if OVERVIEW_FILE.exists():
        parts.append(f"## wiki/overview.md\n{read_file(OVERVIEW_FILE)}")
    
    # 包含最近的5个source页面用于矛盾检查
    sources_dir = WIKI_DIR / "sources"
    if sources_dir.exists():
        recent = sorted(sources_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]
        for p in recent:
            parts.append(f"## {p.relative_to(REPO_ROOT)}\n{read_file(p)}")
    
    return "\n\n---\n\n".join(parts)


def update_index(new_entry: str, section: str = "来源文档"):
    """
    更新Wiki索引，添加新条目（文件系统版，与 FORMATS.md 索引格式一致）

    Args:
        new_entry: 新条目内容
        section: 要添加到的章节名称
    """
    from wiki_engine.constants import (
        EMPTY_INDEX_CONTENT,
        normalize_index_section_headers,
        resolve_index_section,
    )

    if not new_entry:
        return

    canonical = resolve_index_section(section)
    content = read_file(INDEX_FILE)
    if not content:
        content = EMPTY_INDEX_CONTENT
    else:
        content = normalize_index_section_headers(content)

    section_header = f"## {canonical}"
    if section_header in content:
        content = content.replace(
            section_header + "\n", section_header + "\n" + new_entry + "\n", 1
        )
    else:
        content += f"\n{section_header}\n{new_entry}\n"

    write_file(INDEX_FILE, content)
    logger.info("Updated filesystem index: section=%s entry_len=%d", canonical, len(new_entry))
