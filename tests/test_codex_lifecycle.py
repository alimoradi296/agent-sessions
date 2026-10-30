"""Synthetic tests for conservative Codex persisted-state comparison."""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from agent_sessions.analysis.codex_lifecycle import inspect_codex_lifecycle


class CodexLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.database = self.root / "state.sqlite"
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                "CREATE TABLE thread_spawn_edges "
                "(parent_thread_id TEXT, child_thread_id TEXT PRIMARY KEY, status TEXT)"
            )
            connection.executemany(
                "INSERT INTO thread_spawn_edges VALUES (?, ?, ?)",
                [("p", "open-child", "open"), ("p", "closed-child", "closed"),
                 ("p", "active-child", "open"), ("p", "missing-child", "open")],
            )

    def rollout(self, name, child, *markers):
        path = self.root / name
        rows = [{"type": "session_meta", "payload": {"id": child}}]
        rows.extend({"type": "event_msg", "payload": {"type": marker}} for marker in markers)
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        return path

    def test_reports_terminal_open_as_resumable_not_live_or_stale(self):
        rollouts = [
            self.rollout("open.jsonl", "open-child", "task_started", "task_complete"),
            self.rollout("closed.jsonl", "closed-child", "turn_aborted"),
            self.rollout("active.jsonl", "active-child", "task_started"),
        ]
        before = self.database.read_bytes()
        inspection = inspect_codex_lifecycle(self.database, rollouts)
        after = self.database.read_bytes()
        self.assertEqual(before, after)
        by_child = {report.child_thread_id: report for report in inspection.edges}
        self.assertEqual(by_child["open-child"].assessment, "terminal_turn_open_resumable_edge")
        self.assertEqual(by_child["closed-child"].assessment, "closed_edge_terminal_turn")
        self.assertEqual(by_child["active-child"].assessment, "open_edge_nonterminal_turn_liveness_unknown")
        self.assertNotIn("running", by_child["open-child"].assessment)
        self.assertNotIn("stale", by_child["open-child"].assessment)

    def test_missing_and_multiple_rollouts_are_unknown(self):
        one = self.rollout("one.jsonl", "open-child", "task_complete")
        duplicate = self.rollout("two.jsonl", "open-child", "turn_aborted")
        reports = inspect_codex_lifecycle(self.database, [one, duplicate]).edges
        by_child = {report.child_thread_id: report for report in reports}
        self.assertTrue(by_child["open-child"].assessment.startswith("unknown:"))
        missing = inspect_codex_lifecycle(self.database, []).edges
        self.assertTrue({report.child_thread_id: report for report in missing}["open-child"].assessment.startswith("unknown:"))

    def test_invalid_edge_status_is_unknown(self):
        with sqlite3.connect(self.database) as connection:
            connection.execute("UPDATE thread_spawn_edges SET status='mystery' WHERE child_thread_id='open-child'")
        rollout = self.rollout("open.jsonl", "open-child", "task_complete")
        report = next(row for row in inspect_codex_lifecycle(self.database, [rollout]).edges
                      if row.child_thread_id == "open-child")
        self.assertEqual(report.assessment, "unknown: unrecognized_edge_status")

    def test_unknown_database_schema_is_reported_without_assuming_edges(self):
        empty = self.root / "older-schema.sqlite"
        with sqlite3.connect(empty) as connection:
            connection.execute("CREATE TABLE other_table (id TEXT)")
        inspection = inspect_codex_lifecycle(empty, [])
        self.assertEqual(inspection.schema_state, "unknown: thread_spawn_edges_table_missing")
        self.assertEqual(inspection.edges, [])


if __name__ == "__main__":
    unittest.main()
