import os
import sys
import re
import hashlib
from pathlib import Path
from collections import defaultdict

REPO_ROOT = Path(__file__).parent.parent

try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env", override=True)
except ImportError:
    pass
WIKI_DIR = REPO_ROOT / "wiki"
LOG_FILE = WIKI_DIR / "log.md"
INDEX_FILE = WIKI_DIR / "index.md"
OVERVIEW_FILE = WIKI_DIR / "overview.md"


def call_llm(prompt: str, model_env: str = "LLM_MODEL", default_model: str = "claude-3-5-sonnet-latest", max_tokens: int = 4096, validate_json: bool = False) -> str:
    """
    调用LLM模型，返回模型回复
    
    Args:
        prompt: 提示词
        model_env: 环境变量名称，用于获取模型名称
        default_model: 默认模型名称
        max_tokens: 最大生成token数
        validate_json: 是否校验返回内容为合法JSON，若校验失败则自动重试（最多5次，最后一次跳过校验）
    
    Returns:
        模型回复内容
    """
    try:
        from litellm import completion
    except ImportError:
        print("Error: litellm not installed. Run: pip install litellm")
        sys.exit(1)
    
    model = os.getenv(model_env, default_model)

    kwargs = {
        "model": model,
        "extra_body": {"enable_thinking": False},
    }
    
    if max_tokens:
        kwargs["max_tokens"] = max_tokens
    
    api_base = os.getenv("OPENAI_API_BASE")
    api_key = os.getenv("OPENAI_API_KEY")
    
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
    
    for attempt in range(1, max_retries + 1):
        kwargs["messages"] = [{"role": "system", "content": current_prompt}]
        response = completion(**kwargs)
        content = response.choices[0].message.content
        
        # 最后一次不校验，直接返回
        if not validate_json or attempt == max_retries:
            return content
        
        # JSON 格式校验：复用 parse_json_from_response 处理 markdown 围栏等情况
        try:
            parse_json_from_response(content)
            return content
        except (ValueError, json.JSONDecodeError) as e:
            current_prompt = (
                f"{prompt}\n\n"
                f"【上次生成的JSON格式校验失败，请修正】\n"
                f"错误信息：{e}\n"
                f"你的上次回复：\n{content}\n\n"
                f"请重新生成，确保输出合法的JSON格式。"
            )
    
    return content  # 兜底，理论上不会走到这里


def read_file(path: Path) -> str:
    """读取文件内容，如果文件不存在返回空字符串"""
    return path.read_text(encoding="utf-8") if path.exists() else ""


def write_file(path: Path, content: str, verbose: bool = False):
    """写入文件内容，自动创建父目录"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if verbose:
        print(f"  wrote: {path.relative_to(REPO_ROOT)}")


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


def update_index(new_entry: str, section: str = "Sources"):
    """
    更新Wiki索引，添加新条目
    
    Args:
        new_entry: 新条目内容
        section: 要添加到的章节名称
    """
    content = read_file(INDEX_FILE)
    if not content:
        content = "# Wiki Index\n\n## Overview\n- [Overview](overview.md) — living synthesis\n\n## Sources\n\n## Entities\n\n## Concepts\n\n## Syntheses\n"
    
    section_header = f"## {section}"
    if section_header in content:
        content = content.replace(section_header + "\n", section_header + "\n" + new_entry + "\n")
    else:
        content += f"\n{section_header}\n{new_entry}\n"
    
    write_file(INDEX_FILE, content)
