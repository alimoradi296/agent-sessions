# Codex lifecycle consistency probe

Status: synthetic prototype only. No Codex archive or live app-server was read.

## What it checks

Codex persists parent/child spawn edges in SQLite and records turns in rollout
JSONL. This probe compares those two sources when the caller supplies their
paths explicitly. It does not discover `~/.codex`, read environment variables,
contact a provider, or modify any input.

The Codex source currently defines an `open` spawn edge as a child that is
“live or resumable.” A terminal turn marker therefore does not prove that the
edge is stale or that no worker is running. The probe reports
`terminal_turn_open_resumable_edge`; it does not call it a failure. See the
[edge status definition](https://github.com/openai/codex/blob/main/codex-rs/agent-graph-store/src/types.rs)
and [state edge operations](https://github.com/openai/codex/blob/main/codex-rs/state/src/runtime/threads.rs).

## Running the synthetic probe

```sh
python -m examples.probe_codex_lifecycle
python -m unittest tests.test_codex_lifecycle
```

The probe creates a temporary SQLite database and authored JSONL. Its cases
cover an open edge with a terminal marker, a closed edge with a terminal
marker, a nonterminal turn, missing or duplicate rollout matches, an unknown
edge status, and an unsupported database schema. Tests also compare the
database bytes before and after inspection.

For an explicit local experiment, call
`agent_sessions.analysis.codex_lifecycle.inspect_codex_lifecycle(database,
rollout_paths)` with paths you select. The input database is opened with
SQLite `mode=ro` and `PRAGMA query_only`. This API is experimental. Schema
drift is reported as unknown; rollout parsing errors and ambiguous matches
also remain unknown. The result includes local thread IDs, so do not publish
reports made from real local data.

## Limits and next gate

The probe recognizes only the supplied table columns and selected lifecycle
markers. It has not been exercised against a real Codex state database or
runtime, and no compatibility guarantee is made. A terminal rollout and an
open edge can represent a resumable thread. A nonterminal marker does not
prove a process is alive. No edge is closed, repaired, or assigned a liveness
state.

[AgentsView's usage docs](https://github.com/kenn-io/agentsview/blob/main/docs/usage.md)
document Codex termination classification, group status, and subagent trees.
[codex-threads](https://github.com/kcosr/codex-threads) documents querying
thread status and parent/child relationships through Codex's app-server.
[Agent Trail](https://github.com/sudhanshutech/agent-trail) documents session
tree visualization and replay. These overlap with status visibility, but their
public documentation does not establish whether they provide this offline
SQLite-to-rollout comparison. That gap is not proof of uniqueness. The
candidate stays unvalidated until a real user-facing advantage over those
tools is demonstrated without exposing local data.
