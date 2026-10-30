"""Probe recovery of an unavailable subagent result from a synthetic transcript.

This is an authored-format feasibility probe. It never reads a caller's archive
or contacts a provider. The transcript fields are based on public format
descriptions, not a captured current-version session.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from agent_sessions.parsers.claude import ClaudeParser


def _records(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _text_blocks(message: dict[str, Any]) -> str:
    content = message.get("content", [])
    if not isinstance(content, list):
        return content if isinstance(content, str) else ""
    return "\n".join(
        block["text"] for block in content
        if isinstance(block, dict) and block.get("type") == "text"
        and isinstance(block.get("text"), str)
    )


def _recover_candidate(parent_path: Path) -> dict[str, Any]:
    """Recover one final text candidate only when parent and child linkage agree."""
    parent_records = _records(parent_path)
    children: dict[str, list[tuple[str, str]]] = {}

    for record in parent_records:
        if record.get("type") != "assistant":
            continue
        envelope = record.get("toolUseResult")
        message = record.get("message")
        if not isinstance(envelope, dict) or not isinstance(message, dict):
            continue
        agent_id = envelope.get("agentId")
        if not isinstance(agent_id, str) or not agent_id:
            continue
        blocks = message.get("content", [])
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            if (isinstance(block, dict) and block.get("type") == "tool_use"
                    and block.get("name") == "Agent" and isinstance(block.get("id"), str)):
                children.setdefault(block["id"], []).append(
                    (agent_id, str(envelope.get("status", "unknown"))))

    missing_handles: set[str] = set()
    for record in parent_records:
        if record.get("type") != "user":
            continue
        message = record.get("message")
        content = message.get("content", []) if isinstance(message, dict) else []
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_result":
                continue
            call_id = block.get("tool_use_id")
            if call_id not in children:
                continue
            result = block.get("content", "")
            result_text = result if isinstance(result, str) else _text_blocks({"content": result})
            if not result_text.strip() or "no output captured" in result_text.lower():
                missing_handles.add(call_id)

    candidates: list[dict[str, Any]] = []
    for call_id in sorted(missing_handles):
        linked_children = children.get(call_id, [])
        if len(linked_children) != 1:
            continue
        agent_id, status = linked_children[0]
        if status != "completed":
            continue
        child_path = parent_path.with_suffix("") / "subagents" / f"agent-{agent_id}.jsonl"
        if not child_path.is_file():
            continue
        last_assistant = None
        for record in _records(child_path):
            if record.get("type") != "assistant" or record.get("isSidechain") is not True:
                continue
            last_assistant = record
        if last_assistant is None:
            continue
        message = last_assistant.get("message")
        if not isinstance(message, dict):
            continue
        blocks = message.get("content", [])
        if isinstance(blocks, list) and any(
            isinstance(block, dict) and block.get("type") == "tool_use" for block in blocks
        ):
            continue
        stop_reason = message.get("stop_reason", last_assistant.get("stop_reason"))
        text = _text_blocks(message)
        if stop_reason == "end_turn" and text.strip():
            candidates.append({"call_id": call_id, "agent_id": agent_id, "text": text.strip()})

    if len(candidates) != 1:
        return {"recovered": False, "reason": "no_unique_final_result", "candidate_count": len(candidates)}
    item = candidates[0]
    return {"recovered": True, "call_id": item["call_id"], "agent_id": item["agent_id"],
            "text": item["text"], "source": "linked_sidechain_final_record"}


def evaluate() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="synthetic-subagent-output-") as temp:
        projects = Path(temp) / "projects"
        project = projects / "synthetic-project"
        cases = {
            "valid_linked_child": {"status": "completed", "child": "present", "final": True, "duplicate": False, "expected": True},
            "missing_child_file": {"status": "completed", "child": "missing", "final": True, "duplicate": False, "expected": False},
            "failed_child": {"status": "error", "child": "present", "final": True, "duplicate": False, "expected": False},
            "no_terminal_final": {"status": "completed", "child": "present", "final": False, "duplicate": False, "expected": False},
            "ambiguous_parent_link": {"status": "completed", "child": "present", "final": True, "duplicate": True, "expected": False},
            "nested_result_missing": {"status": "completed", "child": "nested", "final": False, "duplicate": False, "expected": False},
            "stale_earlier_final": {"status": "completed", "child": "stale", "final": False, "duplicate": False, "expected": False},
        }
        case_paths: dict[str, Path] = {}

        for name, case in cases.items():
            session_id = f"synthetic-{name}"
            parent_path = project / f"{session_id}.jsonl"
            child_dir = project / session_id / "subagents"
            child_dir.mkdir(parents=True)
            agent_id = "synthetic-child"
            call_id = "call-synthetic"
            assistant = {"type": "assistant", "sessionId": session_id,
                         "toolUseResult": {"agentId": agent_id, "status": case["status"]},
                         "message": {"content": [{"type": "tool_use", "id": call_id,
                                                     "name": "Agent", "input": {"description": "Synthetic child task"}}]}}
            parent = [
                {"type": "user", "sessionId": session_id, "message": {"content": "Synthetic task"}},
                assistant,
                {"type": "user", "sessionId": session_id,
                 "message": {"content": [{"type": "tool_result", "tool_use_id": call_id,
                                             "content": "No output captured."}]}},
            ]
            if case["duplicate"]:
                duplicate = json.loads(json.dumps(assistant))
                duplicate["toolUseResult"]["agentId"] = "synthetic-other-child"
                parent.insert(2, duplicate)
                duplicate_dir = project / session_id / "subagents"
                duplicate_child = [
                    {"type": "assistant", "sessionId": session_id, "isSidechain": True,
                     "message": {"stop_reason": "end_turn", "content": [{"type": "text", "text": "SYNTHETIC_OTHER_RESULT"}]}},
                ]
                (duplicate_dir / "agent-synthetic-other-child.jsonl").write_text(
                    "".join(json.dumps(row) + "\n" for row in duplicate_child), encoding="utf-8")
            if case["child"] in ("present", "nested", "stale"):
                child = [{"type": "user", "sessionId": session_id, "isSidechain": True,
                          "message": {"content": "Synthetic child task"}}]
                if case["child"] == "nested":
                    child.extend([
                        {"type": "assistant", "sessionId": session_id, "isSidechain": True,
                         "toolUseResult": {"agentId": "synthetic-grandchild", "status": "completed"},
                         "message": {"stop_reason": "tool_use", "content": [
                             {"type": "tool_use", "id": "call-grandchild", "name": "Agent", "input": {}}]}},
                        {"type": "user", "sessionId": session_id, "isSidechain": True,
                         "message": {"content": [{"type": "tool_result", "tool_use_id": "call-grandchild",
                                                     "content": "No output captured."}]}},
                    ])
                    grandchild = [{"type": "assistant", "sessionId": session_id, "isSidechain": True,
                                   "message": {"stop_reason": "end_turn", "content": [
                                       {"type": "text", "text": "SYNTHETIC_GRANDCHILD_RESULT"}]}}]
                    (child_dir / "agent-synthetic-grandchild.jsonl").write_text(
                        "".join(json.dumps(row) + "\n" for row in grandchild), encoding="utf-8")
                elif case["child"] == "stale":
                    child.extend([
                        {"type": "assistant", "sessionId": session_id, "isSidechain": True,
                         "message": {"stop_reason": "end_turn", "content": [
                             {"type": "text", "text": "SYNTHETIC_OLD_RESULT"}]}},
                        {"type": "assistant", "sessionId": session_id, "isSidechain": True,
                         "message": {"stop_reason": None, "content": [
                             {"type": "text", "text": "SYNTHETIC_UNCONFIRMED_RESULT"}]}},
                    ])
                else:
                    child.append(
                        {"type": "assistant", "sessionId": session_id, "isSidechain": True,
                         "message": {"stop_reason": "end_turn" if case["final"] else None,
                                     "content": [{"type": "text", "text": "SYNTHETIC_CHILD_RESULT"}]}}
                    )
                (child_dir / f"agent-{agent_id}.jsonl").write_text(
                    "".join(json.dumps(row) + "\n" for row in child), encoding="utf-8")
            parent_path.write_text("".join(json.dumps(row) + "\n" for row in parent), encoding="utf-8")
            case_paths[name] = parent_path

        parent_path = case_paths["valid_linked_child"]

        original = ClaudeParser.find_sessions_dir
        ClaudeParser.find_sessions_dir = classmethod(lambda cls: projects)
        try:
            discovered = ClaudeParser.list_sessions()
            parsed_parent = ClaudeParser.parse(parent_path)
            child_path = project / parent_path.stem / "subagents" / "agent-synthetic-child.jsonl"
            parsed_child = ClaudeParser.parse(child_path)
            case_results = {
                name: _recover_candidate(path).get("recovered", False)
                for name, path in case_paths.items()
            }
            return {
                "synthetic_only": True,
                "source_files_discovered": len(discovered),
                "current_parent_parse_succeeds": parsed_parent is not None,
                "current_parent_tool_result_count": sum(
                    len(message.tool_results) for message in parsed_parent.messages
                ) if parsed_parent else 0,
                "current_child_parse_succeeds": parsed_child is not None,
                "prototype_cases": case_results,
                "all_expected_cases_match": all(case_results[name] == case["expected"] for name, case in cases.items()),
                "valid_result_source_link_verified": case_results["valid_linked_child"],
                "prototype_result_text_emitted": False,
                "limit": "One authored sidechain shape; no current provider runtime or competing viewer was run.",
            }
        finally:
            ClaudeParser.find_sessions_dir = original


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2, sort_keys=True))
