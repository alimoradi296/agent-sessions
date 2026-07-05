#!/usr/bin/env python3
"""
v1 Stop hook — writes a one-line session summary to docs/SESSION_LOG.md.
Captures: date, branch, last commit subject, and a placeholder for next step.
Superseded by v2 which makes SESSION_INDEX.md from session content directly.
"""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path("/path/to/your/project")  # EDIT THIS: absolute path to your project root
LOG_FILE = REPO / "docs" / "SESSION_LOG.md"


def run(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(cmd, cwd=REPO, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}

    branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"]) or "unknown"
    last_commit = run(["git", "log", "-1", "--pretty=%s"]) or "no commits"
    changed_files = run(["git", "diff", "--name-only", "HEAD~1", "HEAD"]) or ""
    changed_summary = ", ".join(changed_files.splitlines()[:5]) if changed_files else "none"
    if len(changed_files.splitlines()) > 5:
        changed_summary += f" (+{len(changed_files.splitlines()) - 5} more)"

    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    entry = (
        f"## {date_str} — branch: {branch}\n"
        f"- Last commit: {last_commit}\n"
        f"- Files changed: {changed_summary}\n"
        f"- Next step: (fill in before closing)\n\n"
    )

    if LOG_FILE.exists():
        existing = LOG_FILE.read_text(encoding="utf-8")
        if existing.startswith("# Session Log"):
            header_end = existing.find("\n\n") + 2
            new_content = existing[:header_end] + entry + existing[header_end:]
        else:
            new_content = entry + existing
    else:
        new_content = "# Session Log\n\nNewest entries first.\n\n" + entry

    LOG_FILE.write_text(new_content, encoding="utf-8")


if __name__ == "__main__":
    main()
