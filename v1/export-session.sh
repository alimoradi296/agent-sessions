#!/usr/bin/env bash
# v1 — Original export-session.sh
# Exports Claude Code session transcript to docs/sessions/<timestamp>-<session_id>.md
# Called by the Stop hook. One new file per stop event — causes duplicates.

set -euo pipefail

INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('session_id',''))" 2>/dev/null || true)

if [[ -z "$SESSION_ID" ]]; then
  exit 0
fi

TRANSCRIPT=$(find ~/.claude/projects -name "${SESSION_ID}.jsonl" 2>/dev/null | head -1)

if [[ -z "$TRANSCRIPT" ]]; then
  exit 0
fi

CWD=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('cwd',''))" 2>/dev/null || true)
if [[ -n "$CWD" && -d "$CWD/docs/sessions" ]]; then
  OUT_DIR="$CWD/docs/sessions"
elif [[ -n "$CWD" && -d "$CWD/docs" ]]; then
  mkdir -p "$CWD/docs/sessions"
  OUT_DIR="$CWD/docs/sessions"
else
  mkdir -p ~/.claude/sessions
  OUT_DIR=~/.claude/sessions
fi

TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
OUT_FILE="$OUT_DIR/${TIMESTAMP}-${SESSION_ID}.md"

python3 - "$TRANSCRIPT" "$OUT_FILE" "$SESSION_ID" <<'PYEOF'
import sys, json
from datetime import datetime, timezone

transcript_path, out_path, session_id = sys.argv[1], sys.argv[2], sys.argv[3]

messages = []
title = "Claude Code Session"

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
            title = d.get("title", title)
        elif t in ("user", "assistant") and not d.get("isSidechain"):
            messages.append(d)

if not messages:
    sys.exit(0)

def fmt_time(ts):
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return ts

def extract_text(content):
    if isinstance(content, str):
        return content
    parts = []
    for block in content:
        if isinstance(block, dict):
            btype = block.get("type")
            if btype == "text":
                parts.append(block.get("text", ""))
            elif btype == "tool_use":
                tool = block.get("name", "tool")
                inp = block.get("input", {})
                summary = json.dumps(inp, ensure_ascii=False)[:200]
                parts.append(f"*[Tool: {tool}]* `{summary}`")
            elif btype == "tool_result":
                result_content = block.get("content", "")
                if isinstance(result_content, list):
                    result_content = " ".join(
                        c.get("text", "") for c in result_content if isinstance(c, dict)
                    )
                parts.append(f"*[Tool result]* {str(result_content)[:300]}")
    return "\n".join(p for p in parts if p)

lines = [
    f"# {title}",
    f"",
    f"**Session ID:** `{session_id}`  ",
    f"**Exported:** {fmt_time(datetime.now(timezone.utc).isoformat())}  ",
    f"",
    f"---",
    f"",
]

for msg in messages:
    role = msg.get("type", "unknown")
    ts = msg.get("timestamp", "")
    content = msg.get("message", {}).get("content", "")
    text = extract_text(content).strip()
    if not text:
        continue

    if role == "user":
        header = f"## User"
        if ts:
            header += f"  <sup>{fmt_time(ts)}</sup>"
        lines.append(header)
        lines.append("")
        lines.append(text)
    else:
        header = f"## Assistant"
        if ts:
            header += f"  <sup>{fmt_time(ts)}</sup>"
        lines.append(header)
        lines.append("")
        lines.append(text)

    lines.append("")
    lines.append("---")
    lines.append("")

with open(out_path, "w") as f:
    f.write("\n".join(lines))

print(f"Session exported to {out_path}")
PYEOF
