#!/usr/bin/env bash
# Exports the current Claude Code session transcript to docs/sessions/<session_id>.md
# One file per session ID — re-exports overwrite, so no duplicate files.
# Also updates docs/sessions/SESSION_INDEX.md with a one-line searchable entry.
# Called by the Stop hook.

set -euo pipefail

INPUT=$(cat)

SESSION_ID=$(echo "$INPUT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(d.get('session_id', ''))
" 2>/dev/null || true)

if [[ -z "$SESSION_ID" ]]; then
  exit 0
fi

TRANSCRIPT=$(find ~/.claude/projects -name "${SESSION_ID}.jsonl" 2>/dev/null | head -1)

if [[ -z "$TRANSCRIPT" ]]; then
  exit 0
fi

CWD=$(echo "$INPUT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(d.get('cwd', ''))
" 2>/dev/null || true)

if [[ -n "$CWD" && -d "$CWD/docs/sessions" ]]; then
  OUT_DIR="$CWD/docs/sessions"
elif [[ -n "$CWD" && -d "$CWD/docs" ]]; then
  mkdir -p "$CWD/docs/sessions"
  OUT_DIR="$CWD/docs/sessions"
else
  mkdir -p ~/.claude/sessions
  OUT_DIR=~/.claude/sessions
fi

OUT_FILE="$OUT_DIR/${SESSION_ID}.md"
INDEX_FILE="$OUT_DIR/SESSION_INDEX.md"

python3 - "$TRANSCRIPT" "$OUT_FILE" "$INDEX_FILE" "$SESSION_ID" <<'PYEOF'
import sys, json, re, subprocess
from datetime import datetime, timezone
from pathlib import Path

transcript_path = sys.argv[1]
out_path        = sys.argv[2]
index_path      = sys.argv[3]
session_id      = sys.argv[4]

# ── Parse transcript ────────────────────────────────────────────────────────
messages      = []
title         = "Claude Code Session"
away_summaries = []
forked_from   = None   # {'sessionId': ..., 'messageUuid': ...}
git_branch    = None
cwd           = None
first_ts      = None
last_ts       = None

with open(transcript_path) as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue

        t = d.get("type")

        if t == "ai-title":
            title = d.get("aiTitle") or d.get("title") or title

        elif t == "system":
            sub = d.get("subtype", "")
            if sub == "away_summary":
                content = d.get("content", "").strip()
                if content and content not in away_summaries:
                    away_summaries.append(content)

        elif t in ("user", "assistant") and not d.get("isSidechain"):
            # Pick up forkedFrom, branch, cwd from first message
            if forked_from is None and d.get("forkedFrom"):
                forked_from = d["forkedFrom"]
            if git_branch is None and d.get("gitBranch"):
                git_branch = d["gitBranch"]
            if cwd is None and d.get("cwd"):
                cwd = d["cwd"]

            ts = d.get("timestamp", "")
            if ts:
                if first_ts is None:
                    first_ts = ts
                last_ts = ts

            messages.append(d)

if not messages:
    sys.exit(0)

# ── Helpers ──────────────────────────────────────────────────────────────────
def fmt_time(ts):
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return ts

def fmt_date(ts):
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return ""

def extract_text(content):
    if isinstance(content, str):
        return content
    parts = []
    for block in content:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "text":
            parts.append(block.get("text", ""))
        elif btype == "tool_use":
            tool = block.get("name", "tool")
            inp  = block.get("input", {})
            summary = json.dumps(inp, ensure_ascii=False)[:200]
            parts.append(f"*[Tool: {tool}]* `{summary}`")
        elif btype == "tool_result":
            rc = block.get("content", "")
            if isinstance(rc, list):
                rc = " ".join(c.get("text", "") for c in rc if isinstance(c, dict))
            parts.append(f"*[Tool result]* {str(rc)[:300]}")
    return "\n".join(p for p in parts if p)

# Best one-line summary: prefer last away_summary (most up-to-date state),
# fall back to title.
best_summary = away_summaries[-1] if away_summaries else title
# Truncate to ~160 chars for the index line
index_summary = best_summary[:160].rstrip()

# ── Write session markdown ───────────────────────────────────────────────────
lines = [
    f"# {title}",
    f"",
    f"**Session ID:** `{session_id}`",
]

if forked_from:
    parent_id = forked_from.get("sessionId", "")
    lines.append(f"**Forked from:** `{parent_id}` (rewind/branch)")

lines += [
    f"**Branch:** `{git_branch or 'unknown'}`",
    f"**Started:** {fmt_time(first_ts) if first_ts else 'unknown'}",
    f"**Exported:** {fmt_time(datetime.now(timezone.utc).isoformat())}",
    f"",
]

if away_summaries:
    lines.append("## Session Summary")
    lines.append("")
    # Show the last (most complete) summary prominently, others as history
    lines.append(away_summaries[-1])
    if len(away_summaries) > 1:
        lines.append("")
        lines.append("<details><summary>Earlier mid-session summaries</summary>")
        lines.append("")
        for s in away_summaries[:-1]:
            lines.append(f"- {s}")
        lines.append("")
        lines.append("</details>")
    lines.append("")

lines += ["---", ""]

for msg in messages:
    role    = msg.get("type", "unknown")
    ts      = msg.get("timestamp", "")
    content = msg.get("message", {}).get("content", "")
    text    = extract_text(content).strip()
    if not text:
        continue

    label  = "User" if role == "user" else "Assistant"
    header = f"## {label}"
    if ts:
        header += f"  <sup>{fmt_time(ts)}</sup>"
    lines.append(header)
    lines.append("")
    lines.append(text)
    lines.append("")
    lines.append("---")
    lines.append("")

Path(out_path).write_text("\n".join(lines), encoding="utf-8")

# ── Update SESSION_INDEX.md ──────────────────────────────────────────────────
index_file = Path(index_path)

date_str   = fmt_date(first_ts) if first_ts else datetime.now().strftime("%Y-%m-%d")
branch_str = git_branch or "unknown"
parent_str = f" ← `{forked_from['sessionId'][:8]}…`" if forked_from else ""

new_entry = (
    f"| `{session_id[:8]}…` "
    f"| {date_str} "
    f"| `{branch_str}` "
    f"| {index_summary}{parent_str} "
    f"| [{session_id}.md]({session_id}.md) |"
)

HEADER = """\
# Session Index

Searchable one-line-per-session log. Newest first.

| ID | Date | Branch | Summary | File |
|---|---|---|---|---|
"""

if index_file.exists():
    existing = index_file.read_text(encoding="utf-8")
    # Remove stale entry for this session_id if re-exporting
    lines_idx = [l for l in existing.splitlines() if session_id[:8] not in l]
    # Find the table body start (after header rows)
    try:
        sep_idx = next(i for i, l in enumerate(lines_idx) if l.startswith("|---"))
        # Insert new entry right after the separator row
        lines_idx.insert(sep_idx + 1, new_entry)
        index_file.write_text("\n".join(lines_idx) + "\n", encoding="utf-8")
    except StopIteration:
        # Malformed index — rewrite from scratch
        index_file.write_text(HEADER + new_entry + "\n", encoding="utf-8")
else:
    index_file.write_text(HEADER + new_entry + "\n", encoding="utf-8")

print(f"Session exported → {out_path}")
print(f"Index updated   → {index_path}")
PYEOF
