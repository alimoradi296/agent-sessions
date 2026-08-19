"""Build cross-session relationship graph from distilled sessions."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class GraphEdge:
    source: str
    target: str
    edge_type: str
    label: str = ""

    def to_dict(self) -> dict:
        return {"source": self.source, "target": self.target, "type": self.edge_type, "label": self.label}


@dataclass
class GraphNode:
    id: str
    title: str
    agent: str
    date: str
    topic: str
    prds: list[str] = field(default_factory=list)
    significance: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "agent": self.agent,
            "date": self.date,
            "topic": self.topic,
            "prds": self.prds,
            "significance": self.significance,
        }


@dataclass
class SessionGraph:
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "version": 1,
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
        }

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> SessionGraph:
        data = json.loads(path.read_text(encoding="utf-8"))
        nodes = [GraphNode(**n) for n in data.get("nodes", [])]
        edges = [GraphEdge(**{**e, "edge_type": e.get("type", e.get("edge_type", ""))}) for e in data.get("edges", [])]
        return cls(nodes=nodes, edges=edges)

    def neighbors(self, session_id: str, edge_type: Optional[str] = None) -> list[GraphEdge]:
        results = []
        for e in self.edges:
            if e.source == session_id or e.target == session_id:
                if edge_type is None or e.edge_type == edge_type:
                    results.append(e)
        return results

    def find_by_prd(self, prd: str) -> list[GraphNode]:
        prd_lower = prd.lower()
        return [n for n in self.nodes if any(prd_lower in p.lower() for p in n.prds)]

    def find_by_branch(self, branch: str) -> list[GraphNode]:
        return []  # branch stored in distilled, not node — query via distilled files


def load_distilled_sessions(distilled_dir: Path) -> list[dict]:
    sessions: list[dict] = []
    for path in distilled_dir.glob("*.distilled.json"):
        try:
            sessions.append(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return sessions


def build_graph(distilled: list[dict]) -> SessionGraph:
    graph = SessionGraph()
    by_id: dict[str, dict] = {d["session_id"]: d for d in distilled}

    for d in distilled:
        graph.nodes.append(GraphNode(
            id=d["session_id"],
            title=d.get("title", "")[:80],
            agent=d.get("agent", ""),
            date=d.get("date", ""),
            topic=d.get("topic", "")[:80],
            prds=d.get("prds", []),
            significance=d.get("significance", 0),
        ))

    seen_edges: set[tuple[str, str, str]] = set()

    def add_edge(source: str, target: str, edge_type: str, label: str = "") -> None:
        if source == target:
            return
        key = (min(source, target), max(source, target), edge_type)
        if key in seen_edges:
            return
        seen_edges.add(key)
        graph.edges.append(GraphEdge(source=source, target=target, edge_type=edge_type, label=label))

    # forked_from edges
    for d in distilled:
        parent = d.get("parent_id")
        if parent and parent in by_id:
            add_edge(d["session_id"], parent, "forked_from", "rewind/branch")

    # same PRD edges
    prd_to_sessions: dict[str, list[str]] = {}
    for d in distilled:
        for prd in d.get("prds", []):
            prd_key = prd.split(" ")[0].upper()
            prd_to_sessions.setdefault(prd_key, []).append(d["session_id"])

    for prd, sids in prd_to_sessions.items():
        if len(sids) < 2:
            continue
        for i, sid in enumerate(sids):
            for other in sids[i + 1:]:
                add_edge(sid, other, "same_prd", prd)

    # same branch edges (same project + branch, limit to avoid clique explosion)
    branch_groups: dict[str, list[str]] = {}
    for d in distilled:
        branch = d.get("branch", "unknown")
        project = d.get("project", "unknown")
        if branch == "unknown":
            continue
        key = f"{project}:{branch}"
        branch_groups.setdefault(key, []).append(d["session_id"])

    for key, sids in branch_groups.items():
        if len(sids) < 2 or len(sids) > 20:
            continue
        anchor = sids[0]
        for sid in sids[1:]:
            add_edge(anchor, sid, "same_branch", key.split(":", 1)[1])

    # same file edges
    file_to_sessions: dict[str, list[str]] = {}
    for d in distilled:
        for fpath in d.get("files_touched", [])[:10]:
            file_to_sessions.setdefault(fpath, []).append(d["session_id"])

    for fpath, sids in file_to_sessions.items():
        if len(sids) < 2 or len(sids) > 15:
            continue
        anchor = sids[0]
        for sid in sids[1:]:
            add_edge(anchor, sid, "same_file", fpath)

    # cross-agent same topic (same PRD already covered; also match similar titles)
    return graph


def _prd_matches(query: str, prd_label: str) -> bool:
    q = re.search(r"\d+", query)
    p = re.search(r"\d+", prd_label)
    if q and p:
        return q.group().lstrip("0") == p.group().lstrip("0") or q.group().zfill(3) == p.group().zfill(3)
    return query.lower() in prd_label.lower()


def query_graph(
    graph: SessionGraph,
    distilled: list[dict],
    *,
    prd: Optional[str] = None,
    branch: Optional[str] = None,
    file_path: Optional[str] = None,
    session_id: Optional[str] = None,
) -> list[dict]:
    """Return matching distilled sessions for a link query."""
    by_id = {d["session_id"]: d for d in distilled}
    matched_ids: set[str] = set()

    if session_id:
        matched_ids.add(session_id)
        for edge in graph.neighbors(session_id):
            other = edge.target if edge.source == session_id else edge.source
            matched_ids.add(other)

    if prd:
        for d in distilled:
            if any(_prd_matches(prd, p) for p in d.get("prds", [])):
                matched_ids.add(d["session_id"])

    if branch:
        branch_lower = branch.lower()
        for d in distilled:
            if branch_lower in d.get("branch", "").lower():
                matched_ids.add(d["session_id"])

    if file_path:
        file_lower = file_path.lower()
        for d in distilled:
            if any(file_lower in f.lower() for f in d.get("files_touched", [])):
                matched_ids.add(d["session_id"])

    return [by_id[sid] for sid in matched_ids if sid in by_id]
