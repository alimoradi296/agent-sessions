# Synthetic tail-restriction probe

This probe compares one selection behavior, not complete products or model outcomes.
It uses invented text and no real agent history.

## Question

Does a context pack retain a required restriction at the end of a relevant source?
If that restriction does not fit, does the workflow reject a ready handoff?

## Inputs

The shared fixture is [continuity_tail_case.json](../tests/fixtures/continuity_tail_case.json).
It generates one 4,230-character source about an example cache.
The final sentence is `Discovery only. Do not implement or publish.`
The query is `example cache`.
The source contains no competing decision, inferred authority, or external evidence.

## Qarinah observation

The runtime probe used Qarinah `0.8.0` at commit `d62e1d80ba6034cc7be4b35ea5f8e7df318d9253`.
It called the public `compileContext` API with `inMemory: true` and `minimumCoverage: "direct"`.
Machine state and the synthetic workspace remained in a new temporary directory.
Dependency installation disabled package scripts.

| Complete packet limit | API returned | Required restriction retained | Reported `truncated` | Excerpt characters |
|---|---|---|---|---|
| 3,000 | Yes | No | `true` | 1,773 |
| 6,000 | Yes | No | `false` | 2,000 |
| 12,000 | Yes | No | `false` | 2,000 |

The inspected [source implementation](https://github.com/AjnasNB/qarinah/blob/d62e1d80ba6034cc7be4b35ea5f8e7df318d9253/src/compiler.js) limits normal excerpts to 2,000 characters before packet fitting.
The observation concerns this API path and revision only.
It does not establish that another Qarinah workflow cannot recover the full source or enforce a custom requirement.

## Qarinah full-recall counterexample

The extended probe also ran the public `recallChatMemory` API at the same pinned revision.
It used `detail: "full"`, the source ID cited by `compileContext`, and each budget from the shared fixture.
The caller followed `nextOffset` until the API returned the complete source.
Every page retained the original source hash, and the concatenated excerpts exactly matched the 4,230-character input.

| Per-call packet limit | Calls | Packet characters | Complete source recovered | Restriction recovered |
|---|---:|---|---|---|
| 3,000 | 2 | 2,902 and 2,578 | Yes | Yes, on the second page |
| 6,000 | 1 | 4,856 | Yes | Yes |
| 12,000 | 1 | 4,856 | Yes | Yes |

The probe checked each canonical JSON packet against its per-call limit.
The 3,000-character case uses two separate packets, not one packet within a shared 3,000-character budget.
These packet counts are not equal-budget task-performance comparisons with this repository's handoff.

The inspected [full-recall implementation](https://github.com/AjnasNB/qarinah/blob/d62e1d80ba6034cc7be4b35ea5f8e7df318d9253/src/chat-memory.js) supports explicit source IDs, offsets, and bounded full-source slices.
The [public type declaration](https://github.com/AjnasNB/qarinah/blob/d62e1d80ba6034cc7be4b35ea5f8e7df318d9253/types/index.d.ts) exposes those options.
No custom adapter, source patch, model, or private transcript was needed.

This is a concrete counterexample to any claim that Qarinah cannot recover the restriction.
The earlier `compileContext` observation still holds for that API path, but it cannot establish product-wide superiority.
The caller explicitly requested full recall after receiving a citation.
This run does not establish whether an independent agent discovers that need or whether Qarinah enforces arbitrary required quotes.

## This repository's observation

The local probe pins the exact restriction and complete section before compilation.
It sets both the source limit and the complete handoff limit to each stated budget.

| Complete handoff limit | Required restriction retained | Ready | Reason |
|---|---|---|---|
| 3,000 | No | No | The complete required section exceeds the source limit |
| 6,000 | Yes | Yes | Evidence-only rendering retains the complete section within the total limit |
| 12,000 | Yes | Yes | The complete required section and framing fit |

Earlier structured rendering failed the 6,000-character limit because its framing and repeated summaries exceeded that limit.
The current evidence-only rendering removes those duplicate summaries and fits the same complete source.
Required evidence selection, source limits, and total-limit checks remain unchanged.

The measured workflow distinction is explicit required-evidence failure behavior before a pack passes readiness.
Recovering complete source evidence is not an exclusive capability.
It is not proof of better retrieval, lower token usage, or correct agent continuation.
Packet formats, metadata, and character accounting differ.
The original query-only command and a careful manual handoff remain useful baselines for a broader evaluation.

## Reproduce

After installing this package, run:

```bash
python examples/evaluate_continuity.py
```

For the external API probe, prepare a separate reviewed Qarinah checkout at the pinned revision.
Install its declared dependencies with package scripts disabled.
Then run:

```bash
node examples/compare_context_selection.mjs /path/to/qarinah
```

The script performs no downloads and changes no agent configuration.
It records the actual checkout revision and package version in its output.
It creates synthetic Qarinah state only under a new temporary directory.
The external runtime dependencies are not dependencies of `agent-sessions`.

## Evidence limits

This is one deterministic fixture with one required quote.
There is no receiving model, human timing measurement, usability study, or paid-user evidence.
The result does not establish exclusive capability or product superiority.
The full-recall counterexample covers one additional API path.
The next comparison needs multiple constraints, corrections, and an actual continuation task with the stronger recall baseline.
