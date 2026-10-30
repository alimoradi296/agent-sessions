# Compaction and requirement continuity screen

Status: closed as a generic product lead after a direct competitive search. No implementation or product differentiation is established.

## Narrow problem hypothesis

When a coding agent compacts a long conversation or hands work to a new session, a user-set requirement can disappear or change while the agent continues as if the task were unchanged. A useful tool might compare the user's original requirements with each available compacted summary or handoff, preserve source links, and show whether the final artifact addresses them.

The proposed target is a solo engineer moving work between coding agents. This is not a claim that every omitted requirement is important, that the summary is the only active task state, or that an offline check can prove task completion.

## Evidence that the problem matters

- [CompactionBench](https://arxiv.org/abs/2610.31778), submitted October 22, 2026, reports that summaries on ProgramBench omitted about one third of anti-cheating constraints after the first compaction. In its SWE-chat analysis, work-style and negative instructions were dropped more often than build specifications. This is study evidence, not a prevalence estimate for all coding-agent users.
- [Cline issue #14732](https://github.com/cline/cline/issues/14732) is open and reports that a summary returned with a provider `incompleteReason` may replace compacted history without a persisted degraded-state marker. The issue discussion also identifies a computed but unpersisted count of source messages excluded before summarization. This is one issue report, not an independent reproduction here.
- [Cline's current SDK architecture](https://github.com/cline/cline/blob/main/sdk/ARCHITECTURE.md#9-context-compaction) describes keeping canonical session history append-only while storing compaction state separately, validating it against a hash of the covered transcript prefix, and warning that older already-compacted histories cannot recover omitted originals.
- [Anthropic's long-running-agent guidance](https://www.anthropic.com/research/effective-harnesses-for-long-running-agents) and [Cloudflare's long-running-agent documentation](https://developers.cloudflare.com/agents/concepts/agentic-patterns/long-running-agents/) recommend structured plans, files, or persisted state across context windows. These approaches overlap with continuity support but do not by themselves establish an audit across arbitrary CLI transcripts.

## Existing coverage and uncertainty

The direct match is [`compaction-loss-check`](https://basitalisandhu.github.io/claude-skills/plugins/cc-setup-tooling/compaction-loss-check/index.html), an open-source Claude Code skill that inspects each compaction, compares the summary with standing rules, edited files, and open tasks, and reports known limits such as paraphrase misses and transcript truncation. [Compaction.dev](https://www.compaction.dev/) markets per-turn input/output comparison and preservation decisions across Claude Code, Codex, and Cursor. These products directly overlap with compaction-loss inspection and cross-agent continuity. Their public claims are not independent runtime validation, but they close the broad product claim.

CompactionBench, structured task-state features, and the repo's own transcript extraction, evidence-linked handoffs, and reviews add further overlap. The repository's earlier tests are a warning against assuming value: the [three-reader exercise](fresh-session-results.md) found the requirements pack matched full-source reading after citation review, while full sources were shorter for that small history. The [long-history exercise](long-history-results.md) found a carefully selected manual handoff matched the requirements presentation. The [changed-context coding comparison](changed-context-coding-results.md) found identical code and all predeclared checks passed for saved notes and a source-bound handoff. None exercised an agent's native compaction boundary, so none validates the narrower compaction-specific hypothesis.

No reviewed source establishes user willingness to pay, but novelty is not the only problem: the core inspection workflow is already offered. Reopen only for a specific consequential failure those tools do not expose, supported by a measured incremental outcome and buyer evidence. “No other repository can do this” is not established and cannot be inferred from a limited search.

## Reopen criteria

Only reconsider this direction if a current, reproducible user case demonstrates a costly compaction loss that both native agent state and the existing checkers miss. Compare on synthetic inputs first, use source anchors, measure false alerts and review effort, and gather separate buyer evidence before implementation. Do not publish personal transcripts or results.
