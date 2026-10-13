# agent-sessions

Searchable local exports of Claude Code, Codex, and Cursor transcripts.

The CLI writes one Markdown file per session ID, a readable index, and a JSON index.
Repeated exports update the same session file. Optional commands extract decisions and connect related sessions.

**Status:** Source-installable `0.2.0` CLI. Transcript formats and hook support depend on the installed agent version.

[Try a sample export](#try-a-sample-export) · [Export your sessions](#export-your-sessions) · [Limits and privacy](#limits-and-privacy)

## Try a sample export

Requirements: Python 3.10 or later.

```bash
git clone https://github.com/alimoradi296/agent-sessions.git
cd agent-sessions
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python examples/demo.py
```

The demo uses a synthetic transcript in this repository. It does not read your agent history or install hooks.
It creates these files in `demo-output/`:

```text
demo-output/
├── sample-session.md
├── SESSION_INDEX.md
└── sessions.json
```

Search the exported title and summary:

```bash
agent-sessions search "retry" -d demo-output
agent-sessions stats -d demo-output
```

Open `demo-output/sample-session.md` to inspect the conversation and session metadata.

## Supported Agents

| Agent | Source Location | Hook Support | Token Tracking |
|---|---|---|---|
| Claude Code | `~/.claude/projects/<slug>/*.jsonl` | Stop hook (auto) | Yes |
| Codex | `~/.codex/sessions/YYYY/MM/DD/*.jsonl` | Stop hook (auto) | Yes |
| Cursor | `~/.cursor/projects/<slug>/agent-transcripts/` | hooks.json | No (not in JSONL) |

## Export your sessions

Use the source installation in the sample procedure above.
The CLI reads the agent directories in the table. Export one session first:

```bash
agent-sessions export claude <session-id> --dry-run
agent-sessions export claude <session-id> -o ./exports
```

Replace `<session-id>` with an existing session ID.
The dry run prints the proposed destination and metadata without exporting files.
Review the output before a bulk export or hook installation.

### Install the Claude Code Stop hook (automatic export on every session end):

```bash
agent-sessions install claude
```

### Cursor hook (manual setup):

```bash
agent-sessions install cursor
# Prints the hooks.json snippet to add to your project
```

### Install the Codex Stop hook (requires a version with Stop hook support):

```bash
agent-sessions install codex
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
agent-sessions search "retry" -d ~/my-sessions/
```

### View aggregate stats

```bash
agent-sessions stats -d ~/my-sessions/
```

Illustrative output, not a benchmark or usage report:
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
agent-sessions link --prd DEMO-001 -d ~/.agent-sessions/exports/
agent-sessions link --branch main -d ~/.agent-sessions/exports/
agent-sessions link --file example.py -d ~/.agent-sessions/exports/
agent-sessions link --session-id 826db1cf-... -d ~/.agent-sessions/exports/
```

Graph edge types: `same_prd`, `same_branch`, `same_file`, `forked_from`

### Export to Obsidian

```bash
agent-sessions to-obsidian \
  --vault /path/to/your/vault \
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

## Limits and privacy

- Agent transcript formats can change. The parsers recognize the formats implemented in this checkout.
- Cursor exports lack token usage and branch metadata in the parsed format. Missing token counts do not mean zero usage.
- Session titles and extracted outcomes are metadata or heuristics. They do not prove completion or deployment.
- Hook installation changes local agent settings. Verify hook support in your installed agent version before installation.
- Exported transcripts can contain prompts, file paths, tool results, and sensitive project information.
- The parser and export commands operate locally. Review generated files before sharing or committing them.

The sample procedure verifies export, indexing, and search with synthetic data.
It does not certify every agent version or hook lifecycle.

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
