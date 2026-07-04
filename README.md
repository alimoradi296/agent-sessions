# claude-session-exporter

A Claude Code Stop hook that exports session transcripts as searchable, deduplicated Markdown files with a live index.

## The Problem

Claude Code saves raw `.jsonl` transcripts internally but provides no human-readable export. Without this hook:
- Sessions accumulate as `{timestamp}-{session_id}.md` — the same session gets re-exported on every stop, creating dozens of duplicates
- No way to find "what session covered topic X" without `grep`-ing hundreds of files
- Rewinds/branches have no link back to their parent session
- The `away_summary` field (Claude's own mid-session state description) is never captured

## Versions

### v1 — Original (naive)
- One new `{timestamp}-{session_id}.md` file per Stop event
- Companion `session_summary.py` writes one line to `SESSION_LOG.md` (branch + last commit — never actually useful)
- No deduplication, no index, no summaries, no parent links

**Problems diagnosed:**
- 315 files for ~50 unique sessions
- `SESSION_LOG.md` always said "Next step: (fill in before closing)" — never filled in
- Impossible to find sessions by topic without grep archaeology
- Rewind/branch sessions had no link to their origin

### v2 — Current
- One `{session_id}.md` file per unique session — re-exports overwrite, no duplicates
- Reads `away_summary` system events from the JSONL as the session summary (Claude's own description of what was happening)
- Reads `forkedFrom` field to link rewind/branch sessions back to parent
- Builds and maintains `SESSION_INDEX.md` — one searchable line per session with date, branch, summary, and link
- Captures `aiTitle` as the document title

## How It Works

Claude Code fires the `Stop` hook every time a session ends. The hook:
1. Reads `session_id` and `cwd` from the hook payload (stdin JSON)
2. Finds the `.jsonl` transcript in `~/.claude/projects/`
3. Parses all message types: `user`, `assistant`, `ai-title`, `system/away_summary`, `forkedFrom`
4. Writes `{session_id}.md` to `{cwd}/docs/sessions/` (overwrites if exists)
5. Appends/updates one row in `SESSION_INDEX.md`

## Installation

```bash
# 1. Copy the script
mkdir -p ~/.claude/scripts
cp v2/export-session.sh ~/.claude/scripts/export-session.sh
chmod +x ~/.claude/scripts/export-session.sh

# 2. Wire it into ~/.claude/settings.json
```

Add to `~/.claude/settings.json`:
```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/.claude/scripts/export-session.sh",
            "timeout": 15,
            "statusMessage": "Exporting session transcript..."
          }
        ]
      }
    ]
  }
}
```

The script auto-detects the output directory: uses `{cwd}/docs/sessions/` if it exists, otherwise `~/.claude/sessions/`.

## SESSION_INDEX.md

After export, `docs/sessions/SESSION_INDEX.md` looks like:

```
| ID         | Date       | Branch        | Summary                                              | File |
|------------|------------|---------------|------------------------------------------------------|------|
| 021f1273…  | 2026-06-21 | deploy/test   | Translating item titles for company 66 to production | 021f1273….md |
| 826db1cf…  | 2026-06-27 | feature/PRD-021 | PRD-021 agent permission system fully implemented  | 826db1cf….md |
```

Search: `grep "company 66" docs/sessions/SESSION_INDEX.md` — one result, instant.

## Session File Format

Each `{session_id}.md` contains:
- Title (from `aiTitle`)
- Session ID, branch, start time, export time
- `Forked from: {parent_session_id}` if this session was a rewind/branch
- **Session Summary** — the last `away_summary` from Claude (most complete state description), with earlier summaries collapsed in a `<details>` block
- Full conversation transcript

## Rewinds and Branches

When you rewind mid-session or use `/branch`, Claude Code creates a new session ID. The new session's JSONL contains a `forkedFrom: {sessionId, messageUuid}` field on every message. v2 reads this and adds a `Forked from` line to the session file, so you can trace the lineage.

## Bulk Migration

To re-export all existing sessions for a project:

```bash
find ~/.claude/projects/-home-ali-empty-Regal-regal-backend -name "*.jsonl" | while read f; do
    sid=$(basename "$f" .jsonl)
    payload="{\"session_id\": \"$sid\", \"cwd\": \"/home/ali/empty/Regal/regal_backend\"}"
    echo "$payload" | bash ~/.claude/scripts/export-session.sh 2>/dev/null
done
```
