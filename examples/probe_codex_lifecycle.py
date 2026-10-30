"""Synthetic-only probe for read-only Codex edge/rollout comparison."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from agent_sessions.analysis.codex_lifecycle import inspect_codex_lifecycle


def write_rollout(path: Path, child: str, marker: str | None) -> None:
    records = [{"type": "session_meta", "payload": {"id": child}}]
    if marker:
        records.append({"type": "event_msg", "payload": {"type": marker}})
    path.write_text("".join(json.dumps(row) + "\n" for row in records), encoding="utf-8")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="agent-sessions-codex-probe-") as temp:
        root = Path(temp)
        database = root / "state_synthetic.sqlite"
        with sqlite3.connect(database) as connection:
            connection.execute(
                "CREATE TABLE thread_spawn_edges "
                "(parent_thread_id TEXT, child_thread_id TEXT PRIMARY KEY, status TEXT)"
            )
            connection.executemany(
                "INSERT INTO thread_spawn_edges VALUES (?, ?, ?)",
                [("parent-a", "child-a", "open"), ("parent-b", "child-b", "closed")],
            )
        a = root / "rollout-a.jsonl"
        b = root / "rollout-b.jsonl"
        write_rollout(a, "child-a", "task_complete")
        write_rollout(b, "child-b", "turn_aborted")
        inspection = inspect_codex_lifecycle(database, [a, b])
        assert inspection.schema_state == "recognized"
        assert [row.assessment for row in inspection.edges] == [
            "terminal_turn_open_resumable_edge", "closed_edge_terminal_turn"
        ]
        # Verify the checker did not alter the source database.
        with sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True) as connection:
            assert connection.execute("SELECT status FROM thread_spawn_edges ORDER BY child_thread_id").fetchall() == [("open",), ("closed",)]
        print("Synthetic Codex lifecycle probe: 2 joined edges passed; live-runtime behavior unverified.")


if __name__ == "__main__":
    main()
