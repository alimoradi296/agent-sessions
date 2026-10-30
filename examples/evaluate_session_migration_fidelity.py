"""Synthetic source-to-projection comparison for a documented Codex edge case.

This models (it does not run) the public 16 MiB legacy migration behavior
described in Codex issues #37673 and #44141. All records and payloads are
authored here, generated in a temporary directory, and omitted from output.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from agent_sessions.parsers.codex import CodexParser

MIB = 1024 * 1024
MIGRATION_LINE_LIMIT = 16 * MIB
SESSION_ID = "synthetic-migration-fidelity"


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> list[int]:
    sizes = []
    with path.open("w", encoding="utf-8") as stream:
        for record in records:
            line = json.dumps(record, separators=(",", ":"), ensure_ascii=True)
            sizes.append(len(line.encode("utf-8")) + 1)
            stream.write(line + "\n")
    return sizes


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _parsed_messages(path: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    diagnostics = {}
    session = CodexParser.parse(path, diagnostics=diagnostics)
    if session is None:
        raise RuntimeError("authored source fixture did not parse")
    parsed = []
    for message in session.messages:
        if message.source_line is None:
            continue
        signature = (
            message.role,
            _digest(message.text),
            tuple((call.name, call.call_id, _digest(call.arguments)) for call in message.tool_calls),
            tuple((result.call_id, result.is_error, _digest(result.content)) for result in message.tool_results),
        )
        parsed.append({"line": message.source_line, "signature": signature,
                       "has_tool_result": bool(message.tool_results)})
    counts = diagnostics[str(path)]
    return parsed, {key: counts[key] for key in ("records", "handled", "ignored", "malformed", "unsupported")}


def _raw_fingerprints(path: Path) -> list[tuple[int, str]]:
    rows = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            value = json.loads(line)
            canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            rows.append((line_number, hashlib.sha256(canonical.encode("utf-8")).hexdigest()))
    return rows


def _missing_source_lines(source: list[tuple[int, Any]], destination: list[tuple[int, Any]]) -> list[int]:
    remaining = Counter(value for _, value in destination)
    missing = []
    for line, value in source:
        if remaining[value]:
            remaining[value] -= 1
        else:
            missing.append(line)
    return missing


def _semantic_missing_source_lines(source: list[dict[str, Any]], destination: list[dict[str, Any]]) -> list[int]:
    remaining = Counter(message["signature"] for message in destination)
    missing = []
    for message in source:
        signature = message["signature"]
        if remaining[signature]:
            remaining[signature] -= 1
        else:
            missing.append(message["line"])
    return missing


def _base_records() -> list[dict[str, Any]]:
    return [
        {"type": "session_meta", "payload": {"id": SESSION_ID}},
        {"type": "response_item", "payload": {
            "type": "message", "role": "user",
            "content": [{"type": "input_text", "text": "SYNTHETIC_FIRST_PROMPT"}],
        }},
        {"type": "response_item", "payload": {
            "type": "message", "role": "assistant",
            "content": [{"type": "output_text", "text": "SYNTHETIC_FIRST_ANSWER"}],
        }},
        {"type": "response_item", "payload": {
            "type": "custom_tool_call", "call_id": "synthetic-call",
            "name": "synthetic_tool", "input": {"value": "synthetic"},
        }},
        {"type": "response_item", "payload": {
            "type": "custom_tool_call_output", "call_id": "synthetic-call",
            "output": "X" * (MIGRATION_LINE_LIMIT + 128),
        }},
        {"type": "response_item", "payload": {
            "type": "message", "role": "user",
            "content": [{"type": "input_text", "text": "SYNTHETIC_SECOND_PROMPT"}],
        }},
        {"type": "response_item", "payload": {
            "type": "message", "role": "assistant",
            "content": [{"type": "output_text", "text": "SYNTHETIC_SECOND_ANSWER"}],
        }},
    ]


def _evaluate_pair(root: Path, name: str, source_records: list[dict[str, Any]],
                   destination_records: list[dict[str, Any]]) -> dict[str, Any]:
    source_path = root / f"{name}-source.jsonl"
    destination_path = root / f"{name}-destination.jsonl"
    _write_jsonl(source_path, source_records)
    _write_jsonl(destination_path, destination_records)
    source_messages, source_counts = _parsed_messages(source_path)
    destination_messages, destination_counts = _parsed_messages(destination_path)
    source_raw = _raw_fingerprints(source_path)
    destination_raw = _raw_fingerprints(destination_path)
    semantic_missing = _semantic_missing_source_lines(source_messages, destination_messages)
    raw_missing = _missing_source_lines(source_raw, destination_raw)
    raw_extra = _missing_source_lines(destination_raw, source_raw)
    source_order = [item["signature"] for item in source_messages]
    destination_order = [item["signature"] for item in destination_messages]
    return {
        "whole_file_sha256_equal": hashlib.sha256(source_path.read_bytes()).digest()
        == hashlib.sha256(destination_path.read_bytes()).digest(),
        "raw_record_multiset_equal": not raw_missing and not raw_extra,
        "raw_missing_source_lines": raw_missing,
        "raw_extra_record_count": len(raw_extra),
        "semantic_missing_source_lines": semantic_missing,
        "semantic_extra_record_count": len(_semantic_missing_source_lines(destination_messages, source_messages)),
        "semantic_order_equal": source_order == destination_order,
        "source_unsupported_record_count": source_counts["unsupported"],
        "destination_unsupported_record_count": destination_counts["unsupported"],
        "source_tool_result_lines": [item["line"] for item in source_messages if item["has_tool_result"]],
        "destination_tool_result_count": sum(item["has_tool_result"] for item in destination_messages),
        "parsed_source_message_record_count": len(source_messages),
        "parsed_destination_message_record_count": len(destination_messages),
    }


def evaluate() -> dict[str, Any]:
    records = _base_records()
    oversized_lines = [line for line, size in enumerate(
        _write_sizes(records), start=1) if size > MIGRATION_LINE_LIMIT]
    # The metadata record is line 1; all other rows retain their input order.
    # CodexParser uses those physical source-line anchors in its message records.

    with tempfile.TemporaryDirectory(prefix="synthetic-session-fidelity-") as temp:
        root = Path(temp)
        omitted = [record for record in records
                   if len(json.dumps(record, separators=(",", ":")).encode("utf-8")) <= MIGRATION_LINE_LIMIT]
        duplicated = [*records, records[2]]
        reordered = [records[0], records[2], records[1], *records[3:]]
        unsupported = [*records, {"type": "synthetic_future_record", "payload": {"note": "SYNTHETIC"}}]
        cases = {
            "unchanged_control": (records, records),
            "modeled_oversized_record_omission": (records, omitted),
            "duplicate_record": (records, duplicated),
            "reordered_messages": (records, reordered),
            "unsupported_record_omission": (unsupported, records),
        }
        results = {name: _evaluate_pair(root, name, source, destination)
                   for name, (source, destination) in cases.items()}
        return {
            "synthetic_only": True,
            "provider_migration_executed": False,
            "migration_behavior_modeled_from_public_issue_and_source": True,
            "line_limit_bytes": MIGRATION_LINE_LIMIT,
            "oversized_source_lines": oversized_lines,
            "cases": results,
            "omission_link_matches_oversized_line": results["modeled_oversized_record_omission"]["semantic_missing_source_lines"] == oversized_lines,
            "payload_text_emitted": False,
        }


def _write_sizes(records: list[dict[str, Any]]) -> list[int]:
    return [len(json.dumps(record, separators=(",", ":")).encode("utf-8")) + 1
            for record in records]


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2, sort_keys=True))
