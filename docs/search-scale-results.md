# Search scale and fresh-index scans

An October 26 synthetic control exposed repeated full-table deletion scans during fresh indexing.
Skipping those scans on newly initialized caches reduced initial command time substantially on the measured workload.
Existing-cache updates retain their deletion path, content hashes, and source checks.

## Workload and measurements

Each view received 2,000 synthetic sessions with 60 initial messages per session.
Message sizes vary, and selected messages contain only fenced code or tool output.
After one message append, the Markdown exports total 124,286,289 bytes.
Dialogue parsing retains 93,998 initial passages; evidence parsing retains all 120,000 initial messages.
These different counts reflect the views' documented content boundaries.

| Complete CLI command | Dialogue before | Dialogue after | Evidence before | Evidence after |
|---|---:|---:|---:|---:|
| Fresh index and query | 53.6978 s | 4.7560 s | 72.0109 s | 2.7521 s |
| Unchanged query, first repeat | 0.5584 s | 0.5010 s | 0.5648 s | 0.5348 s |
| Unchanged query, second repeat | 0.5335 s | 0.4956 s | 0.5632 s | 0.5356 s |
| Unchanged query, third repeat | 0.5421 s | 0.5058 s | 0.5591 s | 0.5332 s |
| Query after one source append | 0.5960 s | 0.5494 s | 0.6332 s | 0.6032 s |

Each measurement includes Python startup, source refresh, search, and JSON output.
The first command starts without a search index; operating-system caches were not controlled.
The before measurements used the prior local implementation; the after measurements used the empty-cache optimization.
An initial post-change sequence gave similar results but started near the unit-test run.
The table uses a subsequent sequence after those tests completed.
These observations are not timing thresholds, randomized trials, or comparisons with another tool.
Repeated synthetic text, local storage, and fixture sizes limit generalization.
Memory use, multi-gigabyte archives, and receiving-agent usefulness were not measured.

## Cause and change

The FTS5 table stores `session_id` as an unindexed field.
Before inserting each source, the old refresh path deleted passages with that source ID.
On a fresh cache, that deletion finds nothing but scans passages inserted for previous sources.

A separate 500-source, 20,000-message profile measured 500 deletion calls taking 2.57 seconds of a 3.06-second refresh.
This profile used direct API execution and is separate from the complete-command table.
The caller now identifies caches initialized within the current operation, including explicit rebuilds.
Only those caches skip the unnecessary deletion scans.
Existing caches still delete changed-source passages before replacement.
Content hashing, transactions, scope filtering, and source-coordinate validation remain active.

## Coverage checks

The probe validates expected source-update and passage counts for every measured command.
Unchanged runs update zero sources; the appended-message run updates exactly one.
Code-only and tool-only target strings each return one hit in evidence view and none in dialogue view.
The main target remains retrievable in both views.
The full suite passed 306 tests after the change, including cache rebuild, source drift, deletion, and rollback checks.

## Reproduce

Run each view separately to avoid competing benchmark processes:

```sh
python3 -m examples.evaluate_retrieval --scale --sources 2000 --messages 60 --mixed-sizes --view dialogue
python3 -m examples.evaluate_retrieval --scale --sources 2000 --messages 60 --mixed-sizes --view evidence
```

The probe creates temporary synthetic exports and removes them after each run.
These commands measure the current implementation rather than reconstructing the historical before timings.

## Bulk mutations against an existing cache

A follow-up starts with 1,000 synthetic sessions and 40,000 initial messages in each view.
The baseline control appends one message before the bulk cases begin.
At that point, the source exports total 41,460,489 bytes.
The cases then add 400 sources, append a qualification to 400 original sources, and remove the 400 added sources.

| Mutation | Dialogue before | Dialogue after | Evidence before | Evidence after |
|---|---:|---:|---:|---:|
| Add 400 sources | 8.2341 s | 0.9590 s | 11.4118 s | 0.6951 s |
| Replace 400 changed sources | 9.7892 s | 1.0690 s | 13.9407 s | 0.8661 s |
| Remove 400 sources | 7.9940 s | 0.3760 s | 11.5202 s | 0.4369 s |

Before this change, each source mutation triggered another scan of the unindexed FTS source-ID field.
Refresh now plans changed and removed sources, then deletes their old passages in parameterized batches of at most 400 IDs.
Changed files are read again and must retain their planned content hash before insertion.
A concurrent change aborts the transaction instead of binding new text to an earlier hash.
Unchanged files still require content hashing; their contents are not buffered across the archive.
Fresh caches continue to skip deletion scans.

The probe checks source totals, passage totals, update counts, removal counts, and replacement-target hits.
Both views end with 1,000 sources; evidence view retains 40,401 messages and dialogue view retains 32,399 passages.
All 400 replacement targets remain searchable.
Regression checks cross the deletion-batch boundary and verify exactly one retained passage per constructed source.
Another check changes a source between planning and insertion and verifies cache rollback.
The full suite passes 308 tests.

Reproduce the current bulk-mutation path:

```sh
python3 -m examples.evaluate_retrieval --bulk-mutations --sources 1000 --messages 40 --mixed-sizes --batch 400 --view dialogue
python3 -m examples.evaluate_retrieval --bulk-mutations --sources 1000 --messages 40 --mixed-sizes --batch 400 --view evidence
```

These timings describe one before/after sequence on the same local machine with uncontrolled filesystem caches.
They do not establish performance across machines or superiority over another search product.

## One long session and broad queries

Another control uses one synthetic session with 20,000 initial mixed-size messages.
After the setup append, its Markdown export contains 20,654,600 bytes.
The broad query is `historical`; its result limit changes without changing the query.

| View | Limit | Matching passages | Returned | Complete CLI time | Pretty JSON characters |
|---|---:|---:|---:|---:|---:|
| Dialogue | 3 | 15,582 | 3 | 0.1925 s | 3,926 |
| Dialogue | 100 | 15,582 | 100 | 0.1997 s | 113,127 |
| Evidence | 3 | 19,998 | 3 | 0.4693 s | 4,737 |
| Evidence | 100 | 19,998 | 100 | 0.5007 s | 140,860 |

The probe verifies each returned quote against its source coordinates and checks the source hash.
This verification runs after the CLI timer stops.
Its cleaned-source validation now parses each source once rather than once per hit.
These checks establish coordinate binding, not factual accuracy, relevance, or complete task coverage.
Result limits leave additional candidates unreturned, as the reported totals show.

### Output-volume experiment

The probe also compares whitespace removal with an experimental layout that stores shared source metadata once.
The grouped layout retains every hit field and reconstructs the complete original report exactly.
It is a measurement helper, not an available CLI output format.

| View and returned count | Minified original JSON | Minified grouped experiment | Existing text output |
|---|---:|---:|---:|
| Dialogue, 3 | 3,264 | 2,681 | 2,096 |
| Dialogue, 100 | 95,684 | 61,927 | 64,926 |
| Evidence, 3 | 3,883 | 3,300 | 2,335 |
| Evidence, 100 | 117,017 | 83,260 | 69,685 |

These are character counts rather than tokens or measured understanding.
Text output presents different fields, so its smaller size is not evidence of lossless equivalence.
Grouping helps this repeated-source case; inputs with one hit per source may not benefit.
Even the grouped 100-hit evidence report remains large.
Reducing the result limit reduces displayed candidates and therefore cannot claim equivalent coverage.

[CASS already documents field projection and output budgets](https://github.com/Dicklesworthstone/coding_agent_session_search/blob/main/SKILL.md).
This experiment establishes neither an exclusive formatting capability nor a reason to expand the production search schema yet.

Reproduce the current long-session and payload controls:

```sh
python3 -m examples.evaluate_retrieval --scale --sources 1 --messages 20000 --mixed-sizes --broad-query --view dialogue
python3 -m examples.evaluate_retrieval --scale --sources 1 --messages 20000 --mixed-sizes --broad-query --view evidence
```

The observations come from one ordered local sequence with uncontrolled filesystem caches.
They do not measure memory use, a receiving model, or another search implementation.
