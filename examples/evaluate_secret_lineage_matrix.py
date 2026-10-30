"""Probe static secret-to-source-code lineage across synthetic transforms.

All records, values, and Git history are fabricated and temporary. The
evaluator never executes candidate code and never prints source values.
This is feasibility evidence, not a production scanner comparison.
"""

from __future__ import annotations

import ast
import base64
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from agent_sessions.parsers.claude import ClaudeParser


FAKE_SECRET = "synthetic_value_not_a_real_credential_7f91c2d4"
FAKE_SOURCE = f"SYNTHETIC_API_KEY={FAKE_SECRET}"
SENSITIVE_KEY_PARTS = ("secret", "token", "password", "credential", "api_key")


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", *args], cwd=repo,
        env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull},
        check=True, capture_output=True, text=True,
    )
    return result.stdout.strip()


def _source_values(text: str) -> list[tuple[str, str]]:
    """Return candidate source values with safe, content-free fingerprints."""
    values: set[str] = {text.strip()} if text.strip() else set()
    for line in text.splitlines():
        key, separator, value = line.partition("=")
        if separator and any(part in key.lower() for part in SENSITIVE_KEY_PARTS):
            values.add(value.strip().strip("'\""))
    return [(value, hashlib.sha256(value.encode("utf-8")).hexdigest()[:12])
            for value in values if len(value) >= 16]


def _constant(node: ast.AST):
    """Evaluate a deliberately small literal-only AST subset; never execute code."""
    if isinstance(node, ast.Constant) and type(node.value) in (str, bytes, int):
        return node.value
    if isinstance(node, (ast.Tuple, ast.List)):
        items = [_constant(item) for item in node.elts]
        if any(item is _UNKNOWN for item in items):
            return _UNKNOWN
        return tuple(items) if isinstance(node, ast.Tuple) else list(items)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _constant(node.left), _constant(node.right)
        if type(left) is type(right) and isinstance(left, (str, bytes, int)):
            return left + right
        return _UNKNOWN
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id == "bytes" and len(node.args) == 1:
            value = _constant(node.args[0])
            if isinstance(value, (list, tuple)) and all(type(item) is int and 0 <= item <= 255
                                                        for item in value):
                return bytes(value)
        if isinstance(node.func, ast.Attribute) and node.func.attr == "b64decode" and node.args:
            try:
                value = _constant(node.args[0])
                raw = value.encode("ascii") if isinstance(value, str) else value
                if isinstance(raw, bytes):
                    return base64.b64decode(raw, validate=True)
            except (UnicodeEncodeError, ValueError):
                return _UNKNOWN
        if isinstance(node.func, ast.Attribute) and node.func.attr == "fromhex" and node.args:
            try:
                value = _constant(node.args[0])
                if isinstance(value, str):
                    return bytes.fromhex(value)
            except ValueError:
                return _UNKNOWN
        if isinstance(node.func, ast.Attribute) and node.func.attr == "decode":
            receiver = _constant(node.func.value)
            if isinstance(receiver, bytes):
                try:
                    encoding = _constant(node.args[0]) if node.args else "utf-8"
                    if isinstance(encoding, str):
                        return receiver.decode(encoding, errors="strict")
                except (LookupError, UnicodeDecodeError):
                    return _UNKNOWN
    return _UNKNOWN


_UNKNOWN = object()


def _transformation(node: ast.AST) -> str:
    if isinstance(node, (ast.Tuple, ast.List)):
        return "integer_bytes"
    if isinstance(node, ast.BinOp):
        return "constant_concatenation"
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute) and node.func.attr == "b64decode":
            return "base64"
        if isinstance(node.func, ast.Attribute) and node.func.attr == "fromhex":
            return "hex"
        if isinstance(node.func, ast.Attribute) and node.func.attr == "decode":
            return "bytes_decode"
        if isinstance(node.func, ast.Name) and node.func.id == "bytes":
            return "bytes_constructor"
    return "literal_or_nested_transform"


def _lineage(code: str, sources: list[tuple[str, str]], path: str,
             commit: str) -> list[dict]:
    tree = ast.parse(code)
    links = []
    seen = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value_node = node.value
        value = _constant(value_node)
        candidates = [value]
        if isinstance(value, (tuple, list)) and all(
                type(item) is int and 0 <= item <= 255 for item in value):
            candidates.append(bytes(value))
        # Decode string literals that contain common encoded representations.
        if isinstance(value, str):
            try:
                candidates.append(bytes.fromhex(value))
            except ValueError:
                pass
            try:
                candidates.append(base64.b64decode(value.encode("ascii"), validate=True))
            except (UnicodeEncodeError, ValueError):
                pass
        decoded = set()
        for candidate in candidates:
            if isinstance(candidate, bytes):
                try:
                    decoded.add(candidate.decode("utf-8", errors="strict"))
                except UnicodeDecodeError:
                    continue
            elif isinstance(candidate, str):
                decoded.add(candidate)
        for source_value, fingerprint in sources:
            if source_value in decoded:
                key = (node.lineno, fingerprint)
                if key in seen:
                    continue
                seen.add(key)
                links.append({
                    "source_fingerprint": fingerprint,
                    "path": path,
                    "line": node.lineno,
                    "commit": commit[:12],
                    "transformation": _transformation(value_node),
                })
    return links


def _fixture_code() -> dict[str, str]:
    encoded = ", ".join(str(byte) for byte in FAKE_SECRET.encode("utf-8"))
    hexed = FAKE_SECRET.encode("utf-8").hex()
    b64 = base64.b64encode(FAKE_SECRET.encode("utf-8")).decode("ascii")
    midpoint = len(FAKE_SECRET) // 2
    return {
        "src/tuple.py": f"VALUE = ({encoded})\n",
        "src/bytes_constructor.py": f"VALUE = bytes([{encoded}]).decode('utf-8')\n",
        "src/hex_literal.py": f"VALUE = '{hexed}'\n",
        "src/hex_decode.py": f"VALUE = bytes.fromhex('{hexed}').decode('utf-8')\n",
        "src/base64_literal.py": f"VALUE = '{b64}'\n",
        "src/base64_decode.py": f"import base64\nVALUE = base64.b64decode('{b64}').decode('utf-8')\n",
        "src/split_concat.py": (
            f"VALUE = '{FAKE_SECRET[:midpoint]}' + '{FAKE_SECRET[midpoint:]}'\n"),
        "src/benign_tuple.py": "VALUE = (80, 89, 84, 72, 79, 78)\n",
        "src/benign_hex.py": "VALUE = bytes.fromhex('deadbeef').decode('latin-1')\n",
        "src/unrelated_b64.py": "VALUE = 'c29tZV91bnJlbGF0ZWRfdmFsdWU='\n",
    }


def evaluate() -> dict:
    report = {"synthetic_only": True, "case_count": 0, "expected_positive": 7,
              "expected_negative": 3, "positive_links": 0, "negative_links": 0,
              "methods": {}, "content_emitted": False}
    with tempfile.TemporaryDirectory(prefix="synthetic-secret-lineage-matrix-") as directory:
        root = Path(directory)
        archive = root / "claude" / "synthetic-session.jsonl"
        archive.parent.mkdir(parents=True)
        records = [
            {"type": "user", "message": {"content": "Inspect a fictional configuration."}},
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": "fake-read", "name": "Read",
                 "input": {"file_path": ".env"}},
            ]}},
            {"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": "fake-read",
                 "content": FAKE_SOURCE},
            ]}},
        ]
        archive.write_text("".join(json.dumps(record) + "\n" for record in records),
                           encoding="utf-8")
        session = ClaudeParser.parse(archive)
        if session is None:
            raise ValueError("Synthetic archive did not parse")
        source_text = "\n".join(result.content for message in session.messages
                                 for result in message.tool_results)
        source_values = _source_values(source_text)
        if not source_values:
            raise ValueError("Synthetic sensitive value was not retained")

        repo = root / "repo"
        repo.mkdir()
        _git(repo, "init", "-q")
        baseline = repo / "README.md"
        baseline.write_text("Synthetic repository only.\n", encoding="utf-8")
        _git(repo, "add", ".")
        _git(repo, "-c", "user.name=Synthetic", "-c",
             "user.email=synthetic@example.invalid", "commit", "-qm", "synthetic base")
        files = _fixture_code()
        for relative, body in files.items():
            destination = repo / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(body, encoding="utf-8")
        _git(repo, "add", ".")
        _git(repo, "-c", "user.name=Synthetic", "-c",
             "user.email=synthetic@example.invalid", "commit", "-qm", "synthetic outputs")
        commit = _git(repo, "rev-parse", "HEAD")

        by_method = {}
        for relative in files:
            code = (repo / relative).read_text(encoding="utf-8")
            links = _lineage(code, source_values, relative, commit)
            if links:
                report["positive_links"] += 1
                by_method[links[0]["transformation"]] = by_method.get(
                    links[0]["transformation"], 0) + 1
            else:
                report["negative_links"] += 1
        report["case_count"] = len(files)
        report["methods"] = by_method
        report["lineage_matches"] = report["positive_links"]
        report["false_positive_cases"] = report["negative_links"]
        report["source_content_or_secret_emitted"] = (
            FAKE_SECRET in json.dumps(report) or FAKE_SOURCE in json.dumps(report))
        report["commit_ids_emitted"] = commit in json.dumps(report)
        report["limits"] = [
            "The corpus contains only authored Python literals and common encodings.",
            "The three non-matching controls are not a false-positive rate.",
            "No Gitleaks, Skarn, DeepBlame, or agent-blast-radius runtime was run.",
            "The evaluator does not establish that a source value is genuinely sensitive.",
            "No reviewer time, customer demand, adoption, or willingness to pay was measured.",
        ]
    return report


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2))
