# claude-session-exporter — Claude Instructions

## What This Repo Is

A Claude Code Stop hook that exports session transcripts as deduplicated, searchable Markdown files. Two versions: v1 (original, naive) and v2 (current, smart).

## Structure

```
v1/
  export-session.sh     — original: writes {timestamp}-{session_id}.md on every stop
  session_summary.py    — original companion: writes one line to SESSION_LOG.md
v2/
  export-session.sh     — current: writes {session_id}.md (deduped), builds SESSION_INDEX.md
README.md               — full design rationale, installation, format docs
CLAUDE.md               — this file
```

## Key Design Decisions (Do Not Revert)

- **Filename is `{session_id}.md`, not `{timestamp}-{session_id}.md`** — the timestamp naming caused hundreds of duplicate files for the same session. Overwriting on re-export is intentional.
- **`away_summary` system events are the real summary** — they contain Claude's own state description mid-session, far more useful than git log output. Always prefer the last one (most complete).
- **`forkedFrom` is the rewind/branch link** — every message in a rewound session carries `forkedFrom: {sessionId, messageUuid}`. Read it from the first message.
- **`SESSION_INDEX.md` is the search interface** — one line per session, grep-able. Never replace this with a full-text search scheme; the index is intentionally lightweight.
- **No deletion of old files** — when migrating from v1 to v2, keep the old timestamp-named files. The new UUID-named files coexist with them.

## JSONL Event Types That Matter

| Type | Field | Purpose |
|---|---|---|
| `ai-title` | `aiTitle` | Session title (human-readable topic) |
| `system` | `subtype == "away_summary"`, `content` | Claude's own state summary — best source for index entry |
| `user` / `assistant` | `forkedFrom` | Present on all messages if session was a rewind/branch — contains `{sessionId, messageUuid}` of parent |
| `user` / `assistant` | `gitBranch`, `cwd` | Git branch and working directory at message time |
| `user` / `assistant` | `isSidechain` | If true, skip — these are tool-use sidechains, not the main conversation |

## What NOT to Do

- Do not add timestamp to the output filename — defeats deduplication
- Do not use git log as the session summary — it tracks commits, not what happened in the session
- Do not remove the `<details>` block for earlier away_summaries — they show the session's progression
- Do not make `SESSION_INDEX.md` a full transcript — it must stay one line per session for grep to work
- Do not sort the index alphabetically — newest-first insertion order is how you find recent sessions

## Testing

To test against a real session:
```bash
python3 -c "
import json, subprocess
payload = json.dumps({'session_id': '<session_id>', 'cwd': '<project_cwd>'})
result = subprocess.run(['bash', 'v2/export-session.sh'], input=payload, capture_output=True, text=True)
print(result.stdout)
print(result.stderr)
"
```

## Installation Path

The live version runs at `~/.claude/scripts/export-session.sh`, wired via `~/.claude/settings.json` Stop hook. See README.md for full installation steps.
