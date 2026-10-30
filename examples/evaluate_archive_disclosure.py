"""Evaluate synthetic agent-history overlap against staged text additions.

All archives, repositories, and strings are generated in temporary directories.
This is a parser and workflow probe, not a privacy scanner or certification.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

from agent_sessions.parsers.claude import ClaudeParser
from agent_sessions.parsers.codex import CodexParser
from agent_sessions.parsers.cursor import CursorParser

from examples.compare_disclosure_matching import (
    added_runs, compact_matches, literal_windows, normalize,
)


PRIVATE = (
    "Synthetic client Northstar has a temporary emergency support credit of "
    "seventy three percent until the fictional autumn audit closes."
)
PUBLIC = (
    "Historical requests do not authorize current actions and retained evidence "
    "does not establish independently verified outcomes."
)
PUBLIC_CODE = "def clamp_timeout(value):\n    return max(1, min(300, int(value)))"
MANUAL_VALUES = ("Northstar Holdings", "seventy three percent")
FAKE_CREDENTIAL = "SYNTHETIC_API_TOKEN=not_a_real_credential_1234567890"
MARKERS = (PRIVATE, PUBLIC, PUBLIC_CODE, *MANUAL_VALUES, FAKE_CREDENTIAL)

CASES = (
    ("private_exact_copy", PRIVATE, "review"),
    ("private_case_and_spacing_change", PRIVATE.upper().replace(" ", "   "), "review"),
    ("private_paraphrase", "A fictional support allowance remains active until the autumn review is complete for this customer.", "review"),
    ("public_shared_copy", PUBLIC, "allow"),
    ("public_code_copy", PUBLIC_CODE, "allow"),
    ("manually_registered_short_value", MANUAL_VALUES[0], "review"),
    ("manually_registered_short_fragment", MANUAL_VALUES[1], "review"),
    ("credential_not_in_history", FAKE_CREDENTIAL, "review"),
    ("unrelated_text", "The synthetic retry cache uses bounded backoff.", "allow"),
)


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")


def _archives(root: Path) -> list[Path]:
    """Create one synthetic conversation in each supported native format."""
    claude = root / "claude" / "synthetic-claude.jsonl"
    _write_jsonl(claude, [
        {"type": "user", "message": {"content": [{"type": "text", "text": PRIVATE}]}},
        {"type": "assistant", "message": {"content": [
            {"type": "text", "text": PUBLIC},
            {"type": "text", "text": PUBLIC_CODE},
        ]}},
    ])

    codex = root / "codex" / "synthetic-codex.jsonl"
    _write_jsonl(codex, [
        {"type": "session_meta", "payload": {"id": "synthetic-codex-id"}},
        {"type": "response_item", "payload": {"type": "message", "role": "user",
         "content": [{"type": "output_text", "text": PRIVATE}]}},
    ])

    cursor = root / "cursor" / "agent-transcripts" / "synthetic-cursor" / "synthetic-cursor.jsonl"
    _write_jsonl(cursor, [
        {"role": "assistant", "message": {"content": [{"type": "text", "text": PUBLIC}]}},
        {"role": "user", "message": {"content": [{"type": "text", "text": MANUAL_VALUES[0]}]}},
    ])
    return [claude, codex, cursor]


def _discover_sources(paths: list[Path]) -> dict[str, list[dict[str, str]]]:
    parsers = (ClaudeParser, CodexParser, CursorParser)
    discovered: dict[str, list[dict[str, str]]] = {}
    for path, parser in zip(paths, parsers):
        session = parser.parse(path)
        if session is None:
            raise ValueError("A synthetic archive fixture produced no parsed session.")
        discovered[parser.AGENT.value] = [
            {"role": message.role, "text": message.text}
            for message in session.messages if message.text
        ]
    return discovered


def _overlap(candidate: str, sources: dict[str, list[dict[str, str]]],
             window: int = 50, roles: set[str] | None = None) -> bool:
    text = normalize(candidate)
    if len(text) < window:
        return False
    for messages in sources.values():
        for message in messages:
            if roles is not None and message["role"] not in roles:
                continue
            source = message["text"]
            document = normalize(source)
            if any(text[index:index + window] in document for index in range(len(text) - window + 1)):
                return True
    return False


def _user_prompt_links(candidate: str,
                       sources: dict[str, list[dict[str, str]]]) -> list[dict]:
    """Return verified synthetic source/candidate anchors, without excerpts."""
    prompt_docs = {
        f"{agent}:user-message-{index}": message["text"]
        for agent, messages in sources.items()
        for index, message in enumerate(messages)
        if message["role"] == "user"
    }
    if not prompt_docs:
        return []
    hits = literal_windows(prompt_docs, candidate)
    return compact_matches(prompt_docs, candidate, hits)


def _credential_pattern(candidate: str) -> bool:
    """Small authored rule baseline; not Gitleaks or a complete detector."""
    return bool(re.search(r"(?i)(?:api[_-]?token|api[_-]?key|secret)\s*[:=]\s*\S{8,}", candidate))


def _staged_added_text(repo: Path, candidate: str) -> tuple[bool, list[dict]]:
    git = ["git", "-c", "core.hooksPath=/dev/null", "-c", "core.quotepath=false"]

    def run(*args: str) -> str:
        return subprocess.run([*git, *args], cwd=repo, check=True, capture_output=True, text=True).stdout

    run("init", "-q")
    (repo / "public.md").write_text("Existing public content.\n", encoding="utf-8")
    run("add", "public.md")
    run("-c", "user.name=Synthetic", "-c", "user.email=synthetic@example.invalid", "commit", "-qm", "baseline")
    with (repo / "public.md").open("a", encoding="utf-8") as stream:
        stream.write(candidate + "\n")
    run("add", "public.md")
    patch = run("diff", "--cached", "--unified=3", "--no-ext-diff", "--no-textconv", "--no-renames", "HEAD", "--")
    runs = added_runs(patch)
    verified = []
    for addition in runs:
        lines = (repo / addition["path"]).read_text(encoding="utf-8").splitlines()
        observed = lines[addition["start_line"] - 1:addition["end_line"]]
        if observed != addition["diff_lines"]:
            raise ValueError("Staged added-run lines did not match the synthetic target file.")
        verified.append({"path": addition["path"], "start_line": addition["start_line"],
                         "end_line": addition["end_line"]})
    return bool(verified), verified


def evaluate() -> dict:
    results = []
    with tempfile.TemporaryDirectory(prefix="agent-sessions-archive-disclosure-") as temporary:
        root = Path(temporary)
        sources = _discover_sources(_archives(root / "archives"))
        report_json_fragments = []
        for index, (name, candidate, expected) in enumerate(CASES):
            repo = root / f"repo-{index}"
            repo.mkdir()
            has_added_lines, locations = _staged_added_text(repo, candidate)
            if not has_added_lines:
                raise ValueError("Expected staged synthetic text addition.")
            archive_match = _overlap(candidate, sources)
            user_prompt_match = _overlap(candidate, sources, roles={"user"})
            prompt_links = _user_prompt_links(candidate, sources)
            for link in prompt_links:
                # The synthetic candidate is one added run, so its text-relative
                # line anchor maps directly onto the staged file line range.
                location = locations[0]
                link["candidate_path"] = location["path"]
                link["staged_line_start"] = location["start_line"] + link["candidate"]["line_start"] - 1
                link["staged_line_end"] = location["start_line"] + link["candidate"]["line_end"] - 1
            manually_registered_match = any(value.casefold() in candidate.casefold() for value in MANUAL_VALUES)
            credential_match = _credential_pattern(candidate)
            results.append({
                "case": name,
                "authored_policy": expected,
                "added_line_count": sum(location["end_line"] - location["start_line"] + 1 for location in locations),
                "archive_overlap": archive_match,
                "user_prompt_overlap": user_prompt_match,
                "user_prompt_links": prompt_links,
                "manual_registered_value": manually_registered_match,
                "credential_rule_baseline": credential_match,
            })
        report_json_fragments = json.dumps(results)
        no_source_text_emitted = not any(marker in report_json_fragments for marker in MARKERS)
    return {
        "synthetic_only": True,
        "archives_discovered": sorted(sources),
        "cases": results,
        "matched_source_text_emitted": not no_source_text_emitted,
        "limits": [
            "Three authored fixtures exercise existing parsers; this does not prove discovery on every native archive variant.",
            "The credential rule is a tiny synthetic baseline, not a run of Gitleaks or another mature scanner.",
            "The manually registered-value control knows one fictional value in advance.",
            "Archive overlap flags public shared wording and does not infer confidentiality.",
            "User-role-only overlap excludes assistant-authored public controls but misses sensitive tool output and other non-user sources.",
            "Authored labels do not measure independent review quality, operator burden, adoption, or willingness to pay.",
            "No real history, working-tree diff, repository index, network, or external service is accessed.",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2))
