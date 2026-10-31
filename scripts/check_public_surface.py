#!/usr/bin/env python3
"""Refuse common private-data leaks before a public push.

Checks tracked and staged Git paths only. Does not redact files.
Exit 0 when clean; exit 1 when a likely private artifact is present.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_NAME_PATTERNS = (
    re.compile(r"(^|/)\.agent-sessions(/|$)"),
    re.compile(r"(^|/)exports(/|$)"),
    re.compile(r"(^|/)handoff-bundles(/|$)"),
    re.compile(r"(^|/)sessions\.json$"),
    re.compile(r"(^|/)SESSION_INDEX\.md$"),
    re.compile(r"(^|/)sessions_graph\.json$"),
    re.compile(r"\.distilled\.json$"),
    re.compile(r"\.jsonl(\.gz)?$"),
    re.compile(r"family-requirements\.json$"),
    re.compile(r"doctor-report"),
    re.compile(r"reconcile-report"),
    re.compile(r"agent-sessions-report"),
)

# Absolute home-export style paths accidentally pasted into tracked text.
HOME_EXPORT_HINT = re.compile(
    r"(?:/Users/[^/\s]+|/home/[^/\s]+)/\.agent-sessions/",
)

ALLOWED_SUFFIXES_FOR_CONTENT = {
    ".md",
    ".py",
    ".toml",
    ".txt",
    ".svg",
    ".yml",
    ".yaml",
    ".json",
}


def _git_files() -> list[str]:
    tracked = subprocess.check_output(
        ["git", "-C", str(ROOT), "ls-files", "-z"],
        text=False,
    ).split(b"\0")
    staged = subprocess.check_output(
        ["git", "-C", str(ROOT), "diff", "--cached", "--name-only", "-z"],
        text=False,
    ).split(b"\0")
    names = {p.decode("utf-8", "surrogateescape") for p in tracked + staged if p}
    return sorted(names)


def main() -> int:
    problems: list[str] = []
    for rel in _git_files():
        for pat in FORBIDDEN_NAME_PATTERNS:
            if pat.search(rel):
                # Synthetic fixtures may use .jsonl under examples/ only when named sample-*.
                if rel.endswith(".jsonl") and rel.startswith("examples/") and "sample" in Path(rel).name:
                    continue
                problems.append(f"forbidden path: {rel}")
                break
        path = ROOT / rel
        if not path.is_file():
            continue
        if path.suffix.lower() not in ALLOWED_SUFFIXES_FOR_CONTENT:
            continue
        if path.stat().st_size > 2_000_000:
            problems.append(f"oversized tracked text file: {rel}")
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            problems.append(f"unreadable: {rel} ({exc})")
            continue
        if HOME_EXPORT_HINT.search(text):
            problems.append(f"home export path in tracked file: {rel}")

    if problems:
        print("Public surface check failed:", file=sys.stderr)
        for item in problems:
            print(f"  - {item}", file=sys.stderr)
        print(
            "Keep real exports, transcripts, and home paths out of the public repository.",
            file=sys.stderr,
        )
        return 1
    print("Public surface check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
