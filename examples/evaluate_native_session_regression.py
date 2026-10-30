"""Probe native-session evidence for a proposed regression case.

All transcripts are synthetic and temporary. The report contains only provider
names, event counts, and source line numbers. It does not emit transcript text.
This checks evidence extraction, not whether the historical change was correct
or whether the case can be replayed in its original environment.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from agent_sessions.parsers.claude import ClaudeParser
from agent_sessions.parsers.codex import CodexParser
from agent_sessions.parsers.cursor import CursorParser
from agent_sessions.analysis.captured_files import _apply_exact_update, _operations


REQUEST = ("Add count_valid(rows). For ['valid', 'invalid', 'valid'], it must return 2; "
           "ignore invalid rows.")
FAILURE = "AssertionError: expected 2 valid rows; received 1"
PATCH = ("*** Begin Patch\n*** Update File: parser.py\n@@\n"
         " # Existing parser.\n"
         " def count_valid(rows):\n-    return 1\n+    return 2\n*** End Patch")
PASS = "1 passed"
COMMAND = "python tests/test_parser.py"
TEST_MARKERS = ("pytest", "unittest", "npm test", "pnpm test", "yarn test",
                "cargo test", "go test", "make test", "vitest", "jest")


def _write(path: Path, records: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in records), encoding="utf-8")
    return path


def _archives(root: Path) -> list[tuple[str, Path, type]]:
    claude = _write(root / "claude" / "synthetic-claude.jsonl", [
        {"type": "user", "message": {"content": [{"type": "text", "text": REQUEST}]}},
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "call-fail", "name": "Bash",
             "input": {"command": COMMAND}},
        ]}},
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "call-fail", "content": FAILURE,
             "is_error": True},
        ]}},
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "call-edit", "name": "apply_patch",
             "input": {"patch": PATCH}},
        ]}},
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "call-edit", "content": "Patch applied",
             "is_error": False},
        ]}},
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "call-pass", "name": "Bash",
             "input": {"command": COMMAND}},
        ]}},
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "call-pass", "content": PASS,
             "is_error": False},
        ]}},
    ])

    codex = _write(root / "codex" / "synthetic-codex.jsonl", [
        {"type": "session_meta", "payload": {"id": "synthetic-codex"}},
        {"type": "response_item", "payload": {"type": "message", "role": "user",
         "content": [{"type": "input_text", "text": REQUEST}]}},
        {"type": "response_item", "payload": {"type": "function_call", "call_id": "call-fail",
         "name": "exec_command", "arguments": json.dumps({"cmd": COMMAND})}},
        {"type": "response_item", "payload": {"type": "function_call_output", "call_id": "call-fail",
         "output": {"exit_code": 1, "stderr": FAILURE}}},
        {"type": "response_item", "payload": {"type": "function_call", "call_id": "call-edit",
         "name": "apply_patch", "arguments": PATCH}},
        {"type": "response_item", "payload": {"type": "function_call_output", "call_id": "call-edit",
         "output": {"exit_code": 0, "stdout": "Patch applied"}}},
        {"type": "response_item", "payload": {"type": "function_call", "call_id": "call-pass",
         "name": "exec_command", "arguments": json.dumps({"cmd": COMMAND})}},
        {"type": "response_item", "payload": {"type": "function_call_output", "call_id": "call-pass",
         "output": {"exit_code": 0, "stdout": PASS}}},
    ])

    cursor = _write(root / "cursor" / "agent-transcripts" / "synthetic-cursor"
                    / "synthetic-cursor.jsonl", [
        {"role": "user", "message": {"content": [{"type": "text", "text": REQUEST}]}},
        {"role": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "call-fail", "name": "run_terminal_command",
             "input": {"command": COMMAND}},
        ]}},
        {"role": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "call-fail", "content": FAILURE,
             "is_error": True},
        ]}},
        {"role": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "call-edit", "name": "apply_patch",
             "input": {"patch": PATCH}},
        ]}},
        {"role": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "call-edit", "content": "Patch applied",
             "is_error": False},
        ]}},
        {"role": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "call-pass", "name": "run_terminal_command",
             "input": {"command": COMMAND}},
        ]}},
        {"role": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "call-pass", "content": PASS,
             "is_error": False},
        ]}},
    ])
    return [
        ("claude", claude, ClaudeParser),
        ("codex", codex, CodexParser),
        ("cursor", cursor, CursorParser),
    ]


def _result_status(result) -> str:
    if result.is_error is True:
        return "failed"
    if result.is_error is False:
        return "success"
    try:
        parsed = json.loads(result.content)
    except (TypeError, ValueError):
        return "unknown"
    if isinstance(parsed, dict) and isinstance(parsed.get("exit_code"), int):
        return "success" if parsed["exit_code"] == 0 else "failed"
    return "unknown"


def _result_text(result) -> str | None:
    if result.is_error is True:
        return None
    try:
        parsed = json.loads(result.content)
    except (TypeError, ValueError):
        return result.content if isinstance(result.content, str) else None
    if isinstance(parsed, dict):
        if parsed.get("exit_code") not in (None, 0):
            return None
        for key in ("stdout", "output"):
            if isinstance(parsed.get(key), str):
                return parsed[key]
    return result.content if isinstance(result.content, str) else None


def _command(arguments: str) -> str | None:
    try:
        value = json.loads(arguments)
    except (TypeError, ValueError):
        return None
    if not isinstance(value, dict):
        return None
    command = value.get("command") or value.get("cmd")
    return " ".join(command.split()) if isinstance(command, str) else None


def _is_test_command(command: str | None) -> bool:
    return bool(command and (_test_path(command)
                             or any(marker in command.lower() for marker in TEST_MARKERS)))


def _patch_paths(arguments: str) -> list[str]:
    value = _patch_text(arguments)
    return re.findall(r"^\*\*\* (?:Update|Add|Delete) File: (.+)$", value, re.MULTILINE)


def _patch_text(arguments: str) -> str:
    try:
        value = json.loads(arguments)
    except (TypeError, ValueError):
        value = arguments
    if isinstance(value, dict):
        value = value.get("patch") or value.get("input") or ""
    return value if isinstance(value, str) else ""


def _test_path(command: str | None) -> str | None:
    if not command:
        return None
    candidates = re.findall(r"(?<!\S)[\w./-]+\.(?:py|js|jsx|ts|tsx|go|rs)(?!\S)", command)
    return next((path for path in candidates if re.search(
        r"(?:^|[/_.-])(?:test|tests|spec)(?:[/_.-]|$)", path, re.IGNORECASE)), None)


def _path_tokens(path: str | None) -> set[str]:
    if not path:
        return set()
    stem = Path(path).stem.lower()
    stem = re.sub(r"^(?:test|tests|spec)[_-]", "", stem)
    stem = re.sub(r"[_-](?:test|tests|spec)$", "", stem)
    return set(re.findall(r"[a-z0-9]+", stem)) - {"test", "tests", "spec", "testcase"}


def _related_paths(test_path: str | None, changed_path: str | None) -> bool:
    """Use filename overlap to reject obvious unrelated edits, not prove causality."""
    return bool(_path_tokens(test_path) & _path_tokens(changed_path))


def _baseline_evidence(session) -> dict:
    calls_by_id = {}
    commit = None
    clean_status = False
    working_directory_recorded = bool(session.cwd)
    for message_index, message in enumerate(session.messages, 1):
        for call in message.tool_calls:
            calls_by_id.setdefault(call.call_id, []).append((message_index, call))
        for result in message.tool_results:
            matches = calls_by_id.get(result.call_id, [])
            if len(matches) != 1:
                continue
            _, call = matches[0]
            command = _command(call.arguments)
            output = _result_text(result)
            if command == "pwd":
                working_directory_recorded = bool(output and Path(output.strip()).is_absolute())
            elif command in {"git rev-parse HEAD", "git rev-parse --verify HEAD"}:
                if output and re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", output.strip()):
                    commit = output.strip()
            elif command in {"git status --porcelain", "git status --short"}:
                clean_status = output == ""
    return {
        "commit_pin_present": commit is not None,
        "clean_worktree_recorded": clean_status,
        "working_directory_recorded": working_directory_recorded,
        "commit_hash_emitted": False,
        "ready_from_archive_evidence": (commit is not None and clean_status
                                         and working_directory_recorded),
    }


def _run_synthetic_test(project: Path) -> int:
    result = subprocess.run(
        [sys.executable, "tests/test_parser.py"],
        cwd=project, capture_output=True, text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        check=False,
    )
    return result.returncode


def _replay_in_synthetic_project(patch: str) -> dict:
    with tempfile.TemporaryDirectory(prefix="synthetic-regression-replay-") as directory:
        project = Path(directory)
        source = project / "parser.py"
        source.write_text("# Existing parser.\ndef count_valid(rows):\n    return 1\n",
                          encoding="utf-8")
        tests = project / "tests" / "test_parser.py"
        tests.parent.mkdir()
        tests.write_text(
            "from pathlib import Path\nimport sys\nimport unittest\n"
            "sys.path.insert(0, str(Path(__file__).resolve().parents[1]))\n"
            "from parser import count_valid\n\n"
            "class ParserTests(unittest.TestCase):\n"
            "    def test_counts_valid_rows(self):\n"
            "        self.assertEqual(count_valid(['valid', 'invalid', 'valid']), 2)\n\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n",
            encoding="utf-8",
        )
        before = _run_synthetic_test(project)
        patch_applied = False
        try:
            operations = _operations(patch)
            for operation, relative, body in operations:
                target = (project / relative).resolve()
                target.relative_to(project.resolve())
                if operation == "update" and target.is_file():
                    target.write_text(_apply_exact_update(
                        target.read_text(encoding="utf-8"), body), encoding="utf-8")
                    patch_applied = True
            after = _run_synthetic_test(project) if patch_applied else None
        except (ValueError, OSError):
            after = None
        return {
            "baseline_exit_code": before,
            "captured_patch_applied": patch_applied,
            "rerun_exit_code": after,
            "patch_reproduces_in_authored_fixture": before != 0 and after == 0,
            "expected_behavior_source": "authored synthetic test oracle",
            "archive_base_commit_present": False,
            "archive_clean_worktree_evidence_present": False,
            "replayable_from_archive": False,
        }


def _candidate(agent: str, label: str, parser, path: Path) -> dict:
    session = parser.parse(path)
    if session is None:
        raise ValueError(f"Synthetic {agent} transcript did not parse")
    requests = []
    calls_by_id: dict[str, list[tuple[int, object, int | None]]] = {}
    results = []
    edits = []
    for message_index, message in enumerate(session.messages, 1):
        if message.role == "user" and message.text.strip():
            requests.append((message_index, message.source_line))
        for call in message.tool_calls:
            calls_by_id.setdefault(call.call_id, []).append(
                (message_index, call, message.source_line))
            if call.name in {"apply_patch", "functions.apply_patch"}:
                edits.extend((message_index, message.source_line, changed_path,
                              _patch_text(call.arguments))
                             for changed_path in _patch_paths(call.arguments))
        for result in message.tool_results:
            matches = calls_by_id.get(result.call_id, [])
            if len(matches) == 1:
                call_index, call, call_line = matches[0]
                results.append({
                    "call_index": call_index,
                    "result_index": message_index,
                    "command": _command(call.arguments),
                    "status": _result_status(result),
                    "call_line": call_line,
                    "result_line": message.source_line,
                })

    linked_tests = [row for row in results if _is_test_command(row["command"])]
    sequence = None
    for failed in linked_tests:
        if failed["status"] != "failed":
            continue
        for edit_index, edit_line, changed_path, patch in edits:
            if edit_index <= failed["result_index"]:
                continue
            if not _related_paths(_test_path(failed["command"]), changed_path):
                continue
            for passed in linked_tests:
                if (passed["status"] == "success"
                        and passed["command"] == failed["command"]
                        and passed["call_index"] > edit_index):
                    sequence = (failed, (edit_index, edit_line, changed_path, patch), passed)
                    break
            if sequence:
                break
        if sequence:
            break

    extractable = bool(requests and sequence)
    if sequence:
        failed, edit, passed = sequence
        refs = {
            "task_request": requests[0],
            "failed_test_call": (failed["call_index"], failed["call_line"]),
            "failed_test_result": (failed["result_index"], failed["result_line"]),
            "captured_edit": edit[:2],
            "edit_test_path_overlap": True,
            "successful_test_call": (passed["call_index"], passed["call_line"]),
            "successful_test_result": (passed["result_index"], passed["result_line"]),
        }
    else:
        edit = edits[0] if edits else None
        refs = {
            "task_request": requests[0] if requests else None,
            "failed_test_call": None,
            "failed_test_result": None,
            "captured_edit": edit[:2] if edit else None,
            "edit_test_path_overlap": False,
            "successful_test_call": None,
            "successful_test_result": None,
        }
    replay = _replay_in_synthetic_project(sequence[1][3]) if sequence else None
    return {
        "agent": agent,
        "synthetic_case": label,
        "candidate_evidence_found": extractable,
        "false_candidate_control": label.endswith("control") and extractable,
        "source_refs": refs,
        "review_gate": "required_before_acceptance" if extractable else "not_applicable",
        "replay": replay,
        "replayable": bool(replay and replay["replayable_from_archive"]),
        "not_established": [
            "The archive does not prove that the correction is the intended behavior.",
            "The pre-change repository state and dependency environment were not captured.",
            "The successful command is evidence from the session, not an independent rerun.",
        ],
        "transcript_text_in_report": False,
    }


def _cursor_control(path: Path, *, failure: str | None,
                    failure_command: str = "python -m pip install fictional-test-dependency",
                    patch: str = PATCH) -> Path:
    records = [
        {"role": "user", "message": {"content": [{"type": "text", "text": REQUEST}]}},
    ]
    if failure is not None:
        records.extend([
            {"role": "assistant", "message": {"content": [
                {"type": "tool_use", "id": "control-fail", "name": "run_terminal_command",
                 "input": {"command": failure_command}},
            ]}},
            {"role": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": "control-fail", "content": failure,
                 "is_error": True},
            ]}},
        ])
    records.extend([
        {"role": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "control-edit", "name": "apply_patch",
             "input": {"patch": patch}},
        ]}},
        {"role": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "control-edit", "content": "Patch applied",
             "is_error": False},
        ]}},
        {"role": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "control-pass", "name": "run_terminal_command",
             "input": {"command": COMMAND}},
        ]}},
        {"role": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "control-pass", "content": PASS,
             "is_error": False},
        ]}},
    ])
    return _write(path, records)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", *args], cwd=repo,
        check=True, capture_output=True, text=True,
        env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull},
    )
    return result.stdout.strip()


def _baseline_probe(root: Path, agent: str, label: str, *, dirty: bool,
                    include_status: bool) -> dict:
    repo = root / f"baseline-{label}"
    repo.mkdir()
    (repo / "parser.py").write_text("# Synthetic baseline.\n", encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "add", "parser.py")
    _git(repo, "-c", "user.name=Synthetic", "-c",
         "user.email=synthetic@example.invalid", "commit", "-qm", "baseline")
    if dirty:
        (repo / "untracked.txt").write_text("synthetic dirty state\n", encoding="utf-8")
    commit = _git(repo, "rev-parse", "HEAD")
    status = _git(repo, "status", "--porcelain")
    evidence = [
        ("pwd", str(repo)),
        ("git rev-parse HEAD", commit),
    ]
    if include_status:
        evidence.append(("git status --porcelain", status))
    records = []
    if agent == "claude":
        records.append({"type": "user", "cwd": str(repo), "message": {"content": [
            {"type": "text", "text": "Inspect a fictional repository baseline."},
        ]}})
        for index, (command, output) in enumerate(evidence, 1):
            call_id = f"base-{index}"
            records.extend([
                {"type": "assistant", "cwd": str(repo), "message": {"content": [
                    {"type": "tool_use", "id": call_id, "name": "Bash",
                     "input": {"command": command}},
                ]}},
                {"type": "user", "cwd": str(repo), "message": {"content": [
                    {"type": "tool_result", "tool_use_id": call_id, "content": output,
                     "is_error": False},
                ]}},
            ])
        parser = ClaudeParser
        path = _write(root / "claude" / label / f"{label}.jsonl", records)
    elif agent == "codex":
        records.append({"type": "session_meta", "payload": {"id": label, "cwd": str(repo)}})
        records.append({"type": "response_item", "payload": {"type": "message", "role": "user",
                         "content": [{"type": "input_text", "text": "Inspect a fictional repository baseline."}]}})
        for index, (command, output) in enumerate(evidence, 1):
            call_id = f"base-{index}"
            records.extend([
                {"type": "response_item", "payload": {"type": "function_call", "call_id": call_id,
                 "name": "exec_command", "arguments": json.dumps({"cmd": command})}},
                {"type": "response_item", "payload": {"type": "function_call_output", "call_id": call_id,
                 "output": {"exit_code": 0, "stdout": output}}},
            ])
        parser = CodexParser
        path = _write(root / "codex" / f"{label}.jsonl", records)
    else:
        records.append({"role": "user", "message": {"content": [
            {"type": "text", "text": "Inspect a fictional repository baseline."},
        ]}})
        for index, (command, output) in enumerate(evidence, 1):
            call_id = f"base-{index}"
            records.extend([
                {"role": "assistant", "message": {"content": [
                    {"type": "tool_use", "id": call_id, "name": "run_terminal_command",
                     "input": {"command": command}},
                ]}},
                {"role": "user", "message": {"content": [
                    {"type": "tool_result", "tool_use_id": call_id, "content": output,
                     "is_error": False},
                ]}},
            ])
        parser = CursorParser
        path = _write(
            root / "cursor" / "projects" / label / "agent-transcripts" / label / f"{label}.jsonl",
            records,
        )
    session = parser.parse(path)
    if session is None:
        raise ValueError("Synthetic Cursor baseline transcript did not parse")
    evidence_report = _baseline_evidence(session)
    evidence_report["git_object_still_available"] = _git(repo, "cat-file", "-e", commit) == ""
    return evidence_report


def evaluate() -> dict:
    with tempfile.TemporaryDirectory(prefix="synthetic-session-regression-") as directory:
        root = Path(directory)
        cases = [_candidate(agent, "authored_positive", parser, path)
                 for agent, path, parser in _archives(root)]
        clean = _cursor_control(root / "cursor-clean.jsonl", failure=None)
        unrelated = _cursor_control(
            root / "cursor-unrelated-failure.jsonl",
            failure="AssertionError in unrelated test suite",
            failure_command="python -m pytest -q tests/test_network.py",
        )
        flaky = _cursor_control(
            root / "cursor-flaky-test.jsonl",
            failure=FAILURE,
            failure_command=COMMAND,
            patch="*** Begin Patch\n*** Update File: README.md\n@@\n-Fictional docs cleanup.\n+Updated fictional docs.\n*** End Patch",
        )
        unrelated_code = _cursor_control(
            root / "cursor-unrelated-code.jsonl",
            failure=FAILURE,
            failure_command=COMMAND,
            patch="*** Begin Patch\n*** Update File: helper.py\n@@\n-def helper():\n+def helper():\n*** End Patch",
        )
        same_target_flaky = _cursor_control(
            root / "cursor-same-target-flaky.jsonl",
            failure=FAILURE,
            failure_command=COMMAND,
            patch=("*** Begin Patch\n*** Update File: parser.py\n@@\n"
                   "-# Existing parser.\n+# Existing parser, documented.\n"
                   " def count_valid(rows):\n*** End Patch"),
        )
        cases.extend([
            _candidate("cursor", "clean_control", CursorParser, clean),
            _candidate("cursor", "unrelated_failure_control", CursorParser, unrelated),
            _candidate("cursor", "flaky_test_control", CursorParser, flaky),
            _candidate("cursor", "unrelated_code_control", CursorParser, unrelated_code),
            _candidate("cursor", "same_target_flaky_control", CursorParser, same_target_flaky),
        ])
        baseline_controls = {
            f"{agent}_clean_anchor": _baseline_probe(
                root, agent, f"{agent}-clean-anchor", dirty=False, include_status=True)
            for agent in ("claude", "codex", "cursor")
        }
        baseline_controls["cursor_dirty_worktree"] = _baseline_probe(
            root, "cursor", "cursor-dirty-anchor", dirty=True, include_status=True)
        baseline_controls["cursor_missing_status_capture"] = _baseline_probe(
            root, "cursor", "cursor-missing-status", dirty=False, include_status=False)
    return {"synthetic_only": True, "provider_count": 3, "case_count": len(cases),
            "cases": cases, "baseline_controls": baseline_controls}


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2))
