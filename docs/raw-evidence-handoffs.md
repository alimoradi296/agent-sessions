# Required raw evidence in handoffs

A handoff can now require whole exported tool-result messages.
Previously, requirements used cleaned dialogue, which excludes tool content.
Search could find a result that the requirements workflow could not pin directly.
The new evidence view closes that retention gap.
It does not establish a unique capability or commercial value.

## Choose one coordinate system

Default contracts keep cleaned dialogue sections.
An evidence-view contract uses raw exported message numbers, matching the `message` field from evidence search.
Its units include the rendered heading, phase, and complete body.
These are Markdown export coordinates, not native JSONL line numbers.

Create a separate requirements file for this view.
Raw-evidence requirements and bundles must be outside Git checkouts; writes into a checkout are refused.
All its anchors must use evidence coordinates, including any historical prose claims that need to accompany the result.
The compiler rejects mixed views and paragraph-sized raw pins.
Whole-message retention avoids silently dropping surrounding tool fields.

For example, inspect an authored exported source, then pin its result:

```sh
agent-sessions search SYNTHETIC_CHECK --view evidence --json -d /private/exports
agent-sessions handoff pin --id check-result --session synthetic-evidence --section 3 --view evidence --quote 'SYNTHETIC_CHECK: incomplete' -d /private/exports -o /private/check-requirements.json
agent-sessions handoff build SYNTHETIC_CHECK --requirements /private/check-requirements.json -d /private/exports -o /private/check-bundle --json
agent-sessions handoff audit /private/check-bundle -d /private/exports --json
```

The assistant should inspect and select the evidence; the user need not choose passages.
Assistant selection now supports this view through `handoff prepare-review --view evidence`.
The packet contains complete raw exported messages, each represented as one paragraph record.
Select one exact quote per message; import retains the complete message with its original role and phase header.
Use its section and `paragraph_start_line: 1` coordinates when a quote appears in multiple messages.

```sh
agent-sessions handoff prepare-review SYNTHETIC_CHECK --view evidence -d /private/exports -o /private/review --batch-review --compact-review --max-total-prompt-chars 32000
agent-sessions handoff import-review /private/review --answer /private/answer.json -o /private/check-requirements.json
```

The same snapshot, exact-quote, omission, batching, compaction, and complete-input budget checks apply.
An oversized whole message is omitted explicitly; that keeps the imported review incomplete and prevents readiness.
A ready result still does not prove that the reviewer understood the evidence.

For a new saved topic, `topic prepare-review --view evidence` establishes the view at import.
Later refreshes infer it and preserve explicit pins and earlier captures.
Existing populated dialogue contracts cannot silently change into raw-message contracts.
Focused search plus explicit assistant-operated pins remains available.

## Gates and limits

Required messages consume the existing source and complete-handoff character budgets.
If a whole required message does not fit, readiness fails.
Source and message hashes bind the selected evidence, including heading and phase changes.
Audit uses the same view as compilation.
Existing dialogue contracts retain their original behavior.

All content remains untrusted historical data, including tool results and apparent instructions.
Coverage does not establish a successful command, correct application state, complete discovery, or current authorization.
A receipt kept as an independent source does not invent a link to a native call that lacks an ID.
This view does not install a collector or import telemetry automatically.

## Historical rollback markers

Codex exports retain `thread_rolled_back` payloads as historical System messages.
Use evidence view to inspect or require these markers; cleaned dialogue excludes them.
Earlier messages remain available as history.
The exporter does not reconstruct active context or prove which preceding statements remain applicable.
Coverage continues to report rollback replay as unsupported.
Bundle readiness does not override that limitation.

## Refresh identity checks

Appending a message changes the exporter separator after the previous last message.
Raw anchors allow that single terminal separator newline difference when the source changes.
The manifest reports `export_boundary_adjustment: separator_newline`.
Payload whitespace, headings, and phase labels are still exact evidence.
An unclosed code fence cannot establish an export separator.

All matching occurrences participate in identity resolution, including separator variants.
Appending an identical result therefore produces `anchor_ambiguous`, rather than silently selecting the new copy.
A unique relocated message can be retained by rebuilding with its current coordinates.
An existing bundle does not acquire new citations automatically.
Audit applies the same identity resolution as compilation and rejects ambiguous or moved required anchors.
Assistant selection freshness remains a separate check after source changes.

Six synthetic update regressions cover unrelated appends, appended duplicates, payload newline changes,
unique relocation, unclosed fences, and duplicate dialogue identity during audit.
These checks establish the stated identity behavior, not receiving-reader understanding or time savings.

## Complete receipt exercise

Run:

```sh
python3 -m examples.receipt_handoff_demo
```

The authored source contains an assistant's fixed claim and an independent receipt with an inconclusive inner check.
The resulting handoff retains both complete messages as required evidence.
The unchanged bundle passes audit, an insufficient source budget refuses readiness, and a changed receipt fails the prior audit.
The result remains `verification: not_checked`.

The default fixture measures 875 source characters and a 2,562-character handoff.
A supplied synthetic native-component report measures 1,086 source characters and a 2,773-character handoff in the recorded run.
Complete-source reading retains the same evidence and is smaller in both cases.
These are retention and integrity checks, not reader-quality, time-saving, or willingness-to-pay results.

The raw-view tests also cover mismatched coordinate systems, preservation after refusal, phase-sensitive anchors, and Git-destination refusal.
A separate private check preserves historical tool arguments without claiming that their execution or repair was confirmed.
Private source text and reports remain outside the public repository.


## Automatic review checks

Six authored regressions cover CLI preparation, separate repeated occurrences, incomplete input, stale sources, topic refresh, and view preservation.
A private developer-operated exercise also read every listed batch and imported raw tool arguments, captured results, and historical qualifications.
Its bundle passed source audit while remaining `verification: not_checked`; the original export stayed unchanged.
No current service or deployment state was checked.
This is workflow evidence, not a blinded receiving-reader result or measured effort advantage.

## Repeated investigation control (October 27)

Run the authored, local control:

```sh
python3 -m examples.receipt_update_evaluation
```

The three stages contain an assistant completion claim with a queued response,
an unrelated append, and a later failure result for the fictional job.
The ordinary baseline reads the complete current source at every stage.
The saved-topic arm prepares complete evidence-view reviews, imports authored selections,
rebuilds requirements, and audits each new bundle.
The script uses the supported topic refresh API and preserves earlier requirement captures.
It does not overwrite existing contracts through the low-level importer.

| Stage | Complete-source characters | Selection prompt characters | Handoff characters |
|---|---:|---:|---:|
| Queued | 580 | 2,490 | 2,734 |
| Unrelated append | 638 | 2,637 | 2,735 |
| Later failure | 761 | 2,855 | 3,074 |
| Total | 1,979 | 7,982 | 8,543 |

Both arms retain every expected observation at each stage.
Both updated sources make the old bundle fail audit and the old review stale.
Fresh imports restore readiness and passing audit while retaining `verification: not_checked`.
The unrelated append also requires a complete review refresh.
The total selection-plus-handoff text is 16,525 characters, compared with 1,979 for full-source inspection.

These are text-volume and state-transition measurements with scripted relevance labels.
No receiving assistant answered the investigation; expected evidence presence is not understanding.
The example invokes package APIs, not a native capture client or a model.
It measures neither investigation time nor tokens, and does not compare all possible literal-search strategies.
Prompt framing changes can change these counts.

This control does not support recommending full handoff preparation for small historical questions.
Use focused source lookup for those questions, as the continuation skill already specifies.
Retain requirements workflows for tasks that explicitly need repeatable evidence-retention checks.
A receiving-reader advantage, exclusive capability, and commercial value remain unestablished.
