"""知识图谱构建工作流模块

提供知识图谱的构建、推理、可视化与报告功能，包括：
- 从 wikilink 提取显式边
- LLM 语义推理隐式边（带 checkpoint/resume）
- Louvain 社区检测
- vis.js 交互式 HTML 可视化
- 图谱健康报告

类:
    GraphWorkflow — 知识图谱构建工作流
"""

import json
import re
import statistics
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from storage.db import WikiStorage
from wiki_engine.constants import (
    COMMUNITY_COLORS,
    EDGE_COLORS,
    GRAPH_CACHE_PATH,
    GRAPH_CHECKPOINT_PATH,
    TYPE_COLORS,
)
from wiki_engine.prompt import GRAPH_INFER_EDGE_PROMPT
from tools.utils import call_llm, extract_wikilinks, sha256
from tools.logger import get_logger

logger = get_logger(__name__)


class GraphWorkflow:
    """知识图谱构建工作流。

    负责从 Wiki 页面的 wikilink 中提取显式关系边，可选地通过 LLM
    推理隐式语义边，并生成可视化的知识图谱。

    Args:
        db: WikiStorage 数据库实例
    """

    def __init__(self, db: WikiStorage) -> None:
        self.db = db

    # ── 边 ID 生成 ─────────────────────────────────────────────────

    @staticmethod
    def edge_id(src: str, target: str, edge_type: str) -> str:
        """生成边的唯一标识符。

        Args:
            src: 源节点 ID
            target: 目标节点 ID
            edge_type: 边类型（EXTRACTED / INFERRED / AMBIGUOUS）

        Returns:
            格式为 ``"src->target:type"`` 的边 ID
        """
        return f"{src}->{target}:{edge_type}"

    # ── 社区检测 ───────────────────────────────────────────────────

    @staticmethod
    def detect_communities(nodes: list[dict], edges: list[dict]) -> dict[str, int]:
        """使用 Louvain 算法检测社区结构。

        需要 networkx 库。若未安装则返回空字典。

        Args:
            nodes: 节点列表
            edges: 边列表

        Returns:
            节点 ID 到社区编号的映射字典
        """
        try:
            import networkx as nx
            from networkx.algorithms import community as nx_community
        except ImportError:
            return {}

        G = nx.Graph()
        for n in nodes:
            G.add_node(n["id"])
        for e in edges:
            G.add_edge(e["from"], e["to"])

        if G.number_of_edges() == 0:
            return {}

        try:
            communities = nx_community.louvain_communities(G, seed=42)
            node_to_community = {}
            for i, comm in enumerate(communities):
                for node in comm:
                    node_to_community[node] = i
            return node_to_community
        except Exception:
            return {}

    # ── 图谱缓存（SQLite-backed） ──────────────────────────────────

    def load_graph_cache(self, project_id: int) -> dict:
        """从 SQLite 加载 SHA256 内容缓存。

        缓存记录每个页面的内容哈希和已推理的边，用于增量推理。

        Args:
            project_id: 项目 ID

        Returns:
            缓存字典，键为页面路径，值为 ``{"hash": ..., "edges": [...]}``
        """
        text = self.db.get_file_text_by_path(project_id, GRAPH_CACHE_PATH)
        if text:
            try:
                return json.loads(text)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def save_graph_cache(self, project_id: int, cache: dict) -> None:
        """将 SHA256 内容缓存保存到 SQLite。

        Args:
            project_id: 项目 ID
            cache: 缓存字典
        """
        content = json.dumps(cache, indent=2, ensure_ascii=False)
        self.db.add_file(project_id, GRAPH_CACHE_PATH, content)

    def load_checkpoint_edges(self, project_id: int) -> tuple[list[dict], set[str]]:
        """从 SQLite 加载之前推理的边和已完成的页面集合。

        用于 checkpoint/resume 机制，避免重复推理。

        Args:
            project_id: 项目 ID

        Returns:
            (已推理边列表, 已完成页面 ID 集合) 元组
        """
        edges = []
        completed = set()
        text = self.db.get_file_text_by_path(project_id, GRAPH_CHECKPOINT_PATH)
        if text:
            for line in text.splitlines():
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    completed.add(record["page_id"])
                    for edge in record.get("edges", []):
                        if not isinstance(edge, dict) or "from" not in edge or "to" not in edge:
                            continue
                        rel_type = edge.get("type", "INFERRED")
                        edges.append({
                            "id": edge.get("id", self.edge_id(edge["from"], edge["to"], rel_type)),
                            "from": edge["from"],
                            "to": edge["to"],
                            "type": rel_type,
                            "title": edge.get("title", edge.get("relationship", "")),
                            "label": edge.get("label", ""),
                            "color": edge.get("color", EDGE_COLORS.get(rel_type, EDGE_COLORS["INFERRED"])),
                            "confidence": float(edge.get("confidence", 0.7)),
                        })
                except (json.JSONDecodeError, KeyError):
                    continue
        return edges, completed

    def append_checkpoint_edge(self, project_id: int, page_id_str: str, edges: list[dict]) -> None:
        """将一个页面的推理边追加到 SQLite checkpoint。

        Args:
            project_id: 项目 ID
            page_id_str: 页面 ID 字符串
            edges: 该页面推理出的边列表
        """
        existing_text = self.db.get_file_text_by_path(project_id, GRAPH_CHECKPOINT_PATH) or ""
        record = {"page_id": page_id_str, "edges": edges, "ts": date.today().isoformat()}
        new_text = existing_text + json.dumps(record, ensure_ascii=False) + "\n"
        self.db.add_file(project_id, GRAPH_CHECKPOINT_PATH, new_text)

    def clear_graph_cache(self, project_id: int) -> None:
        """清除项目的所有图谱构建缓存。

        Args:
            project_id: 项目 ID
        """
        self.db.delete_file_by_path(project_id, GRAPH_CACHE_PATH)
        self.db.delete_file_by_path(project_id, GRAPH_CHECKPOINT_PATH)

    # ── 幽灵枢纽检测 ───────────────────────────────────────────────

    def find_phantom_hubs(self, project_id: int, pages: list[dict], min_refs: int = 2) -> list[dict]:
        """查找幽灵枢纽（被多个页面引用但不存在的页面）。

        这些是页面创建的强烈信号——多个页面通过 wikilink 引用了
        某个概念/实体，但该页面尚未创建。

        Args:
            project_id: 项目 ID
            pages: 页面记录列表
            min_refs: 最小引用次数阈值

        Returns:
            幽灵枢纽信息列表，按引用次数降序排列
        """
        existing_stems = {
            Path(p["relative_path"]).stem.lower() for p in pages
        }
        refs: dict[str, set[str]] = {}
        for p in pages:
            content = self.db.get_file_text_by_path(project_id, p["relative_path"]) or ""
            links = extract_wikilinks(content)
            src = p["relative_path"].replace("wiki/", "").replace(".md", "")
            for link in links:
                link_stem = Path(link).stem.lower() if "/" in link else link.lower()
                if link_stem not in existing_stems:
                    refs.setdefault(link, set()).add(src)

        phantoms = [
            {
                "name": name,
                "ref_count": len(sources),
                "referenced_by": sorted(sources),
            }
            for name, sources in refs.items()
            if len(sources) >= min_refs
        ]
        phantoms.sort(key=lambda x: x["ref_count"], reverse=True)
        return phantoms

    # ── 图谱健康报告 ───────────────────────────────────────────────

    def generate_graph_report(self, project_id: int, nodes: list[dict], edges: list[dict],
                               communities: dict[str, int]) -> str:
        """生成结构化的图谱健康报告。

        报告包含：
            - 健康摘要（边/节点比、孤立页面百分比、社区数量、链接密度）
            - 孤立节点列表
            - 神节点（度数 > μ+2σ 的枢纽页面）
            - 脆弱桥梁（仅通过 1 条边连接的社区对）
            - 社区概览

        Args:
            project_id: 项目 ID
            nodes: 节点列表
            edges: 边列表
            communities: 节点 ID 到社区编号的映射

        Returns:
            Markdown 格式的图谱健康报告
        """
        today = date.today().isoformat()
        n_nodes = len(nodes)
        n_edges = len(edges)

        if n_nodes == 0:
            return f"# Graph Insights Report — {today}\n\nWiki is empty — nothing to report.\n"

        try:
            import networkx as nx
        except ImportError:
            return f"# Graph Insights Report — {today}\n\nnetworkx not installed — analysis unavailable.\n"

        G = nx.Graph()
        for n in nodes:
            G.add_node(n["id"])
        for e in edges:
            G.add_edge(e["from"], e["to"])

        degrees = dict(G.degree())
        edges_per_node = n_edges / n_nodes if n_nodes else 0
        density = nx.density(G)

        if edges_per_node >= 2.0:
            health = "✅ healthy"
        elif edges_per_node >= 1.0:
            health = "⚠️ warning"
        else:
            health = "🔴 critical"

        orphans = sorted([n for n, d in degrees.items() if d == 0])
        orphan_count = len(orphans)
        orphan_pct = (orphan_count / n_nodes * 100) if n_nodes else 0

        deg_values = list(degrees.values())
        mean_deg = statistics.mean(deg_values) if deg_values else 0
        std_deg = statistics.stdev(deg_values) if len(deg_values) > 1 else 0
        god_threshold = mean_deg + 2 * std_deg
        god_nodes = sorted(
            [(n, d) for n, d in degrees.items() if d > god_threshold],
            key=lambda x: x[1],
            reverse=True,
        )

        community_count = len(set(communities.values())) if communities else 0
        comm_members: dict[int, list[str]] = {}
        for node_id, comm_id in communities.items():
            comm_members.setdefault(comm_id, []).append(node_id)

        cross_comm_edges: dict[tuple[int, int], list[dict]] = {}
        for e in edges:
            ca = communities.get(e["from"], -1)
            cb = communities.get(e["to"], -1)
            if ca >= 0 and cb >= 0 and ca != cb:
                key = (min(ca, cb), max(ca, cb))
                cross_comm_edges.setdefault(key, []).append(e)
        fragile_bridges = [
            (pair, edge_list[0])
            for pair, edge_list in sorted(cross_comm_edges.items())
            if len(edge_list) == 1
        ]

        lines = [
            f"# 图谱洞察报告 — {today}",
            "",
            "## 健康摘要",
            f"- **{n_nodes}** 个节点，**{n_edges}** 条边（{edges_per_node:.2f} 边/节点 — {health}）",
            f"- **{orphan_count}** 个孤立节点（{orphan_pct:.1f}%）— 目标：<10%",
            f"- **{community_count}** 个社区",
            f"- 链接密度：{density:.4f}",
            "",
            f"## 🔴 孤立节点（{orphan_count} 个页面，{orphan_pct:.1f}%）",
        ]
        if orphans:
            lines.append("这些页面没有图谱连接。考虑添加 [[wikilink]]：")
            for o in orphans:
                lines.append(f"- `{o}`")
        else:
            lines.append("没有孤立节点 — 非常好！")
        lines.append("")

        lines.append("## 🟡 神节点（枢纽页面）")
        if god_nodes:
            lines.append("这些节点承载了不成比例的连接度（度数 > μ+2σ）。请验证其内容是否完善：")
            lines.append("")
            lines.append("| 节点 | 度数 | 边占比 | 社区 |")
            lines.append("|---|---|---|---|")
            for node_id, deg in god_nodes:
                edge_pct = (deg / (2 * n_edges) * 100) if n_edges else 0
                comm = communities.get(node_id, -1)
                lines.append(f"| `{node_id}` | {deg} | {edge_pct:.1f}% | {comm} |")
        else:
            lines.append("未检测到神节点 — 度数分布均衡。")
        lines.append("")

        lines.append("## 🟡 脆弱桥梁")
        if fragile_bridges:
            lines.append("仅通过 1 条边连接的社区对 — 删除一条链接就会断开：")
            for (ca, cb), edge in fragile_bridges:
                lines.append(f"- 社区 {ca} ↔ 社区 {cb}，通过 `{edge['from']}` → `{edge['to']}`")
        else:
            lines.append("没有脆弱桥梁 — 所有社区连接都有冗余。")
        lines.append("")

        lines.append("## 🟢 社区概览")
        if comm_members:
            lines.append("")
            lines.append("| 社区 | 节点数 | 核心成员 |")
            lines.append("|---|---|---|")
            for comm_id in sorted(comm_members.keys()):
                members = comm_members[comm_id]
                members_sorted = sorted(members, key=lambda m: degrees.get(m, 0), reverse=True)
                key_members = ", ".join(members_sorted[:5])
                if len(members_sorted) > 5:
                    key_members += ", …"
                lines.append(f"| {comm_id} | {len(members)} | {key_members} |")
        else:
            lines.append("未检测到社区 — 图谱可能过于稀疏。")
        lines.append("")

        return "\n".join(lines)

    # ── 语义推理边 ─────────────────────────────────────────────────

    def build_inferred_edges(self, project_id: int, pages: list[dict], existing_edges: list[dict],
                              infer: bool = True, clean: bool = False, resume: bool = True) -> list[dict]:
        """通过 LLM 推理构建隐式语义边。

        对每个页面调用 LLM，识别与其它页面的隐式语义关系。
        支持 checkpoint/resume 机制和内容缓存，避免重复推理。

        Args:
            project_id: 项目 ID
            pages: 页面记录列表
            existing_edges: 已提取的显式边列表
            infer: 是否执行推理；若为 ``False`` 直接返回空列表
            clean: 是否清除缓存从头开始
            resume: 是否从上次中断处继续

        Returns:
            推理出的边列表（包含 INFERRED 和 AMBIGUOUS 类型）
        """
        if not infer:
            return []

        if clean:
            self.clear_graph_cache(project_id)
            logger.info("  cache cleared — rebuilding from scratch")

        checkpoint_edges, completed_ids = self.load_checkpoint_edges(project_id)
        if not resume:
            checkpoint_edges, completed_ids = [], set()

        new_edges = list(checkpoint_edges)

        cache = self.load_graph_cache(project_id)

        changed_pages = []
        for p in pages:
            content = self.db.get_file_text_by_path(project_id, p["relative_path"]) or ""
            h = sha256(content)
            pid = p["relative_path"].replace("wiki/", "").replace(".md", "")
            entry = cache.get(p["relative_path"])

            if pid in completed_ids:
                continue

            if isinstance(entry, dict) and entry.get("hash") == h:
                for rel in entry.get("edges", []):
                    rel_type = rel.get("type", "INFERRED")
                    confidence = float(rel.get("confidence", 0.7))
                    new_edges.append({
                        "id": self.edge_id(pid, rel["to"], rel_type),
                        "from": pid,
                        "to": rel["to"],
                        "type": rel_type,
                        "title": rel.get("relationship", ""),
                        "label": "",
                        "color": EDGE_COLORS.get(rel_type, EDGE_COLORS["INFERRED"]),
                        "confidence": confidence,
                    })
            else:
                changed_pages.append(p)

        if not changed_pages:
            logger.info("  no changed pages — skipping semantic inference")
            return new_edges

        total_pages = len(changed_pages)
        already_done = len(completed_ids)
        grand_total = total_pages + already_done
        logger.info("  inferring relationships for %d remaining pages (of %d total)...", total_pages, grand_total)

        node_list = "\n".join(
            f"- {p['relative_path'].replace('wiki/', '').replace('.md', '')} ({p.get('type', 'unknown')})"
            for p in pages
        )
        existing_edge_summary = "\n".join(
            f"- {e['from']} → {e['to']} (EXTRACTED)" for e in existing_edges[:30]
        )

        for i, p in enumerate(changed_pages, 1):
            full_content = self.db.get_file_text_by_path(project_id, p["relative_path"]) or ""
            src = p["relative_path"].replace("wiki/", "").replace(".md", "")
            global_idx = already_done + i
            logger.info("    [%d/%d] Inferring for '%s'...", global_idx, grand_total, src)

            prompt = GRAPH_INFER_EDGE_PROMPT.format(
                src=src,
                full_content=full_content[:2000],
                node_list=node_list,
                existing_edge_summary=existing_edge_summary,
            )
            page_edges = []
            valid_rels = []
            try:
                raw = call_llm(prompt, "LLM_MODEL_FAST", "claude-3-5-haiku-latest", max_tokens=8192*10)
                raw = raw.strip()

                if not raw:
                    logger.warning("-> Empty response received")
                    continue

                raw = raw.replace('\r\n', '\n').replace('\r', '\n')

                match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", raw)
                if match:
                    raw = match.group(0)
                else:
                    raw = re.sub(r"^```(?:json)?\s*", "", raw)
                    raw = re.sub(r"\s*```$", "", raw)

                raw = raw.strip()
                if not raw:
                    logger.warning("-> No JSON found in response")
                    continue

                try:
                    inferred = json.loads(raw)
                except json.JSONDecodeError as e:
                    logger.warning("-> JSON decode failed: %s", str(e)[:60])
                    logger.warning("   Attempting to fix invalid JSON...")
                    raw = re.sub(r',\s*([}\]])', r'\1', raw)
                    raw = re.sub(r'([{,])\s*([^{}\[\],:\s]+)\s*:', r'\1 "\2":', raw)
                    try:
                        inferred = json.loads(raw)
                        logger.info("   -> Fixed JSON successfully")
                    except json.JSONDecodeError as e2:
                        logger.warning("   -> Fix failed: %s", str(e2)[:60])
                        continue

                if isinstance(inferred, dict):
                    edges_list = inferred.get("edges", [])
                elif isinstance(inferred, list):
                    edges_list = inferred
                else:
                    edges_list = []

                for rel in edges_list:
                    if isinstance(rel, dict) and "to" in rel:
                        confidence = float(rel.get("confidence", 0.7))
                        rel_type = rel.get("type") or ("INFERRED" if confidence >= 0.7 else "AMBIGUOUS")
                        edge = {
                            "id": self.edge_id(src, rel["to"], rel_type),
                            "from": src,
                            "to": rel["to"],
                            "type": rel_type,
                            "title": rel.get("relationship", ""),
                            "label": "",
                            "color": EDGE_COLORS.get(rel_type, EDGE_COLORS["INFERRED"]),
                            "confidence": confidence,
                        }
                        page_edges.append(edge)
                        new_edges.append(edge)
                        valid_rels.append({
                            "to": rel["to"],
                            "relationship": rel.get("relationship", ""),
                            "confidence": confidence,
                            "type": rel_type,
                        })

                cache[p["relative_path"]] = {
                    "hash": sha256(full_content),
                    "edges": valid_rels,
                }
                self.append_checkpoint_edge(project_id, src, page_edges)
                logger.info("-> Found %d edges.", len(page_edges))
            except (json.JSONDecodeError, TypeError, ValueError) as jde:
                logger.warning("-> Invalid JSON: %s", str(jde)[:60])
            except Exception as e:
                err_msg = str(e).replace('\n', ' ')[:80]
                logger.error("-> %s", err_msg)

        self.save_graph_cache(project_id, cache)
        return new_edges

    # ── 边去重 ─────────────────────────────────────────────────────

    def deduplicate_edges(self, edges: list[dict]) -> list[dict]:
        """对边进行去重，保留同一对节点间置信度最高的边。

        Args:
            edges: 边列表

        Returns:
            去重后的边列表
        """
        best = {}
        for e in edges:
            a, b = e["from"], e["to"]
            key = (min(a, b), max(a, b))
            existing = best.get(key)
            if not existing or e.get("confidence", 0) > existing.get("confidence", 0):
                best[key] = e
        deduped = []
        for edge in best.values():
            rel_type = edge.get("type", "INFERRED")
            edge["id"] = edge.get("id", self.edge_id(edge["from"], edge["to"], rel_type))
            edge["color"] = edge.get("color", EDGE_COLORS.get(rel_type, EDGE_COLORS["INFERRED"]))
            edge["confidence"] = float(edge.get("confidence", 0.7 if rel_type != "EXTRACTED" else 1.0))
            edge.setdefault("title", "")
            edge.setdefault("label", "")
            deduped.append(edge)
        return deduped

    # ── HTML 可视化 ────────────────────────────────────────────────

    @staticmethod
    def render_graph_html(nodes: list[dict], edges: list[dict]) -> str:
        """生成 vis.js 交互式知识图谱 HTML 页面。

        生成的 HTML 是自包含的，包含 vis-network 库引用、
        赛博朋克风格 UI、节点搜索/过滤/高亮、内容抽屉等功能。

        Args:
            nodes: 节点列表
            edges: 边列表

        Returns:
            完整的 HTML 字符串
        """
        nodes_json = json.dumps(nodes, indent=2, ensure_ascii=False)
        edges_json = json.dumps(edges, indent=2, ensure_ascii=False)

        n_extracted = len([e for e in edges if e.get('type') == 'EXTRACTED'])
        n_inferred = len([e for e in edges if e.get('type') == 'INFERRED'])
        n_ambiguous = len([e for e in edges if e.get('type') == 'AMBIGUOUS'])

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>LLM Wiki — 知识图谱</title>
  <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    :root {{
      --bg: #0f1117;
      --sidebar-bg: #161822;
      --panel-bg: #1a1d2e;
      --border: #2a2d3e;
      --text: #e2e4f0;
      --text-dim: #8b8fa3;
      --accent: #6c63ff;
      --accent-hover: #7b73ff;
    }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
      background: var(--bg);
      color: var(--text);
      height: 100vh;
      overflow: hidden;
    }}
    #graph {{ width: 100vw; height: 100vh; }}
    .cyber-grid {{
      position: fixed;
      top: 0; left: 0; width: 100%; height: 100%;
      pointer-events: none; z-index: 0;
      background-image:
        linear-gradient(rgba(108, 99, 255, 0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(108, 99, 255, 0.03) 1px, transparent 1px);
      background-size: 50px 50px;
      animation: gridMove 20s linear infinite;
    }}
    @keyframes gridMove {{
      0% {{ background-position: 0 0; }}
      100% {{ background-position: 50px 50px; }}
    }}
    .cyber-particles {{
      position: fixed; top: 0; left: 0; width: 100%; height: 100%;
      pointer-events: none; z-index: 1; overflow: hidden;
    }}
    .particle {{
      position: absolute; width: 2px; height: 2px;
      background: rgba(108, 99, 255, 0.5); border-radius: 50%;
      box-shadow: 0 0 10px rgba(108, 99, 255, 0.5);
      animation: float 15s infinite;
    }}
    @keyframes float {{
      0%, 100% {{ transform: translateY(0) translateX(0); opacity: 0; }}
      10% {{ opacity: 1; }}
      90% {{ opacity: 1; }}
      100% {{ transform: translateY(-100vh) translateX(20px); opacity: 0; }}
    }}
    #controls {{
      position: fixed; top: 16px; left: 16px;
      background: rgba(22, 24, 34, 0.95); padding: 16px;
      border-radius: 12px; z-index: 10; max-width: 300px;
      backdrop-filter: blur(12px); border: 1px solid var(--border);
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    }}
    #controls h3 {{
      margin: 0 0 12px; font-size: 16px; letter-spacing: 0.5px;
      color: var(--accent); font-weight: 700;
    }}
    #search {{
      width: 100%; padding: 8px 12px; margin-bottom: 12px;
      background: var(--panel-bg); color: var(--text);
      border: 1px solid var(--border); border-radius: 8px;
      font-size: 13px; transition: border-color 0.2s;
    }}
    #search:focus {{ outline: none; border-color: var(--accent); }}
    .legend {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }}
    .legend-item {{
      display: flex; align-items: center; gap: 6px;
      padding: 4px 10px; background: var(--panel-bg);
      border-radius: 6px; font-size: 12px; border: 1px solid var(--border);
    }}
    .legend-dot {{ width: 10px; height: 10px; border-radius: 50%; }}
    #controls p {{ margin: 12px 0 0; font-size: 12px; color: var(--text-dim); line-height: 1.6; }}
    .filter-group {{ margin-top: 12px; padding-top: 10px; border-top: 1px solid var(--border); }}
    .filter-group label {{
      display: block; font-size: 12px; color: var(--text-dim);
      margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.5px;
    }}
    .slider-row {{ display: flex; align-items: center; gap: 10px; margin-top: 6px; }}
    .slider-row input[type=range] {{ flex: 1; accent-color: var(--accent); }}
    .slider-val {{
      font-size: 12px; color: var(--accent); min-width: 32px;
      text-align: right; font-weight: 600;
    }}
    .cb-row {{
      display: flex; align-items: center; gap: 8px;
      font-size: 12px; margin: 4px 0; cursor: pointer; padding: 4px 0;
    }}
    .cb-row input {{ accent-color: var(--accent); }}
    .cb-row span {{ display: inline-block; width: 16px; height: 2px; }}
    #drawer {{
      position: fixed; top: 0; right: 0;
      width: clamp(480px, 33vw, 720px); max-width: 100vw; height: 100vh;
      background: rgba(22, 24, 34, 0.98); border-left: 1px solid var(--border);
      box-shadow: -20px 0 60px rgba(0, 0, 0, 0.5); z-index: 20;
      display: none; flex-direction: column; backdrop-filter: blur(16px);
    }}
    #drawer.open {{ display: flex; animation: slideIn 0.3s ease-out; }}
    @keyframes slideIn {{ from {{ transform: translateX(100%); }} to {{ transform: translateX(0); }} }}
    #drawer-header {{ padding: 20px 20px 14px; border-bottom: 1px solid var(--border); }}
    #drawer-topline {{ display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }}
    #drawer-title {{ margin: 0; font-size: 22px; line-height: 1.2; color: var(--accent); font-weight: 700; }}
    #drawer-close {{
      background: transparent; color: var(--text-dim); border: 0;
      font-size: 28px; line-height: 1; cursor: pointer; padding: 0;
      transition: color 0.2s;
    }}
    #drawer-close:hover {{ color: var(--text); }}
    #drawer-meta {{ margin-top: 10px; font-size: 12px; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.5px; }}
    #drawer-path {{
      margin-top: 8px; font-size: 12px; color: var(--text-dim); word-break: break-all;
      background: var(--panel-bg); padding: 6px 10px; border-radius: 6px; border: 1px solid var(--border);
    }}
    #drawer-preview {{
      margin-top: 14px; font-size: 13px; color: var(--text); line-height: 1.6;
      padding: 12px; background: var(--panel-bg); border-radius: 8px; border: 1px solid var(--border);
    }}
    #drawer-related {{ padding: 14px 20px 0; font-size: 12px; color: var(--text-dim); }}
    #drawer-related-list {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }}
    .related-chip {{
      background: var(--panel-bg); color: var(--text); border: 1px solid var(--border);
      border-radius: 999px; font-size: 12px; padding: 6px 14px; cursor: pointer; transition: all 0.2s;
    }}
    .related-chip:hover {{ border-color: var(--accent); color: var(--accent); }}
    #drawer-content {{ flex: 1; min-height: 0; padding: 16px 20px 20px; overflow: auto; }}
    #drawer-markdown {{ color: var(--text); font-size: 14px; line-height: 1.72; }}
    #drawer-markdown h1, #drawer-markdown h2, #drawer-markdown h3,
    #drawer-markdown h4, #drawer-markdown h5, #drawer-markdown h6 {{
      margin: 1.2em 0 0.55em; line-height: 1.3; color: var(--accent); font-weight: 600;
    }}
    #drawer-markdown h1 {{ font-size: 26px; }}
    #drawer-markdown h2 {{ font-size: 22px; }}
    #drawer-markdown h3 {{ font-size: 18px; }}
    #drawer-markdown p {{ margin: 0 0 0.95em; }}
    #drawer-markdown ul, #drawer-markdown ol {{ margin: 0 0 1em 1.35em; padding: 0; }}
    #drawer-markdown li {{ margin: 0.35em 0; }}
    #drawer-markdown hr {{ border: 0; border-top: 1px solid var(--border); margin: 1.2em 0; }}
    #drawer-markdown blockquote {{
      margin: 0 0 1em; padding: 12px 16px; border-left: 3px solid var(--accent);
      background: var(--panel-bg); color: var(--text); border-radius: 0 8px 8px 0;
    }}
    #drawer-markdown pre {{
      margin: 0 0 1em; white-space: pre-wrap; word-break: break-word;
      line-height: 1.55; font-size: 13px; color: var(--text);
      background: var(--panel-bg); border: 1px solid var(--border);
      border-radius: 8px; padding: 16px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }}
    #drawer-markdown code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.92em; background: var(--panel-bg); padding: 0.16em 0.38em;
      border-radius: 6px; color: var(--accent);
    }}
    #drawer-markdown pre code {{ background: transparent; padding: 0; color: inherit; border-radius: 0; }}
    #drawer-markdown .wikilink {{ color: var(--accent); font-weight: 600; }}
    @media (max-width: 960px) {{ #drawer {{ width: 100vw; }} }}
    #stats {{
      position: fixed; top: 16px; right: 16px;
      background: rgba(22, 24, 34, 0.95); padding: 12px 18px;
      border-radius: 12px; font-size: 13px;
      backdrop-filter: blur(12px); border: 1px solid var(--border);
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3); color: var(--text-dim);
    }}
  </style>
</head>
<body>
  <div class="cyber-grid"></div>
  <div class="cyber-particles" id="particles"></div>
  <div id="controls">
    <h3>🔮 知识图谱</h3>
    <input id="search" type="text" placeholder="搜索节点..." oninput="searchNodes(this.value)">
    <div class="legend">
      <div class="legend-item"><div class="legend-dot" style="background:#4CAF50"></div>source</div>
      <div class="legend-item"><div class="legend-dot" style="background:#2196F3"></div>entity</div>
      <div class="legend-item"><div class="legend-dot" style="background:#FF9800"></div>concept</div>
      <div class="legend-item"><div class="legend-dot" style="background:#9C27B0"></div>synthesis</div>
    </div>
    <div class="filter-group">
      <label>边类型</label>
      <div class="cb-row"><input type="checkbox" id="cb-extracted" checked onchange="applyFilters()"><span style="background:#555555"></span> Extracted ({n_extracted})</div>
      <div class="cb-row"><input type="checkbox" id="cb-inferred" checked onchange="applyFilters()"><span style="background:#FF5722"></span> Inferred ({n_inferred})</div>
      <div class="cb-row"><input type="checkbox" id="cb-ambiguous" onchange="applyFilters()"><span style="background:#BDBDBD"></span> Ambiguous ({n_ambiguous})</div>
    </div>
    <div class="filter-group">
      <label>最小置信度</label>
      <div class="slider-row">
        <input type="range" id="conf-slider" min="0" max="100" value="50" oninput="applyFilters()">
        <span class="slider-val" id="conf-val">0.50</span>
      </div>
    </div>
    <p>点击节点可高亮其连接的邻居并在右侧查看内容。点击背景可恢复完整图谱。</p>
  </div>
  <div id="graph"></div>
  <aside id="drawer">
    <div id="drawer-header">
      <div id="drawer-topline">
        <h2 id="drawer-title"></h2>
        <button id="drawer-close" onclick="clearSelection()" aria-label="关闭抽屉">×</button>
      </div>
      <div id="drawer-meta"></div>
      <div id="drawer-path"></div>
      <div id="drawer-preview"></div>
    </div>
    <div id="drawer-related">
      相关节点
      <div id="drawer-related-list"></div>
    </div>
    <div id="drawer-content">
      <div id="drawer-markdown"></div>
    </div>
  </aside>
  <div id="stats"></div>
  <script>
    const particlesContainer = document.getElementById('particles');
    for (let i = 0; i < 30; i++) {{
      const particle = document.createElement('div');
      particle.className = 'particle';
      particle.style.left = Math.random() * 100 + '%';
      particle.style.bottom = '-10px';
      particle.style.animationDelay = Math.random() * 15 + 's';
      particle.style.animationDuration = (10 + Math.random() * 10) + 's';
      particlesContainer.appendChild(particle);
    }}

    const originalNodes = {nodes_json};
    const originalEdges = {edges_json}.map(edge => ({{
      ...edge,
      id: edge.id || `${{edge.from}}->${{edge.to}}:${{edge.type || "INFERRED"}}`,
    }}));
    const nodes = new vis.DataSet(originalNodes);
    const edges = new vis.DataSet(originalEdges);
    const adjacency = new Map();
    const searchInput = document.getElementById("search");
    const stats = document.getElementById("stats");
    const controls = {{
      extracted: document.getElementById("cb-extracted"),
      inferred: document.getElementById("cb-inferred"),
      ambiguous: document.getElementById("cb-ambiguous"),
      confSlider: document.getElementById("conf-slider"),
      confValue: document.getElementById("conf-val"),
    }};
    const nodeMap = new Map(originalNodes.map(node => [node.id, node]));
let activeNodeId = null;

function hexToRgba(color, alpha) {{
  if (!color) return `rgba(255, 255, 255, ${{alpha}})`;
  const normalized = color.replace("#", "");
  const value = normalized.length === 3
    ? normalized.split("").map(ch => ch + ch).join("")
    : normalized;
  const intValue = Number.parseInt(value, 16);
  const r = (intValue >> 16) & 255;
  const g = (intValue >> 8) & 255;
  const b = intValue & 255;
  return `rgba(${{r}}, ${{g}}, ${{b}}, ${{alpha}})`;
}}

function escapeHtml(text) {{
  return (text || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}}

function stripFrontmatter(markdown) {{
  return (markdown || "").replace(/^---\\n[\\s\\S]*?\\n---\\n?/, "");
}}

function renderInlineMarkdown(text) {{
  let html = escapeHtml(text);
  html = html.replace(/\\[\\[([^\\]]+)\\]\\]/g, '<span class="wikilink">[[$1]]</span>');
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/\\*\\*([^*]+)\\*\\*/g, "<strong>$1</strong>");
  html = html.replace(/\\*([^*]+)\\*/g, "<em>$1</em>");
  return html;
}}

function renderMarkdown(markdown) {{
  const lines = stripFrontmatter(markdown).split(/\\r?\\n/);
  const html = [];
  let paragraph = [];
  let listType = null;
  let listItems = [];
  let quoteLines = [];
  let inCodeBlock = false;
  let codeLines = [];

  function flushParagraph() {{
    if (!paragraph.length) return;
    html.push(`<p>${{renderInlineMarkdown(paragraph.join(" "))}}</p>`);
    paragraph = [];
  }}
  function flushList() {{
    if (!listType || !listItems.length) return;
    const items = listItems.map(item => `<li>${{renderInlineMarkdown(item)}}</li>`).join("");
    html.push(`<${{listType}}>${{items}}</${{listType}}>`);
    listType = null;
    listItems = [];
  }}
  function flushQuote() {{
    if (!quoteLines.length) return;
    html.push(`<blockquote>${{quoteLines.map(line => renderInlineMarkdown(line)).join("<br>")}}</blockquote>`);
    quoteLines = [];
  }}
  function flushCode() {{
    if (!codeLines.length) {{ html.push("<pre><code></code></pre>"); return; }}
    html.push(`<pre><code>${{escapeHtml(codeLines.join("\\n"))}}</code></pre>`);
    codeLines = [];
  }}

  for (const rawLine of lines) {{
    const line = rawLine.replace(/\\t/g, "    ");
    const trimmed = line.trim();
    if (trimmed.startsWith("```")) {{
      flushParagraph(); flushList(); flushQuote();
      if (inCodeBlock) {{ flushCode(); inCodeBlock = false; }} else {{ inCodeBlock = true; }}
      continue;
    }}
    if (inCodeBlock) {{ codeLines.push(rawLine); continue; }}
    if (!trimmed) {{ flushParagraph(); flushList(); flushQuote(); continue; }}
    const headingMatch = trimmed.match(/^(#{1,6})\\s+(.+)$/);
    if (headingMatch) {{
      flushParagraph(); flushList(); flushQuote();
      const level = headingMatch[1].length;
      html.push(`<h${{level}}>${{renderInlineMarkdown(headingMatch[2])}}</h${{level}}>`);
      continue;
    }}
    if (/^(-{3,}|\\*{3,})$/.test(trimmed)) {{ flushParagraph(); flushList(); flushQuote(); html.push("<hr>"); continue; }}
    const quoteMatch = trimmed.match(/^>\\s?(.*)$/);
    if (quoteMatch) {{ flushParagraph(); flushList(); quoteLines.push(quoteMatch[1]); continue; }}
    flushQuote();
    const unorderedMatch = trimmed.match(/^[-*]\\s+(.+)$/);
    if (unorderedMatch) {{
      flushParagraph();
      if (listType && listType !== "ul") flushList();
      listType = "ul"; listItems.push(unorderedMatch[1]); continue;
    }}
    const orderedMatch = trimmed.match(/^\\d+\\.\\s+(.+)$/);
    if (orderedMatch) {{
      flushParagraph();
      if (listType && listType !== "ol") flushList();
      listType = "ol"; listItems.push(orderedMatch[1]); continue;
    }}
    flushList();
    paragraph.push(trimmed);
  }}
  if (inCodeBlock) flushCode();
  flushParagraph(); flushList(); flushQuote();
  return html.join("");
}}

function rebuildAdjacency(filteredEdges) {{
  adjacency.clear();
  for (const node of originalNodes) adjacency.set(node.id, new Set());
  for (const edge of filteredEdges) {{
    if (!adjacency.has(edge.from)) adjacency.set(edge.from, new Set());
    if (!adjacency.has(edge.to)) adjacency.set(edge.to, new Set());
    adjacency.get(edge.from).add(edge.to);
    adjacency.get(edge.to).add(edge.from);
  }}
}}

function currentEdgeState() {{
  const minConf = parseInt(controls.confSlider.value, 10) / 100;
  controls.confValue.textContent = minConf.toFixed(2);
  return {{
    showExtracted: controls.extracted.checked,
    showInferred: controls.inferred.checked,
    showAmbiguous: controls.ambiguous.checked,
    minConf,
  }};
}}

function passesEdgeFilters(edge, edgeState) {{
  const typeOk = (edge.type === "EXTRACTED" && edgeState.showExtracted)
    || (edge.type === "INFERRED" && edgeState.showInferred)
    || (edge.type === "AMBIGUOUS" && edgeState.showAmbiguous);
  const confOk = (edge.confidence ?? 1.0) >= edgeState.minConf;
  return typeOk && confOk;
}}

function searchNodes(q) {{ applyFilters(q, activeNodeId); }}

function clearSelection() {{
  activeNodeId = null;
  closeDrawer();
  applyFilters(searchInput.value, null);
}}

function closeDrawer() {{ document.getElementById("drawer").classList.remove("open"); }}

function openDrawer(node, relatedIds) {{
  document.getElementById("drawer").classList.add("open");
  document.getElementById("drawer-title").textContent = node.label;
  const communityText = Number.isInteger(node.group) && node.group >= 0 ? ` · community ${{node.group}}` : "";
  document.getElementById("drawer-meta").textContent = `${{node.type}}${{communityText}}`;
  document.getElementById("drawer-path").textContent = node.path;
  document.getElementById("drawer-preview").textContent = node.preview || "";
  document.getElementById("drawer-markdown").innerHTML = renderMarkdown(node.markdown || "");
  const relatedList = document.getElementById("drawer-related-list");
  relatedList.innerHTML = "";
  const relatedNodes = originalNodes.filter(item => relatedIds.has(item.id) && item.id !== node.id).sort((a, b) => a.label.localeCompare(b.label));
  if (relatedNodes.length === 0) {{
    const empty = document.createElement("span");
    empty.textContent = "No directly connected nodes";
    relatedList.appendChild(empty);
    return;
  }}
  for (const related of relatedNodes) {{
    const chip = document.createElement("button");
    chip.className = "related-chip";
    chip.textContent = related.label;
    chip.onclick = () => focusNode(related.id);
    relatedList.appendChild(chip);
  }}
}}

function applyFilters(query = searchInput.value, selectedNodeId = activeNodeId) {{
  const lower = (query || "").trim().toLowerCase();
  const edgeState = currentEdgeState();
  const filteredEdges = originalEdges.filter(edge => passesEdgeFilters(edge, edgeState));
  rebuildAdjacency(filteredEdges);
  const relatedIds = selectedNodeId ? new Set([selectedNodeId, ...(adjacency.get(selectedNodeId) || [])]) : null;
  const filteredNodeIds = new Set();
  for (const edge of filteredEdges) {{ filteredNodeIds.add(edge.from); filteredNodeIds.add(edge.to); }}
  let visibleNodeCount = 0;
  const nodeUpdates = originalNodes.map(node => {{
    const matchesSearch = !lower || node.label.toLowerCase().includes(lower);
    const isActive = selectedNodeId === node.id;
    const isConnected = filteredNodeIds.has(node.id);
    const isRelated = !relatedIds || relatedIds.has(node.id);
    const hidden = !selectedNodeId && !lower && !isConnected;
    const emphasized = matchesSearch && isRelated && (isConnected || !!lower || isActive);
    if (!hidden) visibleNodeCount += 1;
    return {{
      id: node.id, hidden,
      color: {{
        background: emphasized ? node.color : hexToRgba(node.color, hidden ? 0.05 : 0.14),
        border: emphasized ? hexToRgba(node.color, 0.96) : hexToRgba(node.color, hidden ? 0.08 : 0.22),
        highlight: {{ background: node.color, border: hexToRgba(node.color, 1) }},
        hover: {{ background: node.color, border: hexToRgba(node.color, 1) }},
      }},
      font: {{ color: emphasized ? "#f2f3f8" : hidden ? "rgba(242,243,248,0.08)" : "rgba(242,243,248,0.2)" }},
      borderWidth: isActive ? 5 : 2,
      size: isActive ? 18 : 12,
    }};
  }});
  const edgeUpdates = originalEdges.map(edge => {{
    const enabled = passesEdgeFilters(edge, edgeState);
    if (!enabled) return {{ id: edge.id, hidden: true }};
    const matchesSearch = !lower || nodeMap.get(edge.from)?.label.toLowerCase().includes(lower) || nodeMap.get(edge.to)?.label.toLowerCase().includes(lower);
    const isRelated = !relatedIds || relatedIds.has(edge.from) || relatedIds.has(edge.to);
    const touchesActive = !!selectedNodeId && (edge.from === selectedNodeId || edge.to === selectedNodeId);
    const emphasized = matchesSearch && isRelated;
    return {{
      id: edge.id, hidden: false,
      width: touchesActive ? 2.8 : emphasized ? 1.2 : 0.6,
      color: emphasized ? edge.color : hexToRgba(edge.color, 0.08),
    }};
  }});
  nodes.update(nodeUpdates);
  edges.update(edgeUpdates);
  if (selectedNodeId) {{
    const activeNode = nodeMap.get(selectedNodeId);
    if (activeNode) openDrawer(activeNode, relatedIds || new Set([selectedNodeId]));
  }}
  const focusSuffix = selectedNodeId && nodeMap.get(selectedNodeId) ? ` · focused: ${{nodeMap.get(selectedNodeId).label}}` : "";
  stats.textContent = `${{visibleNodeCount}} nodes · ${{filteredEdges.length}} edges${{focusSuffix}}`;
}}

const container = document.getElementById("graph");
const nodeCount = originalNodes.length;
const gravConst = nodeCount > 80 ? -8000 : nodeCount > 30 ? -5000 : -2000;
const springLen = nodeCount > 80 ? 250 : nodeCount > 30 ? 200 : 150;

const network = new vis.Network(container, {{ nodes, edges }}, {{
  nodes: {{
    shape: "dot",
    font: {{ color: "#ddd", size: 12, strokeWidth: 3, strokeColor: "#111" }},
    borderWidth: 1.5,
    scaling: {{ min: 8, max: 40, label: {{ enabled: true, min: 10, max: 20, drawThreshold: 6, maxVisible: 24 }} }},
  }},
  edges: {{
    width: 0.8, smooth: {{ type: "continuous" }},
    arrows: {{ to: {{ enabled: true, scaleFactor: 0.4 }} }},
    color: {{ inherit: false }}, hoverWidth: 2,
  }},
  physics: {{
    stabilization: {{ iterations: 250, updateInterval: 25, fit: true }},
    barnesHut: {{ gravitationalConstant: gravConst, springLength: springLen, springConstant: 0.02, damping: 0.15 }},
    minVelocity: 0.75,
  }},
  interaction: {{ hover: true, tooltipDelay: 150, hideEdgesOnDrag: true, hideEdgesOnZoom: true }},
}});

network.once("stabilizationIterationsDone", function () {{
  network.fit({{ animation: {{ duration: 400, easingFunction: "easeInOutQuad" }} }});
}});

function focusNode(nodeId) {{
  activeNodeId = nodeId;
  applyFilters(searchInput.value, nodeId);
  const node = nodeMap.get(nodeId) || nodes.get(nodeId);
  const relatedIds = new Set([nodeId, ...(adjacency.get(nodeId) || [])]);
  openDrawer(node, relatedIds);
  network.focus(nodeId, {{ scale: 1.1, animation: {{ duration: 300, easingFunction: "easeInOutQuad" }} }});
}}

network.on("click", params => {{
  if (params.nodes.length > 0) focusNode(params.nodes[0]);
  else clearSelection();
}});

applyFilters();
</script>
</body>
</html>"""

    # ── 主构建方法 ─────────────────────────────────────────────────

    def build_graph(
        self,
        project_id: int,
        infer: bool = False,
        clean: bool = False,
        resume: bool = True,
        report: bool = True,
    ) -> dict[str, Any]:
        """为项目构建知识图谱（完整版）。

        流程：
            1. 从 Wiki 页面提取节点和显式边（wikilink → EXTRACTED 边）
            2. （可选）通过 LLM 推理隐式语义边（INFERRED / AMBIGUOUS）
            3. 边去重
            4. Louvain 社区检测
            5. 生成 graph.json 和 graph.html
            6. （可选）生成图谱健康报告

        Args:
            project_id: 项目 ID
            infer: 是否进行语义推理（需要额外 LLM 调用）
            clean: 是否清除推理缓存
            resume: 是否从上次中断处继续（checkpoint/resume）
            report: 是否生成图谱健康报告

        Returns:
            构建结果字典，包含：
            - ``n_nodes``: 节点数
            - ``n_edges``: 边数
            - ``n_extracted``: 显式边数
            - ``n_inferred``: 推理边数
            - ``graph_data``: 完整图谱数据
            - ``phantom_hubs``: 幽灵枢纽列表
            - ``report``: 图谱健康报告（仅 ``report=True`` 时）

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
            return {"n_nodes": 0, "n_edges": 0, "message": "Wiki 为空"}

        # Pass 1: 提取节点
        nodes = []
        for p in pages:
            content = self.db.get_file_text_by_path(project_id, p["relative_path"]) or ""
            node_type = "unknown"
            m = re.search(r"^type:\s*(\S+)", content, re.MULTILINE)
            if m:
                node_type = m.group(1).strip("\"'")

            title_match = re.search(r'^title:\s*"?([^"\n]+)"?', content, re.MULTILINE)
            label = title_match.group(1).strip() if title_match else Path(p["relative_path"]).stem

            body = re.sub(r"^---\n.*?\n---\n?", "", content, flags=re.DOTALL)
            preview_lines = [line.strip() for line in body.splitlines() if line.strip()]
            preview = " ".join(preview_lines[:3])[:220]

            page_id_str = p["relative_path"].replace("wiki/", "").replace(".md", "")
            nodes.append({
                "id": page_id_str,
                "label": label,
                "type": node_type,
                "color": TYPE_COLORS.get(node_type, TYPE_COLORS["unknown"]),
                "path": p["relative_path"],
                "markdown": content,
                "preview": preview,
            })

        # Pass 1: 提取显式边
        stem_map: dict[str, str] = {}
        for p in pages:
            page_id_str = p["relative_path"].replace("wiki/", "").replace(".md", "")
            stem_map[Path(p["relative_path"]).stem.lower()] = page_id_str

        edges = []
        seen = set()
        for p in pages:
            content = self.db.get_file_text_by_path(project_id, p["relative_path"]) or ""
            src = p["relative_path"].replace("wiki/", "").replace(".md", "")
            for link in extract_wikilinks(content):
                link_stem = link.lower()
                if "/" in link:
                    link_stem = Path(link).stem.lower()
                target = stem_map.get(link_stem)
                if target and target != src:
                    key = (src, target)
                    if key not in seen:
                        seen.add(key)
                        edges.append({
                            "id": self.edge_id(src, target, "EXTRACTED"),
                            "from": src,
                            "to": target,
                            "type": "EXTRACTED",
                            "color": EDGE_COLORS["EXTRACTED"],
                            "confidence": 1.0,
                        })

        # Pass 2: 语义推理
        if infer:
            logger.info("  Pass 2: inferring semantic relationships...")
            inferred = self.build_inferred_edges(
                project_id, pages, edges, infer=True, clean=clean, resume=resume
            )
            edges.extend(inferred)
            n_inf_new = len([e for e in inferred if e["type"] in ("INFERRED", "AMBIGUOUS")])
            logger.info("  -> %d inferred edges", n_inf_new)

        # 去重
        before_dedup = len(edges)
        edges = self.deduplicate_edges(edges)
        if before_dedup != len(edges):
            logger.info("  dedup: %d -> %d edges", before_dedup, len(edges))

        # 社区检测
        logger.info("  Running Louvain community detection...")
        communities = self.detect_communities(nodes, edges)
        for node in nodes:
            comm_id = communities.get(node["id"], -1)
            if comm_id >= 0:
                node["color"] = COMMUNITY_COLORS[comm_id % len(COMMUNITY_COLORS)]
            node["group"] = comm_id

        # 度数计算
        degree_map: dict[str, int] = {}
        for e in edges:
            degree_map[e["from"]] = degree_map.get(e["from"], 0) + 1
            degree_map[e["to"]] = degree_map.get(e["to"], 0) + 1
        for node in nodes:
            node["value"] = degree_map.get(node["id"], 0) + 1

        # 保存图谱数据
        today = date.today().isoformat()
        graph_data = {
            "built": today,
            "project_id": project_id,
            "project_name": proj["name"],
            "nodes": nodes,
            "edges": edges,
        }

        graph_json = json.dumps(graph_data, ensure_ascii=False, indent=2)
        self.db.add_file(project_id, "graph/graph.json", graph_json)

        graph_html = self.render_graph_html(nodes, edges)
        self.db.add_file(project_id, "graph/graph.html", graph_html)

        n_ext = len([e for e in edges if e['type'] == 'EXTRACTED'])
        n_inf = len([e for e in edges if e['type'] in ('INFERRED', 'AMBIGUOUS')])
        logger.info("  saved: graph/graph.json (%d nodes, %d edges)", len(nodes), len(edges))
        logger.info("  saved: graph/graph.html")
        logger.info("  (%d extracted, %d inferred)", n_ext, n_inf)

        # 幽灵枢纽
        phantom_hubs = []
        if report:
            phantom_hubs = self.find_phantom_hubs(project_id, pages)
            if phantom_hubs:
                logger.info("  phantom hubs: %d pages referenced but not created", len(phantom_hubs))

        # 报告
        report_text = ""
        if report:
            report_text = self.generate_graph_report(project_id, nodes, edges, communities)
            if phantom_hubs:
                report_text += "\n## 👻 Phantom Hubs (Referenced but Non-existent)\n"
                report_text += "These pages are linked by 2+ existing pages but don't exist yet — strong signals for page creation:\n\n"
                for ph in phantom_hubs:
                    report_text += f"- **{ph['name']}** (referenced by {ph['ref_count']} pages: {', '.join(ph['referenced_by'][:3])})\n"
                report_text += "\n"
            self.db.add_file(project_id, "graph/graph-report.md", report_text)
            logger.info("  saved: graph/graph-report.md")

        return {
            "n_nodes": len(nodes),
            "n_edges": len(edges),
            "n_extracted": n_ext,
            "n_inferred": n_inf,
            "graph_data": graph_data,
            "phantom_hubs": phantom_hubs,
            "report": report_text if report else None,
        }
