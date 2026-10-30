"""Evaluate one synthetic agent-secret-to-committed-code transformation.

This is a narrow product probe, not a production scanner or a competitor
runtime comparison. It uses a fabricated secret and temporary Git repository.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import tempfile
from pathlib import Path

from examples.evaluate_archive_disclosure import _credential_pattern, _overlap
from agent_sessions.parsers.claude import ClaudeParser


FAKE_SECRET = "SYNTHETIC_KEY=fictional_value_never_valid_for_any_service"
SOURCE_ID = "claude:synthetic-tool-result-1"
DECOY_TUPLE = (80, 89, 84, 72, 79, 78)  # "PYTHON"


def _git(repo: Path, *args: str) -> str:
    env = os.environ.copy()
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    result = subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", *args], cwd=repo,
        check=True, capture_output=True, text=True, env=env)
    return result.stdout.strip()


def _integer_tuple_links(code: str, source_text: str, path: str,
                         commit: str) -> list[dict[str, object]]:
    """Prototype exact UTF-8 integer-tuple correlation using AST, not eval."""
    tree = ast.parse(code)
    links: list[dict[str, object]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if not isinstance(value, (ast.Tuple, ast.List)) or not value.elts:
            continue
        if not all(isinstance(item, ast.Constant) and type(item.value) is int
                   and 0 <= item.value <= 255 for item in value.elts):
            continue
        try:
            decoded = bytes(item.value for item in value.elts).decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            continue
        if decoded and decoded in source_text:
            links.append({"source_id": SOURCE_ID, "path": path,
                          "line": node.lineno, "commit": commit[:12],
                          "verified": True})
    return links


def evaluate() -> dict[str, object]:
    encoded = ", ".join(str(byte) for byte in FAKE_SECRET.encode("utf-8"))
    code = (
        "# Generated module; all values in this probe are fictional.\n"
        f"PROV_CANARY: tuple[int, ...] = ({encoded})\n"
        f"BUILD_TAG: tuple[int, ...] = {DECOY_TUPLE!r}\n"
    )
    repo_relpath = "src/generated.py"

    with tempfile.TemporaryDirectory(prefix="synthetic-secret-lineage-") as directory:
        root = Path(directory)
        archive = root / "archives" / "claude" / "synthetic-session.jsonl"
        archive.parent.mkdir(parents=True)
        records = [
            {"type": "user", "message": {"content": "Inspect the fictional service configuration."}},
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": "synthetic-call-1", "name": "Read",
                 "input": {"file_path": ".env"}},
            ]}},
            {"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": "synthetic-call-1",
                 "content": FAKE_SECRET},
            ]}},
        ]
        archive.write_text("".join(json.dumps(record) + "\n" for record in records),
                           encoding="utf-8")
        session = ClaudeParser.parse(archive)
        if session is None:
            raise ValueError("The synthetic Claude transcript did not produce a session.")
        sources = {"claude": [
            *({"role": message.role, "text": message.text} for message in session.messages),
            *({"role": "tool", "text": result.content}
              for message in session.messages for result in message.tool_results),
        ]}
        tool_results = [result.content for message in session.messages
                        for result in message.tool_results]
        source_text = "\n".join(tool_results)
        if not source_text:
            raise ValueError("The synthetic Claude parser did not retain the tool result.")

        repo = root / "repo"
        repo.mkdir()
        # Establish the pre-change baseline, then commit the synthetic output.
        baseline = repo / "src" / "baseline.py"
        baseline.parent.mkdir(parents=True)
        baseline.write_text("# Synthetic baseline.\n", encoding="utf-8")
        _git(repo, "init", "-q")
        _git(repo, "add", ".")
        _git(repo, "-c", "user.name=Synthetic Evaluation", "-c",
             "user.email=synthetic@example.invalid", "commit", "-qm", "synthetic baseline")
        target = repo / repo_relpath
        target.write_text(code, encoding="utf-8")
        _git(repo, "add", repo_relpath)
        _git(repo, "-c", "user.name=Synthetic Evaluation", "-c",
             "user.email=synthetic@example.invalid", "commit", "-qm", "synthetic encoded output")
        commit = _git(repo, "rev-parse", "HEAD")
        committed = subprocess.run(
            ["git", "-c", "core.hooksPath=/dev/null", "show", f"{commit}:{repo_relpath}"],
            cwd=repo, check=True, capture_output=True, text=True,
            env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull},
        ).stdout
        links = _integer_tuple_links(committed, source_text, repo_relpath, commit)

    decoy_only_code = f"BUILD_TAG: tuple[int, ...] = {DECOY_TUPLE!r}\n"
    report = {
        "synthetic_only": True,
        "source_parser": "claude",
        "parsed_tool_result_count": len(tool_results),
        "parsed_source_contains_synthetic_value": FAKE_SECRET in source_text,
        "committed_destination": "src/generated.py",
        "committed_line": links[0]["line"] if links else None,
        "commit_link_count": len(links),
        "prototype_link": links[0] if links else None,
        "literal_archive_overlap": _overlap(code, sources),
        "user_prompt_overlap": _overlap(code, sources, roles={"user"}),
        "credential_shape_match": _credential_pattern(code),
        "literal_source_value_in_candidate": FAKE_SECRET in code,
        "benign_tuple_links": len(_integer_tuple_links(
            decoy_only_code, source_text, repo_relpath, "synthetic-decoy")),
        "limits": [
            "One authored UTF-8 integer-tuple transformation; no realistic prevalence claim.",
            "The prototype compares exact decoded text and does not cover other encodings or transformations.",
            "The baseline functions are this repository's literal matcher and small regex, not Gitleaks, Skarn, or DeepBlame.",
            "No competitor runtime, reviewer time, adoption, or willingness to pay was measured.",
            "All archive content and Git history are synthetic and temporary; no real archive or caller index is read.",
        ],
    }
    report["secret_emitted_in_result"] = FAKE_SECRET in json.dumps(report, sort_keys=True)
    return report


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2))
