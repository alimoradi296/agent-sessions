"""Provider-native parent relationships stay distinct in the session graph."""

import unittest

from agent_sessions.analysis.linker import build_graph


class ThreadLineageGraphTests(unittest.TestCase):
    def test_codex_spawn_edge_is_not_mislabeled_as_a_fork(self):
        graph = build_graph([
            {"session_id": "root-thread", "agent": "codex", "title": "Root"},
            {"session_id": "child-thread", "agent": "codex", "title": "Child",
             "parent_id": "root-thread"},
            {"session_id": "fork-thread", "agent": "claude", "title": "Fork",
             "parent_id": "root-thread"},
        ])
        edges = {(edge.source, edge.target, edge.edge_type, edge.label) for edge in graph.edges}
        self.assertIn(("child-thread", "root-thread", "spawned_from", "subagent"), edges)
        self.assertIn(("fork-thread", "root-thread", "forked_from", "rewind/branch"), edges)


if __name__ == "__main__":
    unittest.main()
