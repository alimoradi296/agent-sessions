"""Synthetic probe for exact Codex parent-spawn to child-rollout joins.

This uses only authored records. It does not inspect local Codex or Cursor data,
install hooks, or claim that a provider runtime emitted these records.
"""

from __future__ import annotations

import json


def child_for_spawn(parent_records: list[dict], child_rollouts: list[list[dict]],
                    call_id: str, parent_thread_id: str):
    """Join call ID -> returned agent ID -> child thread ID and parent ID."""
    calls = [
        record.get("payload", {})
        for record in parent_records
        if record.get("type") == "response_item"
        and record.get("payload", {}).get("type") == "function_call"
        and record.get("payload", {}).get("name", "").endswith("spawn_agent")
        and record.get("payload", {}).get("call_id") == call_id
    ]
    outputs = [
        record.get("payload", {})
        for record in parent_records
        if record.get("type") == "response_item"
        and record.get("payload", {}).get("type") == "function_call_output"
        and record.get("payload", {}).get("call_id") == call_id
    ]
    if len(calls) != 1 or len(outputs) != 1:
        return "unknown"
    output = outputs[0].get("output")
    if isinstance(output, str):
        try:
            output = json.loads(output)
        except ValueError:
            return "unknown"
    if not isinstance(output, dict) or not output.get("agent_id"):
        return "unknown"
    agent_id = str(output["agent_id"])
    matching = []
    for rollout in child_rollouts:
        metadata = [
            record.get("payload", {})
            for record in rollout
            if record.get("type") == "session_meta"
        ]
        if any(str(meta.get("id", "")) == agent_id
               and str(meta.get("parent_thread_id", "")) == parent_thread_id
               for meta in metadata):
            matching.append(rollout)
    if len(matching) != 1:
        return "unknown"
    terminal = {
        record.get("payload", {}).get("type")
        for record in matching[0]
        if record.get("type") == "event_msg"
    }
    completed = terminal.intersection({"task_complete", "turn_completed"})
    aborted = terminal.intersection({"turn_aborted"})
    if len(completed) + len(aborted) != 1:
        return "unknown"
    if completed:
        return "completed"
    if aborted:
        return "aborted"
    return "unknown"


def meta(agent_id: str, parent_thread_id: str) -> dict:
    # Codex shares session_id across a thread tree. `id` is the thread identity.
    return {"type": "session_meta", "payload": {
        "session_id": "root-thread", "id": agent_id,
        "parent_thread_id": parent_thread_id,
    }}


def result(call_id: str, agent_id: str | None) -> dict:
    output = {"agent_id": agent_id} if agent_id else {"nickname": "worker"}
    return {"type": "response_item", "payload": {
        "type": "function_call_output", "call_id": call_id,
        "output": json.dumps(output),
    }}


def spawn_call(call_id: str) -> dict:
    return {"type": "response_item", "payload": {
        "type": "function_call", "name": "multi_agent_v1.spawn_agent",
        "call_id": call_id, "arguments": "{}",
    }}


def main() -> None:
    # Deliberately interleaved siblings: explicit IDs must preserve the mapping.
    parent = [spawn_call("spawn-a"), result("spawn-a", "agent-a"),
              spawn_call("spawn-b"), result("spawn-b", "agent-b")]
    children = [
        [meta("agent-b", "root-thread"), {"type": "event_msg", "payload": {"type": "turn_aborted"}}],
        [meta("agent-a", "root-thread"), {"type": "event_msg", "payload": {"type": "task_complete"}}],
    ]
    assert child_for_spawn(parent, children, "spawn-a", "root-thread") == "completed"
    assert child_for_spawn(parent, children, "spawn-b", "root-thread") == "aborted"
    assert child_for_spawn(parent, children, "missing-call", "root-thread") == "unknown"
    assert child_for_spawn([spawn_call("spawn-a"), result("spawn-a", None)], children,
                           "spawn-a", "root-thread") == "unknown"
    assert child_for_spawn(parent, children + [[meta("agent-a", "root-thread")]],
                           "spawn-a", "root-thread") == "unknown"
    assert child_for_spawn(parent, [[meta("agent-a", "root-thread")]],
                           "spawn-a", "root-thread") == "unknown"
    assert child_for_spawn(parent, [[meta("agent-a", "other-root"),
                                    {"type": "event_msg", "payload": {"type": "task_complete"}}]],
                           "spawn-a", "root-thread") == "unknown"
    print("Synthetic Codex transcript join: 7 cases passed; runtime behavior unverified.")


if __name__ == "__main__":
    main()
