"""健康检查与代码检查工作流模块

提供两种知识库质量检查功能：
- **健康检查**（health_check）：纯确定性结构检查，零 LLM 调用
- **代码检查**（lint）：包含 LLM 语义分析的内容质量检查

类:
    HealthWorkflow — 健康检查与代码检查工作流
"""

import re
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from storage.db import WikiStorage
from wiki_engine.helpers import append_log
from tools.utils import call_llm, extract_wikilinks, strip_frontmatter


class HealthWorkflow:
    """健康检查与代码检查工作流。

    健康检查是快速的结构完整性检查，适合每次会话开始时运行；
    代码检查是深度内容质量检查，包含 LLM 语义分析，适合定期运行。

    Args:
        db: WikiStorage 数据库实例
    """

    def __init__(self, db: WikiStorage) -> None:
        self.db = db

    # ══════════════════════════════════════════════════════════════
    # 健康检查（零 LLM 调用）
    # ══════════════════════════════════════════════════════════════

    def health_check(self, project_id: int) -> dict[str, Any]:
        """结构健康检查（无 LLM 调用，纯确定性检查）。

        检查项：
            - **空/存根文件**：除 frontmatter 外内容过少的页面
            - **索引同步**：index.md 中的链接与实际页面的对应关系
            - **日志覆盖**：源页面在 log.md 中是否有对应的 ingest 条目

        Args:
            project_id: 项目 ID

        Returns:
            健康检查结果字典，包含：
            - ``date``: 检查日期
            - ``project_name``: 项目名称
            - ``total_pages``: 页面总数
            - ``empty_files``: 空/存根文件列表
            - ``index_sync``: 索引同步问题
            - ``log_coverage``: 日志覆盖缺失列表

        Raises:
            ValueError: 项目不存在
        """
        proj = self.db.get_project(project_id)
        if not proj:
            raise ValueError(f"项目不存在: {project_id}")

        wiki_files = self.db.list_files(project_id, "wiki/")
        pages = [
            f for f in wiki_files
            if Path(f["relative_path"]).name
            not in ("index.md", "log.md", "lint-report.md")
        ]

        return {
            "date": date.today().isoformat(),
            "project_name": proj["name"],
            "total_pages": len(pages),
            "empty_files": self._check_empty_files(project_id, pages),
            "index_sync": self._check_index_sync(project_id, pages),
            "log_coverage": self._check_log_coverage(project_id),
        }

    def _check_empty_files(
        self, project_id: int, pages: list[dict], threshold: int = 100
    ) -> list[dict]:
        """检查空文件和存根文件。

        Args:
            project_id: 项目 ID
            pages: 页面记录列表
            threshold: 正文最小字节数阈值，低于此值视为存根

        Returns:
            空/存根文件信息列表，按正文长度升序排列
        """
        results = []
        for p in pages:
            raw = self.db.get_file_text_by_path(project_id, p["relative_path"]) or ""
            body = strip_frontmatter(raw)
            if len(body) < threshold:
                results.append({
                    "path": p["relative_path"],
                    "total_bytes": len(raw),
                    "body_bytes": len(body),
                    "status": "empty" if len(body) == 0 else "stub",
                })
        results.sort(key=lambda x: x["body_bytes"])
        return results

    def _check_index_sync(
        self, project_id: int, pages: list[dict]
    ) -> dict[str, list[str]]:
        """检查索引与磁盘页面的同步状态。

        Args:
            project_id: 项目 ID
            pages: 页面记录列表

        Returns:
            包含两个键的字典：
            - ``in_index_not_on_disk``: 索引中有但磁盘上没有的路径
            - ``on_disk_not_in_index``: 磁盘上有但索引中没有的路径
        """
        index_content = self.db.get_file_text_by_path(project_id, "wiki/index.md") or ""
        index_links = set(re.findall(r"\[.*?\]\(([^)]+\.md)\)", index_content))
        meta_pages = {"overview.md"}

        index_paths: set[str] = set()
        for link in index_links:
            if Path(link).name not in meta_pages:
                index_paths.add(f"wiki/{link}")

        disk_paths: set[str] = {
            p["relative_path"] for p in pages
            if Path(p["relative_path"]).name not in meta_pages
        }

        return {
            "in_index_not_on_disk": sorted(index_paths - disk_paths),
            "on_disk_not_in_index": sorted(disk_paths - index_paths),
        }

    def _check_log_coverage(self, project_id: int) -> list[dict]:
        """检查日志覆盖情况。

        对比 wiki/sources/ 下的源页面与 wiki/log.md 中的 ingest 条目，
        找出缺少日志记录的源页面。

        Args:
            project_id: 项目 ID

        Returns:
            缺少日志记录的源页面信息列表
        """
        log_content = self.db.get_file_text_by_path(project_id, "wiki/log.md") or ""
        logged_titles = set(
            m.group(1).strip().lower()
            for m in re.finditer(
                r"^## \[\d{4}-\d{2}-\d{2}\] ingest \| (.+)$",
                log_content,
                re.MULTILINE,
            )
        )

        source_files = self.db.list_files(project_id, "wiki/sources/")
        missing = []
        for s in source_files:
            slug = Path(s["relative_path"]).stem.lower().replace("-", " ").replace("_", " ")
            content = self.db.get_file_text_by_path(project_id, s["relative_path"]) or ""
            title_match = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', content, re.MULTILINE)
            fm_title = title_match.group(1).strip().lower() if title_match else ""

            if slug not in logged_titles and fm_title not in logged_titles:
                missing.append({
                    "path": s["relative_path"],
                    "slug": Path(s["relative_path"]).stem,
                    "title": fm_title or Path(s["relative_path"]).stem,
                })
        return missing

    # ══════════════════════════════════════════════════════════════
    # 代码检查（包含 LLM 语义分析）
    # ══════════════════════════════════════════════════════════════

    def lint(self, project_id: int, save: bool = False) -> str:
        """内容质量检查（包含 LLM 语义分析）。

        检查项：
            - **孤立页面**：无入站 wikilink 的页面
            - **损坏链接**：指向不存在页面的 wikilink
            - **缺失实体**：被 3 次以上引用但没有独立页面的实体
            - **稀疏页面**：出站 wikilink 少于 2 个的页面
            - **语义检查**（LLM）：矛盾、过时内容、数据缺口、需深化的概念

        Args:
            project_id: 项目 ID
            save: 是否将报告保存到 wiki/lint-report.md

        Returns:
            Markdown 格式的检查报告

        Raises:
            ValueError: 项目不存在
        """
        proj = self.db.get_project(project_id)
        if not proj:
            raise ValueError(f"项目不存在: {project_id}")

        wiki_files = self.db.list_files(project_id, "wiki/")
        pages = [
            f for f in wiki_files
            if Path(f["relative_path"]).name
            not in ("index.md", "log.md", "lint-report.md")
        ]

        if not pages:
            return "知识库为空，无需检查。"

        today = date.today().isoformat()
        print(f"  检查 {len(pages)} 个 wiki 页面...")

        orphans = self._find_orphans(project_id, pages)
        broken = self._find_broken_links(project_id, pages)
        missing_entities = self._find_missing_entities(project_id, pages)
        sparse_pages = self._check_link_density(project_id, pages)

        print(f"    孤立页面: {len(orphans)}")
        print(f"    损坏链接: {len(broken)}")
        print(f"    缺失实体: {len(missing_entities)}")
        print(f"    稀疏页面: {len(sparse_pages)}")

        # 语义检查（LLM） 
        # todo - 仅检查前 20 个页面
        sample = pages[:20]
        pages_context = ""
        for p in sample:
            content = self.db.get_file_text_by_path(project_id, p["relative_path"]) or ""
            pages_context += f"\n\n### {p['relative_path']}\n{content[:1500]}"

        print("  运行语义检查 (LLM)...")
        prompt = f"""你正在检查一个企业知识库 Wiki。审查以下页面并识别:
1. 页面之间的矛盾（冲突的主张）
2. 过时内容（已被新源文档取代的摘要）
3. 数据缺口（Wiki 无法回答的重要问题 —— 建议具体来源）
4. 被提及但缺乏深度的概念

Wiki 页面（{len(sample)} 个页面样本）:
{pages_context}

返回一个 Markdown 检查报告，包含以下部分:
## 矛盾
## 过时内容
## 数据缺口和建议来源
## 需要深化的概念

请具体指明涉及的页面和主张。
"""
        semantic_report = call_llm(prompt, max_tokens=8192*10)

        report_lines = [
            f"# Wiki 检查报告 — {today}",
            f"项目: {proj['name']}",
            "",
            f"扫描了 {len(pages)} 个页面。",
            "",
            "## 结构性问题",
            "",
        ]

        if orphans:
            report_lines.append("### 孤立页面（无入站链接）")
            for path in orphans:
                report_lines.append(f"- `{path}`")
            report_lines.append("")

        if broken:
            report_lines.append("### 损坏的 Wiki 链接")
            for page_path, link in broken:
                report_lines.append(f"- `{page_path}` 链接到 `[[{link}]]` — 页面不存在")
            report_lines.append("")

        if missing_entities:
            report_lines.append("### 缺失实体页面（被提及 3 次以上但无独立页面）")
            for name in missing_entities:
                report_lines.append(f"- `[[{name}]]`")
            report_lines.append("")

        if not orphans and not broken and not missing_entities and not sparse_pages:
            report_lines.append("未发现结构性问题。")
            report_lines.append("")

        if sparse_pages:
            report_lines.append(f"### 稀疏页面 — 出站链接不足 ({len(sparse_pages)} 个页面)")
            report_lines.append("以下页面的出站 wikilink 少于 2 个:")
            report_lines.append("")
            for sp in sparse_pages:
                existing = ", ".join(f"`[[{l}]]`" for l in sp["links"]) if sp["links"] else "—"
                report_lines.append(f"- `{sp['path']}` ({sp['outbound_links']} 个链接: {existing})")
            report_lines.append("")

        report_lines.append("---")
        report_lines.append("")
        report_lines.append(semantic_report)

        report = "\n".join(report_lines)

        if save:
            self.db.add_file(project_id, "wiki/lint-report.md", report)
            print(f"  报告已保存到 wiki/lint-report.md")

        append_log(
            self.db,
            project_id,
            f"## [{today}] lint | Wiki 健康检查\n\n运行了代码检查。详见 lint-report.md。",
        )

        return report

    def _find_orphans(
        self, project_id: int, pages: list[dict]
    ) -> list[str]:
        """查找孤立页面（无入站 wikilink 的页面）。

        Args:
            project_id: 项目 ID
            pages: 页面记录列表

        Returns:
            孤立页面的相对路径列表（排除 overview.md）
        """
        inbound: dict[str, int] = defaultdict(int)
        existing_stems = {Path(p["relative_path"]).stem.lower() for p in pages}

        for p in pages:
            content = self.db.get_file_text_by_path(project_id, p["relative_path"]) or ""
            for link in extract_wikilinks(content):
                link_stem = link.lower()
                if "/" in link:
                    link_stem = Path(link).stem.lower()
                if link_stem in existing_stems:
                    for ep in pages:
                        if Path(ep["relative_path"]).stem.lower() == link_stem:
                            inbound[ep["relative_path"]] += 1

        return [
            p["relative_path"]
            for p in pages
            if inbound.get(p["relative_path"], 0) == 0
            and Path(p["relative_path"]).name != "overview.md"
        ]

    def _find_broken_links(
        self, project_id: int, pages: list[dict]
    ) -> list[tuple[str, str]]:
        """查找损坏的 wikilink（指向不存在页面的链接）。

        Args:
            project_id: 项目 ID
            pages: 页面记录列表

        Returns:
            (页面路径, 链接目标) 元组列表
        """
        # 文件名就是索引名
        existing_stems = {Path(p["relative_path"]).stem.lower() for p in pages}
        print("existing_stems:", existing_stems)
        broken = []
        for p in pages:
            content = self.db.get_file_text_by_path(project_id, p["relative_path"]) or ""
            for link in extract_wikilinks(content):
                link_stem = link.lower()
                if "/" in link:
                    link_stem = Path(link).stem.lower()
                if link_stem not in existing_stems:
                    broken.append((p["relative_path"], link))
        print("broken:", broken)
        return broken

    def _find_missing_entities(
        self, project_id: int, pages: list[dict]
    ) -> list[str]:
        """查找缺失实体页面（被 3 次以上引用但没有独立页面的实体）。

        Args:
            project_id: 项目 ID
            pages: 页面记录列表

        Returns:
            缺失实体名称列表
        """
        mention_counts: dict[str, int] = defaultdict(int)
        existing_stems = {Path(p["relative_path"]).stem.lower() for p in pages}

        for p in pages:
            content = self.db.get_file_text_by_path(project_id, p["relative_path"]) or ""
            links = extract_wikilinks(content)
            for link in links:
                link_stem = link.lower()
                if "/" in link:
                    link_stem = Path(link).stem.lower()
                if link_stem not in existing_stems:
                    mention_counts[link] += 1

        return [name for name, count in mention_counts.items() if count >= 3]

    def _check_link_density(
        self, project_id: int, pages: list[dict], min_outbound: int = 2
    ) -> list[dict]:
        """检查链接密度不足的页面。

        Args:
            project_id: 项目 ID
            pages: 页面记录列表
            min_outbound: 最小出站链接数阈值

        Returns:
            稀疏页面信息列表，按出站链接数升序排列
        """
        results = []
        for p in pages:
            if Path(p["relative_path"]).name == "overview.md":
                continue
            content = self.db.get_file_text_by_path(project_id, p["relative_path"]) or ""
            links = extract_wikilinks(content)
            unique_links = set(link.lower() for link in links)
            if len(unique_links) < min_outbound:
                results.append({
                    "path": p["relative_path"],
                    "outbound_links": len(unique_links),
                    "links": sorted(unique_links),
                })
        results.sort(key=lambda x: x["outbound_links"])
        return results
