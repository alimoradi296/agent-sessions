# Code decision archaeology screen

Run date: October 28, 2026.

## Candidate

Let a solo engineer using multiple coding agents ask why a current code path exists, and retrieve the earlier agent decisions, constraints, and failed approaches with source citations.

## Public evidence

- [`nicknisi/sessions`](https://github.com/nicknisi/sessions) documents Claude Code, Codex, and Pi support, session search, cross-agent continuation, and a `sessions why <target>` command that correlates files, lines, or commits with sessions. The repository describes read-only Git correlation and source excerpts.
- [`ctx`](https://ctx.rs/) documents local indexing across agent sources, session search, and `ctx blame` that links code lines or commits to sessions with citations to transcript messages and tool calls. Its docs also say it cannot prove attribution when the teammate's session is unavailable locally.
- [Entire Agentic Search](https://entire.com/blog/introducing-agentic-search-for-code-and-context) says its search returns code, reasoning, and session transcripts across repositories and agents. Its benchmark is vendor-reported and was not independently reproduced.
- [Waypoint](https://docs.getwaypoint.dev/) describes synthesizing agent-session events into searchable decisions linked to files and commits, with agent-facing context injection. This screen did not test the software.
- Pi's [official extension docs](https://pi.dev/docs/latest/extensions) say nested calls do not create transcript entries and their persisted `nestedCalls` summary omits results, with per-call/per-result size bounds and a 256-call cap. The same API exposes nested `tool_execution_end` events with results and parent IDs to extensions.
- [`pi-trace-extension`](https://pi.dev/packages/pi-trace-extension) documents durable `events.jsonl` and `trace.html` output built from provider and tool lifecycle events, including tool results and subagent traces. It is local and single-user; the docs say string values are truncated at 8 KB, retention is not rotated, and prompts/tool outputs are stored without broad PII redaction.
- [`pi-session-tracer`](https://github.com/aaroncarry/pi-session-tracer) documents live inspection of tool arguments and outputs, but keeps live capture in memory, caps tool output at 16 KB and the live store at 500 turns; historical replay cannot recover timings that Pi did not persist.

## Fresh reliability signal

The [ctx issue tracker](https://github.com/ctxrs/ctx/issues) currently lists open reports about [Codex code-mode `exec` extraction (#1144)](https://github.com/ctxrs/ctx/issues/1144), [Pi nested tool-call parsing (#1143)](https://github.com/ctxrs/ctx/issues/1143), and [Claude/Pi commit attribution (#1142)](https://github.com/ctxrs/ctx/issues/1142), alongside an OpenCode large-cell hydration issue. These titles identify concrete parser and attribution failure modes in a direct competitor. They are maintainer issue reports, not evidence of broad user prevalence, paid demand, or persistent defects in the latest release; the individual issue pages could not be independently fetched in this screen.

The local Codex parser preserves a `custom_tool_call` named `exec` and its paired output as source-backed tool-call/result records. The captured-file reader separately attempts static extraction of complete literal `tools.apply_patch(...)` calls from an `exec` body. That does not establish general Code Mode action attribution, arbitrary shell effects, provider completeness, or a product advantage. Existing recovery is already scoped to authored literal inputs and labels execution as unknown.

For Pi, a prospective live capture extension could preserve nested execution events that the native session summary omits, but Pi already exposes those events and the documented trace extensions capture them. An adapter to ingest such traces into a cross-agent archive would be an integration, not a defensible product by itself. No customer workflow, time savings, or paid demand for that adapter is established.

## Decision

Close generic code-decision archaeology as a product lead. The candidate is directly served by multiple current projects, including tools aimed at individual local workflows as well as broader repository search. Cross-agent support, source citations, and local indexing are not sufficient differentiation claims by themselves.

This is a documentation screen, not a runtime comparison. Competitor descriptions do not prove accuracy, adoption, or commercial success. The specific failure, user time saved, and willingness to pay for this repository remain unestablished.

## Commercial signal

The [ctx changelog](https://www.ctx.rs/changelog/) describes `ctx pro` as a separately subscribed feature for file, commit, and pull-request blame, with a 14-day trial and a browser flow to subscribe. This is evidence that one vendor is attempting to monetize agent-session attribution. It does not establish paid conversion, customer count, revenue, or willingness to pay for this repository. The currently indexed standalone page that once exposed a price is not a reliable current price source, so no amount is claimed here.

Do not implement another session search, agent blame, decision index, rationale summarizer, or Pi trace collector. Static source review shows the Codex reader preserves the outer call/result and has narrowly scoped literal-patch recovery; Pi's native session format omits some nested result detail, but its extension API and existing trace extensions expose and persist more. The broad decision-archaeology task is covered. Do not spend time on a synthetic comparison that cannot change that product decision. Continue by finding a recurrent, costly target-user job from public evidence and require a same-case comparison before reopening a feature.

Keep real agent histories and repository paths outside the public repository. Any future public fixture must be synthetic.
