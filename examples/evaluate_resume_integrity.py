"""Probe the evidence required to classify resumed synthetic agent tasks.

This is a design probe, not a production guard or a benchmark of other tools.
All records are authored here; nothing reads agent archives or a Git checkout.
"""

from __future__ import annotations

import json


CASES = (
    {
        "name": "old_running_record_but_output_verified",
        "task_generation": "g1",
        "current_generation": "g2",
        "task_state": "running",
        "transcript_outcome": "success",
        "terminal_event": "success",
        "worker": "absent",
        "expected_tree": "tree-a",
        "current_tree": "tree-a",
        "expected": "stale_completed_do_not_dispatch",
    },
    {
        "name": "old_pending_record_already_applied",
        "task_generation": "g1",
        "current_generation": "g2",
        "task_state": "pending",
        "transcript_outcome": "success",
        "terminal_event": "success",
        "worker": "absent",
        "expected_tree": "tree-b",
        "current_tree": "tree-b",
        "expected": "stale_completed_do_not_dispatch",
    },
    {
        "name": "running_record_without_live_worker_or_terminal_event",
        "task_generation": "g2",
        "current_generation": "g2",
        "task_state": "running",
        "transcript_outcome": "none",
        "terminal_event": "none",
        "worker": "absent",
        "expected_tree": "tree-c",
        "current_tree": "tree-before",
        "expected": "unknown_do_not_dispatch",
    },
    {
        "name": "current_generation_with_live_worker",
        "task_generation": "g2",
        "current_generation": "g2",
        "task_state": "running",
        "transcript_outcome": "none",
        "terminal_event": "none",
        "worker": "live",
        "expected_tree": "tree-d",
        "current_tree": "tree-before",
        "expected": "active",
    },
    {
        "name": "success_event_but_repository_changed_afterward",
        "task_generation": "g2",
        "current_generation": "g2",
        "task_state": "completed",
        "transcript_outcome": "success",
        "terminal_event": "success",
        "worker": "absent",
        "expected_tree": "tree-e",
        "current_tree": "tree-later-edit",
        "expected": "recheck_current_tree",
    },
    {
        "name": "current_terminal_result_and_matching_tree",
        "task_generation": "g2",
        "current_generation": "g2",
        "task_state": "completed",
        "transcript_outcome": "success",
        "terminal_event": "success",
        "worker": "absent",
        "expected_tree": "tree-f",
        "current_tree": "tree-f",
        "expected": "completed_verified_for_recorded_tree",
    },
)


def _proposed_gate(case: dict) -> str:
    same_generation = case["task_generation"] == case["current_generation"]
    tree_matches = case["expected_tree"] == case["current_tree"]

    if not same_generation:
        if case["terminal_event"] == "success" and tree_matches:
            return "stale_completed_do_not_dispatch"
        return "stale_do_not_dispatch"
    if case["worker"] == "live" and case["task_state"] == "running":
        return "active"
    if case["terminal_event"] == "success":
        return "completed_verified_for_recorded_tree" if tree_matches else "recheck_current_tree"
    if case["terminal_event"] == "failed":
        return "failed_do_not_claim_complete"
    if case["task_state"] in {"running", "pending"}:
        return "unknown_do_not_dispatch"
    return "unknown_do_not_dispatch"


def evaluate() -> dict:
    results = []
    for case in CASES:
        results.append({
            "case": case["name"],
            "expected": case["expected"],
            "status_note_only": case["task_state"],
            "transcript_only": case["transcript_outcome"],
            "repository_only": "matches_expected_tree" if case["expected_tree"] == case["current_tree"] else "differs_from_expected_tree",
            "proposed_gate": _proposed_gate(case),
        })
    return {
        "synthetic_only": True,
        "cases": results,
        "proposed_gate_matches_authored_expected": all(r["expected"] == r["proposed_gate"] for r in results),
        "limits": [
            "The cases and expected outcomes are authored; the rule is designed against those cases.",
            "This does not run a provider, task board, hook, or competing tool.",
            "A real gate needs trustworthy task identity, generation, terminal events, and repository fingerprints.",
            "A missing worker observation is not proof of completion; unknown states must not trigger a rerun.",
            "The probe measures no real false-alert rate, user effort, adoption, or willingness to pay.",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2))
