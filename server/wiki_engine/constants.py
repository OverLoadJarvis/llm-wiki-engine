"""全局常量与配置

定义引擎中使用的文件扩展名、颜色方案等常量。
"""

from pathlib import Path
import re

# 后端工程根目录 (server/)
REPO_ROOT = Path(__file__).resolve().parent.parent

# 格式规范文件路径
SCHEMA_FILE = REPO_ROOT / "FORMATS.md"

# markitdown 可转换的文件扩展名
CONVERTIBLE_EXTENSIONS = {
    ".pdf", ".docx", ".pptx", ".xlsx", ".xls",
    ".html", ".htm", ".txt", ".csv", ".json", ".xml",
    ".rst", ".rtf", ".epub", ".ipynb",
    ".yaml", ".yml", ".tsv",
    ".wav", ".mp3",
}

# 所有支持的文件扩展名（含 Markdown）
ALL_SUPPORTED_EXTENSIONS = {".md"} | CONVERTIBLE_EXTENSIONS

# ── 图谱可视化颜色 ──────────────────────────────────────────────

TYPE_COLORS = {
    "source": "#4CAF50",
    "entity": "#2196F3",
    "concept": "#FF9800",
    "synthesis": "#9C27B0",
    "unknown": "#9E9E9E",
}

EDGE_COLORS = {
    "EXTRACTED": "#555555",
    "INFERRED": "#FF5722",
    "AMBIGUOUS": "#BDBDBD",
}

COMMUNITY_COLORS = [
    "#E91E63", "#00BCD4", "#8BC34A", "#FF5722", "#673AB7",
    "#FFC107", "#009688", "#F44336", "#3F51B5", "#CDDC39",
]

# ── 图谱缓存路径（SQLite 内的虚拟路径） ─────────────────────────

GRAPH_CACHE_PATH = "graph/.cache.json"
GRAPH_CHECKPOINT_PATH = "graph/.inferred_edges.jsonl"

# ── 外部文件上传默认目录 ──────────────────────────────────────

DEFAULT_UPLOAD_DIR = REPO_ROOT / "uploads"
"""外部系统上传文件的默认本地目录，按项目名称分子文件夹存储。"""

# ── wiki/index.md 节标题（与 FORMATS.md「索引格式」一致，一律中文展示）──
# 路径与 frontmatter type 仍用英文：sources/entities/concepts/syntheses、
# type: source|entity|concept|synthesis —— 那是机器标识，不进索引标题。

INDEX_SECTION_OVERVIEW = "全局概览"
INDEX_SECTION_SOURCES = "来源文档"
INDEX_SECTION_ENTITIES = "实体页"
INDEX_SECTION_CONCEPTS = "概念页"
INDEX_SECTION_SYNTHESIS = "综合页"

# 规范标题 → 历史别名（读写时归一到规范标题）
# 别名覆盖：早期英文草稿、复数、旧中文短名
INDEX_SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    INDEX_SECTION_OVERVIEW: (
        INDEX_SECTION_OVERVIEW,
        "Overview",
    ),
    INDEX_SECTION_SOURCES: (
        INDEX_SECTION_SOURCES,
        "Sources",
        "源文档",  # 旧默认参数
    ),
    INDEX_SECTION_ENTITIES: (
        INDEX_SECTION_ENTITIES,
        "Entities",
    ),
    INDEX_SECTION_CONCEPTS: (
        INDEX_SECTION_CONCEPTS,
        "Concepts",
    ),
    INDEX_SECTION_SYNTHESIS: (
        INDEX_SECTION_SYNTHESIS,
        "Synthesis",  # FORMATS 旧稿 / 早期实现
        "Syntheses",
        "Comprehensive",  # helpers 曾用模板
        "综合",  # query 曾查找的短名
    ),
}

EMPTY_INDEX_CONTENT = (
    "# Wiki Index\n\n"
    f"## {INDEX_SECTION_OVERVIEW}\n"
    "- [全局概览](overview.md) — 知识库全局总结\n\n"
    f"## {INDEX_SECTION_SOURCES}\n\n"
    f"## {INDEX_SECTION_ENTITIES}\n\n"
    f"## {INDEX_SECTION_CONCEPTS}\n\n"
    f"## {INDEX_SECTION_SYNTHESIS}\n"
)


def resolve_index_section(section: str) -> str:
    """将节名（含历史别名）归一为 FORMATS.md 规范标题。"""
    for canonical, aliases in INDEX_SECTION_ALIASES.items():
        if section == canonical or section in aliases:
            return canonical
    return section


def normalize_index_section_headers(content: str) -> str:
    """把 index.md 中的历史节标题改写为规范标题。

    按整行 ``## …`` 匹配，避免短别名（如「综合」）误伤规范名（「综合页」）。
    别名按长度降序替换，进一步降低前缀冲突。
    """
    for canonical, aliases in INDEX_SECTION_ALIASES.items():
        ordered = sorted(
            (a for a in aliases if a != canonical),
            key=len,
            reverse=True,
        )
        for alias in ordered:
            content = re.sub(
                rf"(?m)^## {re.escape(alias)}[ \t]*$",
                f"## {canonical}",
                content,
            )
    return content

