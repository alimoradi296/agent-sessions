# Native archive importer comparison

Review date: October 25, 2026. All runtime inputs were invented synthetic traces.
The comparison tested parsers rather than complete CLI workflows or database persistence.

## Existing importer execution

Pinned [agent-replay](https://github.com/clay-good/agent-replay/tree/ccda6229a9451692fb6f1d6d323dd825c2be9dbb) at revision `ccda6229a9451692fb6f1d6d323dd825c2be9dbb`.
The [probe](../examples/compare_native_importers.mjs) compiles its existing Claude and Codex importer code with esbuild.
Only `ingestTrace` is replaced, capturing its input instead of writing a database.
The source checkout stays unchanged; the probe uses no service or real transcript.

Each trace includes an initial request, two paired tool calls, a later correction, and a final response.
The correction occurs between the two calls.
Arguments exceed 1,300 characters, and one tool result contains 1,700 characters.
The Codex fixture includes function and custom tool-call families.
The Claude fixture includes an explicit failed tool-result flag.

| Observed field | Native Codex importer | Native Claude importer |
|---|---|---|
| Session identity | Retained | Retained |
| Initial request | Retained | Retained |
| Later correction text | Retained | Retained |
| Final response | Retained | Retained |
| Two tool-call identities | Retained | Retained |
| Complete argument and long result content | Retained | Retained |
| Skipped fixture records | 0 / 8 | 0 / 7 |
| Explicit Claude error flag | Not supplied in this format | Retained |

The Codex fixture's result contains a process-exit string rather than an explicit error flag.
The native importer kept that text without marking its tool step as failed.
This observation does not establish a missed explicit status field.

These native importers already preserve much of the proposed adapter's basic data.
No manual conversion of fixture records was required before calling the parsers.
The storage substitution means the full import command and persisted output remain untested.

## Remaining chronology limit

Both importers retain later user turns as text in `metadata.follow_up_prompts`.
That array does not retain the correction's timestamp or source-line position.
Tool steps retain their own timestamps, but the imported payload alone cannot place this correction between them.
The original raw transcript still contains that position.
This is a reconstructed-payload limitation, not proof that the entire project cannot support chronological replay.

Whether preserving this position produces a useful regression case remains untested.
A field-level difference alone does not establish a distinct product.

## Defect found in this repository

The same fixture exposed losses in our Claude parser before correction:

- Tool call and result IDs were empty.
- Arguments and results were truncated to 300 and 500 characters.
- The explicit error flag was discarded.
- Messages lacked source-line locations.

The parser now keeps complete tool arguments and results, call IDs, boolean error flags, and source locations.
The short argument summary remains bounded for display.
Missing error flags stay unknown instead of becoming success.
Regression tests check complete rendering and paired evidence.
The corrected fixture retains all seven message locations and the explicit failed result.

This fixes existing evidence loss; it is not a new competitive capability.
Image content, sidechains, resumed-session merging, and general format compatibility were not covered by this two-fixture probe.

## Reproduce

Use the pinned checkout and an installed esbuild module in a separate temporary environment:

```sh
node examples/compare_native_importers.mjs /path/to/checkout /path/to/esbuild/lib/main.js /path/to/new-private-output
```

The output directory must not exist.
The script generates only synthetic fixtures and parser reports.
It does not install packages, change agent settings, upload traces, or run a model.

## Decision

Do not build a generic importer merely to preserve messages and paired tools that existing code already handles.
Next, test whether correction-to-tool ordering changes a reproduced regression when using an existing replay engine.
Use the original raw trace as a baseline and measure required preparation work.
Reject the chronology adapter hypothesis if a small existing transformation gives equivalent results.
No willingness to pay or exclusive capability is established.
