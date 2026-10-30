"""Reproduce oversized Codex legacy-rollout migration behavior with synthetic data.

The probe runs only when explicitly invoked. It creates isolated temporary
Codex homes, disables telemetry, and prints counts and source line numbers only.
No existing Codex profile or session file is read.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from examples.evaluate_session_migration_fidelity import (
    MIGRATION_LINE_LIMIT,
    _parsed_messages,
    _semantic_missing_source_lines,
)

THREAD_ID = "00000000-0000-4000-8000-000000000001"
TIMESTAMP = "2026-10-28T12:00:00Z"


def _meta() -> dict[str, Any]:
    return {
        "attached_thread": False,
        "creator_user_id": None,
        "creator_account_id": None,
        "session_id": THREAD_ID,
        "id": THREAD_ID,
        "forked_from_id": None,
        "forked_from_ordinal_exclusive": None,
        "parent_thread_id": None,
        "timestamp": TIMESTAMP,
        "cwd": "/",
        "runtime_workspace_roots": None,
        "originator": "codex",
        "cli_version": "0.0.0",
        "source": "cli",
        "thread_source": None,
        "agent_path": None,
        "agent_nickname": None,
        "agent_role": None,
        "model_provider": "synthetic-provider",
        "base_instructions": None,
        "dynamic_tools": None,
        "selected_capability_roots": [],
        "memory_mode": None,
        "history_mode": "legacy",
        "history_base": None,
        "subagent_history_start_ordinal": None,
        "multi_agent_version": None,
        "context_window": None,
        "git": None,
    }


def _write_source(path: Path, assistant_text: str) -> None:
    prompt = "SYNTHETIC_PROMPT"
    records = [
        {
            "timestamp": TIMESTAMP,
            "type": "session_meta",
            "payload": _meta(),
        },
        {
            "timestamp": TIMESTAMP,
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": prompt}],
            },
        },
        {
            "timestamp": TIMESTAMP,
            "type": "event_msg",
            "payload": {"type": "user_message", "message": prompt, "kind": "plain"},
        },
        {
            "timestamp": TIMESTAMP,
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": assistant_text}],
            },
        },
    ]
    with path.open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, separators=(",", ":")) + "\n")


def _isolated_env(codex_home: Path, home: Path) -> dict[str, str]:
    return {
        "PATH": os.environ.get("PATH", os.defpath),
        "HOME": str(home),
        "CODEX_HOME": str(codex_home),
        "DO_NOT_TRACK": "1",
        "OTEL_SDK_DISABLED": "true",
        "CODEX_CLI_NO_AUTO_UPDATE": "1",
    }


def _run_case(binary: str, root: Path, name: str, assistant_text: str) -> dict[str, Any]:
    case_root = root / name
    codex_home = case_root / "codex-home"
    sessions = codex_home / "sessions" / "2026" / "10"
    sessions.mkdir(parents=True)
    source = sessions / f"rollout-2026-10-28T12-00-00-{THREAD_ID}.jsonl"
    _write_source(source, assistant_text)
    source_bytes = source.stat().st_size
    source_copy = case_root / "source-before-migration.jsonl"
    shutil.copyfile(source, source_copy)

    try:
        process = subprocess.run(
            [binary, "migrate-rollouts", "--apply", "--thread", THREAD_ID, "--json"],
            env=_isolated_env(codex_home, case_root),
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"source_bytes": source_bytes, "comparison_complete": False}
    try:
        report = json.loads(process.stdout)
        outcome = report["outcomes"][0]
    except (json.JSONDecodeError, KeyError, IndexError, TypeError):
        return {
            "exit_code": process.returncode,
            "report_parseable": False,
            "source_bytes": source_bytes,
        }

    migrated_files = list(codex_home.rglob("*.jsonl"))
    if len(migrated_files) != 1:
        return {
            "exit_code": process.returncode,
            "status": outcome.get("status"),
            "failure_reason": outcome.get("failure_reason"),
            "source_bytes": source_bytes,
            "migrated_jsonl_count": len(migrated_files),
            "comparison_complete": False,
        }

    try:
        source_messages, _ = _parsed_messages(source_copy)
        migrated_messages, _ = _parsed_messages(migrated_files[0])
    except (OSError, RuntimeError, ValueError):
        return {
            "exit_code": process.returncode,
            "status": outcome.get("status"),
            "failure_reason": outcome.get("failure_reason"),
            "source_bytes": source_bytes,
            "comparison_complete": False,
        }
    missing_lines = _semantic_missing_source_lines(source_messages, migrated_messages)
    return {
        "exit_code": process.returncode,
        "status": outcome.get("status"),
        "failure_reason": outcome.get("failure_reason"),
        "source_bytes": source_bytes,
        "migrated_bytes": migrated_files[0].stat().st_size,
        "source_message_count": len(source_messages),
        "migrated_message_count": len(migrated_messages),
        "missing_source_lines": missing_lines,
        "comparison_complete": True,
    }


def evaluate(binary: str | None = None) -> dict[str, Any]:
    binary = binary or shutil.which("codex")
    if not binary:
        return {"codex_available": False, "synthetic_only": True}

    with tempfile.TemporaryDirectory(prefix="synthetic-codex-migration-probe-") as temp:
        root = Path(temp)
        version_home = root / "version-home"
        version_home.mkdir()
        try:
            version = subprocess.run(
                [binary, "--version"],
                env=_isolated_env(version_home / "codex-home", version_home),
                text=True,
                capture_output=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return {"codex_available": False, "synthetic_only": True}
        if version.returncode:
            return {"codex_available": False, "synthetic_only": True}
        small = _run_case(binary, root, "small-control", "SYNTHETIC_ANSWER_" + "X" * 128)
        oversized = _run_case(
            binary,
            root,
            "oversized-response",
            "SYNTHETIC_ANSWER_" + "X" * (MIGRATION_LINE_LIMIT + 128),
        )
    return {
        "codex_available": True,
        "codex_version": version.stdout.strip(),
        "synthetic_only": True,
        "provider_data_read": False,
        "telemetry_disabled": True,
        "line_limit_bytes": MIGRATION_LINE_LIMIT,
        "small_control": small,
        "oversized_response": oversized,
        "reproduced_migrated_status_with_loss": (
            small.get("comparison_complete") is True
            and small.get("status") == "migrated"
            and not small.get("missing_source_lines")
            and oversized.get("comparison_complete") is True
            and oversized.get("status") == "migrated"
            and 4 in oversized.get("missing_source_lines", [])
        ),
        "payload_text_emitted": False,
    }


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2, sort_keys=True))
