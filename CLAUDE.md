# agent-sessions — Claude Instructions

## What This Repo Is

A universal AI agent session exporter. Parses JSONL transcripts from Claude Code, Codex, and Cursor into deduplicated, searchable Markdown with a shared index.

## Structure

```
agent_sessions/
  __init__.py         — package root, exports public API
  __main__.py         — `python3 -m agent_sessions` entry
  models.py           — Session, Message, TokenUsage, ToolCall dataclasses
  cli.py              — argparse CLI: hook, export, bulk, search, stats, install
  hook_setup.py       — Codex/Cursor user-level configuration and pinned launchers
  reconcile.py        — source comparison, selective export, private reconciliation reports
  storage.py          — directory locks and atomic file replacement
  parsers/
    __init__.py       — PARSERS registry dict
    claude.py         — Claude Code JSONL parser
    codex.py          — Codex CLI JSONL parser
    cursor.py         — Cursor IDE JSONL parser
  renderers/
    __init__.py
    markdown.py       — Session → {session_id}.md
    index.py          — Session → SESSION_INDEX.md (one line per session)
    json_index.py     — Session → sessions.json (machine-readable)
  analysis/
    distiller.py      — Session → .distilled.json
    linker.py         — cross-session graph
    obsidian.py       — distilled → Obsidian notes
    report.py         — weekly reports
    doctor.py         — read-only archive and hook diagnostics
    context.py        — cited, unverified conversation excerpts
    transcript.py     — conversation prose filtering
v1/                   — original naive implementation (preserved for history)
v2/                   — claude-only smart implementation (preserved for history)
```

## Key Design Decisions (Do Not Revert)

- **Parser/renderer split** — parsers return a `Session` dataclass, renderers consume it. Adding a new agent = one new parser file. Never put agent-specific logic in renderers.
- **Filename is `{session_id}.md`** — overwrite on re-export, no duplicates.
- **`away_summary` is the real summary** (Claude only) — prefer last one (most complete).
- **`forkedFrom` is the rewind/branch link** — read from first message in Claude sessions.
- **`SESSION_INDEX.md` stays one line per session** — grep-able. Never turn it into a full transcript.
- **`sessions.json` is the programmatic interface** — all metadata, tokens, durations. Markdown is for humans.
- **Token usage is cumulative** — Codex gives `total_token_usage` snapshots (use last one). Claude gives per-message usage (sum all).
- **No external dependencies** — stdlib only. This must run on any machine with Python 3.10+.

## JSONL Format Reference

### Claude Code
- Location: `~/.claude/projects/<slug>/<session_id>.jsonl`
- Key events: `user`, `assistant`, `ai-title`, `custom-title`, `system` (subtype=`away_summary`), `attachment`
- Messages carry: `forkedFrom`, `gitBranch`, `cwd`, `timestamp`, `usage`, `model`, `isSidechain`

### Codex
- Location: `~/.codex/sessions/YYYY/MM/DD/rollout-<datetime>-<session_id>.jsonl`
- Wrapper: `{"type": "...", "payload": {...}}`
- Key event types: `session_meta`, `event_msg` (subtypes: `task_started`, `turn_completed`, `turn_aborted`, `user_message`, `agent_message`, `token_count`), `response_item`
- Thread names in: `~/.codex/session_index.jsonl`

### Cursor
- Location: `~/.cursor/projects/<slug>/agent-transcripts/<id>/<id>.jsonl`
- Minimal format: `{"role": "user"|"assistant", "message": {"content": [...]}}`
- Also: `{"type": "turn_ended", "status": "success"|"aborted"}`
- No timestamps, no branch, no usage data in JSONL

## What NOT to Do

- Do not add external dependencies — stdlib only
- Do not put agent-specific logic in renderers
- Do not add timestamp to output filenames
- Do not sort the index alphabetically — newest-first insertion order
- Do not remove v1/ or v2/ — they document the evolution
- Do not hardcode paths — use Path.home() and the resolution chain
- Keep generated hook launchers, private configuration, backups, and transcript fixtures outside the repository.
- Hook stdout must remain JSON. Test generated launchers from an unrelated directory with synthetic data.
