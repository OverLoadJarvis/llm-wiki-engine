#!/usr/bin/env python3
"""
Convert PDF or arXiv sources to Markdown for the raw/ directory.

Usage:
    python tools/pdf2md.py <input> [--output raw/papers/output.md] [--backend auto]

Inputs:
    arXiv ID      →  2401.12345
    arXiv URL     →  https://arxiv.org/abs/2401.12345
    Local PDF     →  /path/to/paper.pdf

Backends:
    auto          →  arXiv inputs use arxiv2md; PDFs use marker (fallback: pymupdf4llm)
    arxiv2md      →  Best for arXiv papers (uses structured source, not PDF)
    marker        →  Best for complex multi-column academic PDFs
    pymupdf4llm   →  Fast, lightweight, no GPU — good for native-text PDFs

Examples:
    python tools/pdf2md.py 2401.12345
    python tools/pdf2md.py https://arxiv.org/abs/2401.12345
    python tools/pdf2md.py paper.pdf --backend marker
    python tools/pdf2md.py paper.pdf -o raw/papers/my-paper.md
"""

import argparse
import importlib
import os
import re
import subprocess
import sys
from pathlib import Path

from tools.logger import get_logger, setup_logging

logger = get_logger(__name__)

REPO_ROOT = Path(__file__).parent.parent
DEFAULT_OUTPUT_DIR = REPO_ROOT / "raw" / "papers"

ARXIV_PATTERNS = [
    re.compile(r"^(\d{4}\.\d{4,5})(v\d+)?$"),                          # 2401.12345
    re.compile(r"arxiv\.org/abs/(\d{4}\.\d{4,5})(v\d+)?"),              # URL form
    re.compile(r"arxiv\.org/pdf/(\d{4}\.\d{4,5})(v\d+)?"),              # PDF URL
]


def extract_arxiv_id(source: str) -> str | None:
    """Return arXiv ID if input looks like an arXiv reference, else None."""
    for pattern in ARXIV_PATTERNS:
        m = pattern.search(source)
        if m:
            return m.group(1)
    return None


def check_dependency(package: str, pip_name: str | None = None) -> bool:
    """Check if a Python package is importable."""
    try:
        importlib.import_module(package)
        return True
    except ImportError:
        return False


def install_hint(pip_name: str) -> str:
    return f"  Install with: pip install {pip_name}"


# ─── Backend: arxiv2md ──────────────────────────────────────────────

def convert_arxiv(arxiv_id: str, output: Path) -> Path:
    """Convert arXiv paper using arxiv2md (structured source, not PDF)."""
    pip_name = "arxiv2markdown"
    if not check_dependency("arxiv2md", pip_name):
        logger.error("arxiv2md not installed.\n%s", install_hint(pip_name))
        sys.exit(1)

    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["arxiv2md", arxiv_id, "-o", str(output)]
    logger.info("  Running: %s", ' '.join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        logger.error("arxiv2md failed:\n%s", result.stderr)
        sys.exit(1)

    logger.info("  Converted arXiv %s -> %s", arxiv_id, output.relative_to(REPO_ROOT))
    return output


# ─── Backend: marker ────────────────────────────────────────────────

def convert_marker(pdf_path: Path, output: Path) -> Path:
    """Convert PDF using marker (high-fidelity, handles complex layouts)."""
    pip_name = "marker-pdf"
    if not check_dependency("marker", pip_name):
        logger.error("marker not installed.\n%s", install_hint(pip_name))
        sys.exit(1)

    output.parent.mkdir(parents=True, exist_ok=True)
    # marker outputs to a directory; we move the result to the target path
    tmp_dir = output.parent / f".marker_tmp_{output.stem}"
    cmd = ["marker_single", str(pdf_path), "--output_dir", str(tmp_dir)]
    logger.info("  Running: %s", ' '.join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        logger.error("marker failed:\n%s", result.stderr)
        sys.exit(1)

    # marker creates <pdf_name>/<pdf_name>.md inside output_dir
    md_files = list(tmp_dir.rglob("*.md"))
    if not md_files:
        logger.error("marker produced no markdown output.")
        sys.exit(1)

    # Move first .md to target, clean up
    md_files[0].rename(output)
    import shutil
    shutil.rmtree(tmp_dir, ignore_errors=True)

    logger.info("  Converted %s -> %s", pdf_path.name, output.relative_to(REPO_ROOT))
    return output


# ─── Backend: pymupdf4llm ───────────────────────────────────────────

def convert_pymupdf(pdf_path: Path, output: Path) -> Path:
    """Convert PDF using pymupdf4llm (fast, lightweight, native-text PDFs)."""
    pip_name = "pymupdf4llm"
    if not check_dependency("pymupdf4llm", pip_name):
        logger.error("pymupdf4llm not installed.\n%s", install_hint(pip_name))
        sys.exit(1)

    import pymupdf4llm

    output.parent.mkdir(parents=True, exist_ok=True)
    md_text = pymupdf4llm.to_markdown(str(pdf_path))
    output.write_text(md_text, encoding="utf-8")

    logger.info("  Converted %s -> %s", pdf_path.name, output.relative_to(REPO_ROOT))
    return output


# ─── Auto-detect & dispatch ─────────────────────────────────────────

BACKENDS = {
    "arxiv2md": convert_arxiv,
    "marker": convert_marker,
    "pymupdf4llm": convert_pymupdf,
}


def slugify(name: str) -> str:
    """Turn a filename or arXiv ID into a safe kebab-case slug."""
    name = Path(name).stem if "." in name else name
    name = re.sub(r"[^\w\s-]", "", name.lower())
    return re.sub(r"[\s_]+", "-", name).strip("-")


def resolve_output(source: str, arxiv_id: str | None, output_arg: str | None) -> Path:
    """Determine the output path."""
    if output_arg:
        p = Path(output_arg)
        return p if p.is_absolute() else REPO_ROOT / p

    if arxiv_id:
        slug = slugify(arxiv_id)
    else:
        slug = slugify(Path(source).stem)

    return DEFAULT_OUTPUT_DIR / f"{slug}.md"


def main():
    parser = argparse.ArgumentParser(
        description="Convert PDF/arXiv to Markdown for raw/",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("input", help="arXiv ID, arXiv URL, or path to a PDF file")
    parser.add_argument("-o", "--output", help="Output .md path (default: raw/papers/<slug>.md)")
    parser.add_argument(
        "-b", "--backend",
        choices=["auto", "arxiv2md", "marker", "pymupdf4llm"],
        default="auto",
        help="Conversion backend (default: auto-detect)",
    )
    args = parser.parse_args()

    setup_logging(level="INFO")

    arxiv_id = extract_arxiv_id(args.input)
    output = resolve_output(args.input, arxiv_id, args.output)
    backend = args.backend

    logger.info("\npdf2md — LLM Wiki Agent")
    logger.info("  Input:   %s", args.input)
    logger.info("  Output:  %s", output.relative_to(REPO_ROOT))

    # ── Auto-select backend ──
    if backend == "auto":
        if arxiv_id:
            backend = "arxiv2md"
        elif check_dependency("marker"):
            backend = "marker"
        elif check_dependency("pymupdf4llm"):
            backend = "pymupdf4llm"
        else:
            logger.error("\nNo conversion backend found.")
            logger.error("Install one of:")
            logger.error("  pip install arxiv2markdown   # for arXiv papers")
            logger.error("  pip install marker-pdf       # for complex PDFs")
            logger.error("  pip install pymupdf4llm      # for simple/fast PDF conversion")
            sys.exit(1)

    logger.info("  Backend: %s", backend)
    logger.info("")

    # ── Dispatch ──
    if backend == "arxiv2md":
        if not arxiv_id:
            logger.error("Error: arxiv2md backend requires an arXiv ID or URL.")
            sys.exit(1)
        convert_arxiv(arxiv_id, output)
    else:
        pdf_path = Path(args.input)
        if not pdf_path.exists():
            logger.error("Error: file not found: %s", args.input)
            sys.exit(1)
        BACKENDS[backend](pdf_path, output)

    logger.info("\nDone. Now ingest with:")
    logger.info("  python tools/ingest.py %s", output.relative_to(REPO_ROOT))
    logger.info("  — or in your agent: ingest %s", output.relative_to(REPO_ROOT))


if __name__ == "__main__":
    main()
