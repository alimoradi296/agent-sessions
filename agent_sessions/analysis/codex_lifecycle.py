"""Read-only comparison of Codex spawn edges and rollout turn markers.

This module deliberately reports evidence, not process liveness. An ``open``
edge means live or resumable in Codex; a terminal rollout marker does not prove
that the edge is stale or that no worker is running.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import quote


@dataclass(frozen=True)
class EdgeEvidence:
    parent_thread_id: str
    child_thread_id: str
    edge_status: str
    rollout_evidence: str
    assessment: str


@dataclass(frozen=True)
class LifecycleInspection:
    schema_state: str
    edges: list[EdgeEvidence]


def _load_edges(database: Path) -> tuple[str, list[tuple[str, str, str]]]:
    # URI mode=ro and query_only provide two layers against accidental writes.
    uri = f"file:{quote(database.resolve().as_posix(), safe='/')}?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True) as connection:
            connection.execute("PRAGMA query_only = ON")
            tables = connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='thread_spawn_edges'"
            ).fetchone()
            if tables is None:
                return "unknown: thread_spawn_edges_table_missing", []
            columns = {row[1] for row in connection.execute("PRAGMA table_info(thread_spawn_edges)")}
            required = {"parent_thread_id", "child_thread_id", "status"}
            if not required.issubset(columns):
                return "unknown: unsupported_thread_spawn_edges_schema", []
            rows = connection.execute(
                "SELECT parent_thread_id, child_thread_id, status "
                "FROM thread_spawn_edges ORDER BY parent_thread_id, child_thread_id"
            ).fetchall()
    except sqlite3.Error:
        return "unknown: database_unavailable_or_unreadable", []
    return "recognized", [(str(parent), str(child), str(status)) for parent, child, status in rows]


def _rollout_turn_state(paths: list[Path], child_id: str) -> str:
    matches: list[tuple[Path, list[str]]] = []
    malformed = False
    for path in paths:
        metadata_ids: list[str] = []
        lifecycle: list[str] = []
        try:
            with path.open(encoding="utf-8") as stream:
                for line in stream:
                    try:
                        record = json.loads(line)
                    except (ValueError, TypeError):
                        malformed = True
                        continue
                    if not isinstance(record, dict):
                        malformed = True
                        continue
                    payload = record.get("payload")
                    if not isinstance(payload, dict):
                        continue
                    if record.get("type") == "session_meta" and payload.get("id"):
                        metadata_ids.append(str(payload["id"]))
                    if record.get("type") == "event_msg":
                        marker = payload.get("type")
                        if marker in {"task_started", "task_complete", "turn_completed", "turn_aborted"}:
                            lifecycle.append(str(marker))
        except (OSError, UnicodeError):
            malformed = True
            continue
        if child_id in metadata_ids:
            # Multiple metadata identities inside a file cannot be safely joined.
            if len(set(metadata_ids)) != 1:
                return "unknown: conflicting_thread_metadata"
            matches.append((path, lifecycle))

    if malformed:
        return "unknown: malformed_or_unreadable_rollout"
    if len(matches) != 1:
        return "unknown: missing_or_multiple_rollouts"
    markers = matches[0][1]
    if not markers:
        return "unknown: no_turn_lifecycle_marker"
    last = markers[-1]
    if last in {"task_complete", "turn_completed", "turn_aborted"}:
        return f"last_recorded_turn_terminal:{last}"
    return "last_recorded_turn_nonterminal:task_started"


def inspect_codex_lifecycle(database: Path, rollout_paths: list[Path]) -> LifecycleInspection:
    """Compare explicit SQLite and rollout paths; never discovers user data."""
    schema_state, edge_rows = _load_edges(Path(database))
    if schema_state != "recognized":
        return LifecycleInspection(schema_state, [])
    reports = []
    for parent, child, status in edge_rows:
        turn = _rollout_turn_state([Path(path) for path in rollout_paths], child)
        if status not in {"open", "closed"}:
            assessment = "unknown: unrecognized_edge_status"
        elif turn.startswith("unknown:"):
            assessment = turn
        elif status == "open" and turn.startswith("last_recorded_turn_terminal:"):
            assessment = "terminal_turn_open_resumable_edge"
        elif status == "closed" and turn.startswith("last_recorded_turn_terminal:"):
            assessment = "closed_edge_terminal_turn"
        elif status == "open":
            assessment = "open_edge_nonterminal_turn_liveness_unknown"
        else:
            assessment = "closed_edge_nonterminal_turn_liveness_unknown"
        reports.append(EdgeEvidence(parent, child, status, turn, assessment))
    return LifecycleInspection(schema_state, reports)


def report_as_dicts(inspection: LifecycleInspection) -> dict[str, object]:
    """JSON-friendly form for local tools and synthetic evaluations."""
    return {
        "schema_state": inspection.schema_state,
        "edges": [asdict(report) for report in inspection.edges],
    }
