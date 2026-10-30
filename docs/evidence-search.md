# Search code and captured output

The default dialogue search indexes cleaned conversation prose.
This is useful for knowledge retrieval but omits fenced code, tool payloads, and phase-tagged assistant messages.
Those omissions prevent some command and traceback investigations.

Use the evidence view for raw exported message bodies:

```sh
agent-sessions search "entry.caption" --view evidence --role assistant --json
agent-sessions search "AttributeError" --view evidence --role user --json
agent-sessions search "synthetic failure" --view evidence --role tool --json
agent-sessions topic search example "caption" --view evidence --json
```

Search does not execute the source text or assign a causal relationship between hits.
An error can be quoted, copied from another system, or reported without independently verified execution.
Message roles and phases do not authenticate authorship.

## Citations and cache

Evidence hits provide `message`, `phase`, `message_heading_line`, and `locator_method: rendered_message_v1`.
Text output includes the export heading-line locator for reading surrounding source context.
Evidence excerpt lines also carry `L<number>:` prefixes for direct citation.
These prefixes are display annotations rather than source text.
An excerpt cut within a line marks that displayed line as `(fragment)`.
Use complete source lines when a task requires exact line citations.
`source_quote_start` and `source_quote_end` locate the exact quote in the decoded Markdown export.
Offsets count Unicode characters rather than bytes.
Decode source bytes as UTF-8 without newline normalization when applying these offsets.
The source hash binds the export bytes.
The existing `quote_start` and `quote_end` remain offsets inside the raw message body.

These are raw message locators, not the cleaned section numbers used by handoff requirements.
Do not copy an evidence message number into a `--section` pin.
Inspect the cleaned dialogue view before creating that kind of anchor.

Headings inside code fences do not create new message boundaries.
Export text can still contain forged headings or wrappers; these locators are not an authentication boundary.
Evidence quotes stay contiguous and are checked against the current source during retrieval.

Dialogue and evidence use separate private SQLite caches.
Project selectors also keep their existing separate caches and exact metadata scope.
Rebuild the selected view explicitly:

```sh
agent-sessions index --view evidence --rebuild --project /workspace/example
```

Rebuilding changes derived search state rather than original exports.
The evidence cache contains private code and output as well as prose.

## Synthetic comparison

Run:

```sh
python3 -m examples.snippet_matching_evaluation
```

Eight authored cases contain earlier code, repeated code, later-only code, user-supplied code, formatting changes, variable changes, and prose-only mentions.
Literal message scanning and evidence search find the same number of keyword-bearing messages in every case.
The dialogue view misses fenced code and tracebacks; it finds only the prose mention in this exercise.

A small optional experiment filters earlier assistant code by the statement shown in a narrow Python traceback shape.
AST comparison tolerates the tested whitespace change without executing code.
Its candidate sets match all eight authored references, and repeated matching snippets remain ambiguous.
The simpler earlier-message literal filter matches six of those references; formatting and prose mentions explain its two differences.

This demonstrates candidate filtering rather than execution attribution or semantic equivalence.
The helper is an experiment, not a production failure matcher.
It does not establish less reading time, better diagnosis, general accuracy, demand, or an exclusive capability.
Ordinary literal search remains a strong baseline now that code is available through the evidence view.

The practical correction is searchable evidence with explicit source coordinates.
Do not build a matching service until a receiving-assistant comparison shows that it improves the investigation workflow.
## Failure recovery

These rules apply to both dialogue and evidence search.

| Failure | Recovery boundary |
|---|---|
| More than 32 query terms or 2,000 query characters | Shorten the query; validation runs before source refresh |
| Export is not valid UTF-8 | Restore or re-export the named source; rebuilding the cache cannot repair it |
| Export cannot be read | Restore access or re-export the named source; the error identifies its filename and error class |
| Damaged derived search cache | Use explicit `index --rebuild` with the same view and project selectors |

Failed source refreshes return no evidence and roll back cache changes.
An error is not a completed search with zero matches.
Synthetic CLI checks confirmed invalid-source rollback and explicit damaged-cache recovery without source changes.
Permission failure coverage uses fault injection rather than operating-system permission certification.


## Parsed tool-record availability

New exports add `parsed_tool_records` to each session's JSON metadata.
Markdown headers also show the parsed call and result counts, including records with nonempty string IDs.
Evidence-search JSON includes these counts per hit; text output describes each source once.
For example, an authored call-only export reports one parsed call without an ID and zero parsed results.
This makes an evidence limit visible without counting records by hand.

These are export-metadata counts of parser output.
They do not establish complete source coverage, command execution, successful checks, or a unique call/result pair.
Unsupported input records can still be missing from a parser's output.
Equal call and result counts can describe different IDs or ambiguous repeated IDs.
A completed hook name also does not establish that a nested application check succeeded.

Legacy exports and invalid count metadata report `null` in evidence-search JSON and unavailable counts in text.
They are not treated as zero-result histories.
Normal dialogue search remains unchanged.
Re-exporting with this version adds the metadata; existing private exports are not rewritten automatically.
