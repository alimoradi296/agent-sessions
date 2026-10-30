"""Probe documented synthetic Cursor/Codex hook identity joins.

This reads no client configuration or transcripts and installs no hooks.
It only examines authored payload shapes and reports join ambiguity.
"""

from __future__ import annotations

import hashlib
import json


TASK = "Synthetic task: update the example retry policy."


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.strip().encode("utf-8")).hexdigest()


def cursor_start(task: str = TASK, *, subagent_id: str = "cursor-agent-1") -> dict:
    return {
        "hook_event_name": "subagentStart",
        "conversation_id": "synthetic-conversation",
        "generation_id": "synthetic-prompt-generation-1",
        "subagent_id": subagent_id,
        "tool_call_id": f"synthetic-tool-call-{subagent_id}",
        "parent_conversation_id": "synthetic-conversation",
        "task": task,
        "git_branch": "synthetic-branch",
    }


def cursor_stop(task: str = TASK) -> dict:
    return {
        "hook_event_name": "subagentStop",
        "conversation_id": "synthetic-conversation",
        "generation_id": "synthetic-prompt-generation-1",
        "subagent_type": "generalPurpose",
        "status": "completed",
        "task": task,
        "modified_files": ["synthetic/example.py"],
    }


def cursor_join(starts: list[dict], stop: dict) -> dict:
    # Cursor's documented stop payload does not include the start's subagent_id
    # or tool_call_id, so the only shared task discriminator here is task text.
    key = (stop.get("conversation_id"), _fingerprint(stop.get("task", "")))
    matches = [
        start for start in starts
        if (start.get("conversation_id"), _fingerprint(start.get("task", ""))) == key
    ]
    if len(matches) != 1:
        return {"join": "unknown", "reason": "no unique start matches stop task fingerprint"}
    return {
        "join": "weak_task_fingerprint_match",
        "attempt_id": matches[0]["subagent_id"],
        "terminal_status": stop.get("status"),
        "raw_task_text_persisted": False,
    }


def codex_pretool() -> dict:
    return {
        "hook_event_name": "PreToolUse",
        "session_id": "synthetic-session",
        "turn_id": "synthetic-turn-1",
        "tool_name": "Agent",
        "tool_use_id": "synthetic-tool-call-1",
        "tool_input": {"prompt": TASK, "description": "Synthetic task"},
    }


def codex_subagent_start() -> dict:
    return {
        "hook_event_name": "SubagentStart",
        "session_id": "synthetic-session",
        "turn_id": "synthetic-turn-1",
        "agent_id": "synthetic-agent-1",
        "agent_type": "general",
    }


def codex_subagent_stop() -> dict:
    return {
        "hook_event_name": "SubagentStop",
        "session_id": "synthetic-session",
        "turn_id": "synthetic-turn-1",
        "agent_id": "synthetic-agent-1",
        "agent_type": "general",
        "last_assistant_message": "Synthetic completion.",
    }


def codex_join(pretool: dict, start: dict, stop: dict) -> dict:
    # The direct documented hook payloads give a tool_use_id before dispatch
    # and agent_id at lifecycle start/stop, but no shared identifier between
    # those records. A single turn is not a safe join key for parallel agents.
    pretool_key = (pretool.get("session_id"), pretool.get("turn_id"), pretool.get("tool_use_id"))
    lifecycle_key = (start.get("session_id"), start.get("turn_id"), start.get("agent_id"))
    stop_key = (stop.get("session_id"), stop.get("turn_id"), stop.get("agent_id"))
    lifecycle_pairs = lifecycle_key == stop_key
    return {
        "pretool_to_agent_join": "unknown",
        "reason": "documented hook payloads share no invocation-to-agent identifier",
        "agent_start_stop_pair": "matched_by_agent_id" if lifecycle_pairs else "unknown",
        "pretool_invocation_fingerprint": hashlib.sha256(repr(pretool_key).encode()).hexdigest(),
        "task_text_persisted": False,
    }


def evaluate() -> dict:
    one_cursor_start = cursor_start()
    parallel_cursor_starts = [one_cursor_start, cursor_start(subagent_id="cursor-agent-2")]
    cursor_one = cursor_join([one_cursor_start], cursor_stop())
    cursor_ambiguous = cursor_join(parallel_cursor_starts, cursor_stop())
    codex = codex_join(codex_pretool(), codex_subagent_start(), codex_subagent_stop())
    return {
        "synthetic_only": True,
        "cursor_unique_task_fingerprint": cursor_one,
        "cursor_duplicate_parallel_task_fingerprint": cursor_ambiguous,
        "codex_documented_hook_join": codex,
        "limits": [
            "Cursor stop-to-start matching by task text is a heuristic, not a stable native task identity.",
            "Cursor identical parallel task descriptions are ambiguous and must remain unknown.",
            "Codex direct hook payloads can identify a tool invocation and a subagent lifecycle separately but do not document a shared join key.",
            "This probe does not read transcripts, call a provider, install hooks, or measure task-state truth.",
            "No production block decision is justified by these payload-shape probes.",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2))
