"""全局常量与配置

定义引擎中使用的文件扩展名、颜色方案等常量。
"""

from pathlib import Path

# 项目根目录
REPO_ROOT = Path(__file__).parent.parent

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
