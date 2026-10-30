# Verification freshness screen

**Date:** 2026-10-28
**Status:** Closed as a product lead; no runtime comparison performed.

## Initial signal

A plausible failure is that an agent reports a green test run even though it edited relevant files afterward. A useful tool would need to link the check output, changed files, and final claim without trusting the model's summary.

## Existing coverage

- [Backcheck](https://github.com/VectorInstitute/backcheck) reads Claude Code transcripts and checks claims against recorded commands and edits. Its published examples explicitly cover tests that passed before later source edits, partial test runs presented as full-suite success, and test suites weakened by edits. It reports source coverage and limitations; this is a direct match for the initial signal.
- [Treft](https://treft.dev/) describes independent PR verification in a clean sandbox, with evidence separated from the coding agent's summary. This covers the adjacent workflow of checking a patch before merge.
- [Yoetz](https://yoetz.dev/) documents local receipts that compare agent-reported plans/work/claims with host-reported sessions, tool calls, and edits for Codex, Claude Code, and Cursor. Its page explicitly shows a test claim rejected because the recorded pass predates the last edit.
- [trustbut](https://github.com/isAlmogK/trustbut) documents fresh test reruns, checks whether new tests fail on the base revision, and flags skipped tests and weakened checks across several coding agents. It focuses on whether the change is proven rather than transcript claim parsing.
- [evigate](https://github.com/shiki-yusuke/evigate) documents local deterministic detectors for completion claims, plus an authored mutation evaluation harness. Its own notes distinguish mutation coverage from natural-data recall evidence.
- [Explyt's verification guide](https://explyt.ai/docs/getting-started/guides/verify-agent-report) documents checking run timestamps and test counts against the last edit. This is a documented workflow, not proof of an automated competitor feature.

These are published product descriptions, not independent runtime validation. Backcheck's claimed tests over 81 sessions are its own report, not independently audited here. No customer incidence, usage, or willingness-to-pay evidence was collected.

## Decision

Close stale-test detection and generic “verify what the agent says” as product leads. Backcheck directly addresses transcript-level freshness; Yoetz covers cross-agent receipts and freshness; trustbut independently checks whether tests establish the changed behavior; Treft checks PRs in a clean sandbox; evigate evaluates transcript claim detectors. This repository has no measured incremental advantage. Do not implement a checker, hook, dashboard, or competing PR verifier from this screen.

## Next discovery direction

Continue from a different customer outcome, not another summary or verification surface. Start with real, public maintainer/user reports of a costly workflow involving agent-session records, then map the exact task to current tools and this repository's existing capabilities before proposing a prototype. Public reports can establish that a person reported a problem, but not prevalence, market size, or willingness to pay. Private transcripts and personal records are not needed for this research and must stay out of the public repository.
