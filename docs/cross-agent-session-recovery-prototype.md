# Cross-agent session recovery synthetic probe

**Date:** 2026-10-28
**Status:** Mechanism demonstration only; no product comparison or compatibility claim.

Run from the repository root:

```sh
python -m examples.probe_cross_agent_recovery
```

The probe creates temporary, invented stores for Codex, Claude Code, and Cursor. For each provider it exercises three states: source and index agree; a source transcript exists without a UI-index entry; and an index entry exists without a source transcript. It prints only provider, synthetic case, finding category, and counts. It does not attempt repair.

## Result

| Provider | Healthy case | Source present, index missing | Index entry, source missing |
|---|---|---|---|
| Codex | No action | Review possible visibility gap | Do not repair from index alone |
| Claude Code | No action | Review possible visibility gap | Do not repair from index alone |
| Cursor | No action | Review possible visibility gap | Do not repair from index alone |

All 9 authored cases produced their expected category. The result is expected for these hand-built inputs; it is not an accuracy estimate. Diagnosis reads the temporary fixture after creation and leaves its file hashes unchanged during classification. No real client data, provider process, native recovery tool, or external service was used.

## Important implementation gap

This is not yet a three-provider adapter. Codex and Claude cases call this repository's JSONL parsers, but use simplified synthetic UI indexes. The Cursor case uses newly authored SQLite structures based on a public report; it does not call the existing `CursorParser`, which reads Cursor project `agent-transcripts` JSONL files. The reported Cursor recovery case depends on global and workspace SQLite state. Likewise, this repository does not read Codex `state_5.sqlite` or Claude Desktop's native session metadata/index stores. The fixture shapes have not been validated against current installed client versions.

## What this establishes

The classifier mechanics can keep three outcomes separate: source and index agree, a possible navigation gap, and an index reference without source evidence. The last outcome must not trigger index reconstruction. A unified result vocabulary is feasible in a synthetic setup.

## What this does not establish

The probe does not show that current provider stores can be read reliably, that this workflow solves a case missed by SessionArk, AllSessions, or provider-specific scripts, that it is safer or faster than those tools, or that anyone will pay for it. It supplies no evidence of prevalence or willingness to pay.

## Decision

Keep this as a candidate, not a product direction. Before adding provider adapters, inspect current public source and release documentation for the exact storage formats and existing recovery behavior. Then compare one complete synthetic repair workflow with the provider-specific alternatives, including backup and rollback rehearsal. Stop if the result is only a common status report or if current tools already give users the same safe next action.
