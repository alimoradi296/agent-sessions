# agent-sessions

Universal AI agent session exporter. Turns raw JSONL transcripts from Claude Code, Codex, and Cursor into searchable, deduplicated Markdown files with a live index.

## The Problem

Every AI coding agent stores session transcripts in its own format, in its own location. None of them give you a human-readable, searchable archive. Without this tool:

- Sessions pile up as opaque JSONL files across `~/.claude/`, `~/.codex/`, `~/.cursor/`
- No way to find "what session covered topic X" without grep archaeology
- No duration, token usage, or cost tracking per session
- Rewinds/branches have no link back to their parent session
- No cross-agent view of your work

## Supported Agents

| Agent | Source Location | Hook Support | Token Tracking |
|---|---|---|---|
| Claude Code | `~/.claude/projects/<slug>/*.jsonl` | Stop hook (auto) | Yes |
| Codex | `~/.codex/sessions/YYYY/MM/DD/*.jsonl` | Manual (bulk) | Yes |
| Cursor | `~/.cursor/projects/<slug>/agent-transcripts/` | hooks.json | No (not in JSONL) |

## Installation

```bash
pip install -e /path/to/agent-sessions
# or from the repo directory:
pip install -e .
```

### Install the Claude Code Stop hook (automatic export on every session end):

```bash
agent-sessions install claude
```

### Cursor hook (manual setup):

```bash
agent-sessions install cursor
# Prints the hooks.json snippet to add to your project
```

### Codex (no hook support — use bulk export):

```bash
agent-sessions bulk --agent codex -o ~/my-sessions/
```

## Usage

### Export a single session

```bash
agent-sessions export claude <session-id>
agent-sessions export codex <session-id>
agent-sessions export cursor <session-id>

# Dry run — see what would be exported without writing
agent-sessions export claude <session-id> --dry-run
```

### Bulk export all sessions

```bash
# All agents
agent-sessions bulk -o ~/my-sessions/

# One agent
agent-sessions bulk --agent claude -o ~/my-sessions/

# One project
agent-sessions bulk --agent claude --project home-ali-myproject -o ~/my-sessions/
```

### Search across sessions

```bash
agent-sessions search "authentication"
agent-sessions search "company 66" -d ~/my-sessions/
```

### View aggregate stats

```bash
agent-sessions stats -d ~/my-sessions/
```

Output:
```
Total sessions: 142
Total messages: 3,847
Total tokens:   12,453,200
Total duration: 47.2h

  claude: 98 sessions, 8,200,000 tokens, 32.1h
  codex:  31 sessions, 3,100,000 tokens, 11.4h
  cursor: 13 sessions, 0 tokens, 3.7h
```

## Output Format

### Session files (`<session-id>.md`)

Each file contains:
- Title, agent, session ID, branch, model
- Forked-from link (if rewind/branch)
- Duration and token usage
- Session summary (from `away_summary` for Claude)
- Full conversation transcript

### SESSION_INDEX.md

One searchable line per session:

```
| ID | Agent | Date | Branch | Duration | Messages | Summary | File |
|---|---|---|---|---|---|---|---|
| 021f1273… | claude | 2026-06-21 | deploy/test | 1h 23m | 12u/45a | Translating item titles... | 021f1273….md |
```

### sessions.json

Machine-readable index with full metadata, token counts, and durations. Enables programmatic queries like "show me all sessions on branch X between date A and B".

## Architecture

```
Raw JSONL (agent-specific)
    ↓
Parser (one per agent)         ← claude.py, codex.py, cursor.py
    ↓
Canonical Session dataclass    ← models.py
    ↓
Renderers (shared)             ← markdown.py, index.py, json_index.py
```

Adding a new agent = write one parser that returns a `Session`. All renderers work automatically.

## Knowledge Extraction (v0.2)

Turn transcripts into structured knowledge:

```
Raw transcript (.md)
    ↓
distill  →  {session_id}.distilled.json  (PRDs, files, decisions, bugs, deferred)
    ↓
link     →  sessions_graph.json           (cross-session relationships)
    ↓
to-obsidian → Obsidian notes with frontmatter
report   →  weekly markdown report
```

### Distill sessions

```bash
# All exported sessions
agent-sessions distill -d ~/.agent-sessions/exports/

# Only significant sessions (PRD work, 30m+, 5+ files, decisions)
agent-sessions distill -d ~/.agent-sessions/exports/ --significant-only

# One session
agent-sessions distill <session-id> -d ~/.agent-sessions/exports/
```

Each `.distilled.json` contains:
- PRDs worked on, files touched, tools/commands used
- Inferred outcome (implemented, fixed, reviewed, planned, etc.)
- Extracted decisions, bugs, deferred work, open questions
- Significance score (0–10) for filtering

### Link related sessions

```bash
# Build relationship graph
agent-sessions link --build -d ~/.agent-sessions/exports/

# Query by PRD, branch, file, or session
agent-sessions link --prd PRD-021 -d ~/.agent-sessions/exports/
agent-sessions link --branch deploy/new_test -d ~/.agent-sessions/exports/
agent-sessions link --file apps/users/permissions.py -d ~/.agent-sessions/exports/
agent-sessions link --session-id 826db1cf-... -d ~/.agent-sessions/exports/
```

Graph edge types: `same_prd`, `same_branch`, `same_file`, `forked_from`

### Export to Obsidian

```bash
agent-sessions to-obsidian \
  --vault ~/empty/growing_in_my_mind \
  --since 2026-07-01 \
  --significant-only \
  -d ~/.agent-sessions/exports/
```

Creates notes in `Agent Sessions/` with YAML frontmatter, PRD links, decisions, and deferred work.

### Weekly report

```bash
agent-sessions report --week -d ~/.agent-sessions/exports/
agent-sessions report --since 2026-07-01 -o ~/report.md
```

## History

### v1 — Original (Claude-only, naive)
- `{timestamp}-{session_id}.md` per Stop event — caused hundreds of duplicates
- Git-log-based summary — never useful

### v2 — Claude-only, smart
- Deduplication via `{session_id}.md` naming
- `away_summary` as real session summary
- `forkedFrom` tracking
- `SESSION_INDEX.md`

### v3 — Universal
- Multi-agent: Claude Code, Codex, Cursor
- Parser/renderer architecture — new agents are one file
- Token usage and duration tracking
- `sessions.json` machine-readable index
- pip-installable CLI with `export`, `bulk`, `search`, `stats`, `install`
- `--dry-run` flag

### v0.2 — Knowledge extraction (current)
- `distill` — structured JSON per session (PRDs, files, decisions, bugs, deferred)
- `link` — cross-session graph (same PRD, branch, file, fork lineage)
- `to-obsidian` — Zettelkasten-friendly notes with frontmatter
- `report` — weekly aggregate report with extracted knowledge
