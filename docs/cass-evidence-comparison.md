# Native evidence comparison with CASS

Run date: October 26, 2026. Inputs were two authored synthetic fixtures, not private transcripts.
The comparison used the released Linux amd64 [CASS v0.10.0](https://github.com/Dicklesworthstone/coding_agent_session_search/releases/tag/v0.10.0) binary.
Its release revision is `2bfe708d35734656f0d34eab112bf051e354519c`.
The downloaded archive matched its published checksum:

```text
638ea8a8a9023c2e046bf8868392e6191218b89cf006e81af3ca205b546c4681
```

The [reproducer](../examples/compare_cass_importer.py) additionally checks the extracted binary hash before execution.
It downloads nothing and rejects another binary before creating output.
It supplies a new home, configuration roots, data directory, and minimal environment to every CASS subprocess.
No provider credentials or real history paths are supplied.
Indexing and lexical searches use the actual CLI rather than mocked storage.

## Input and result

The Codex JSONL fixture contains a request, analysis, both tool-call families, paired outputs, a correction, and a final answer.
The Cursor agent-transcript JSONL fixture contains prose, a structured tool invocation, and a structured result with an explicit error flag.
Long payloads contain distinct head and tail markers.
Neither tool executes the commands represented by these records.

CASS discovered both fixtures and indexed two conversations containing ten canonical messages.
Searches completed without reported timeouts.
The comparison counts literal markers within returned `content`, excluding title-only matches.

| Authored markers | CASS indexed content | Our evidence search |
|---|---:|---:|
| Codex request, analysis, correction, final | 4 / 4 | 4 / 4 |
| Codex function/custom arguments and results, head and tail | 8 / 8 | 8 / 8 |
| Cursor request and prose answer | 2 / 2 | 2 / 2 |
| Cursor structured tool arguments and result, head and tail | 0 / 4 | 4 / 4 |

The selected canonical Cursor answer showed the tool name but not the argument marker.
CASS physical-file viewing retrieved the argument and result from their original JSONL lines.
Therefore, this is a searchable-projection gap in the tested release and fixture, rather than proof of irrecoverable archive loss.
The raw-view fallback is part of the baseline, not an absent capability.
Search message ordinals and physical file lines are different coordinate spaces; the probe uses each command's documented option.

These marker counts are not semantic accuracy scores or exhaustive format coverage.
The runtime release differs from the separately inspected main revision `20258bd2fa653fb433e841e4cc2c2cfbf088ad35`.
Current-main runtime behavior, other Cursor storage formats, task-level recovery effort, and commercial value remain unestablished.
Source fixture bytes were unchanged after both tools ran.

## Pinned main-source check and stronger fallback

The inspected CASS main revision pins `franken-agent-detection` at `6b337ba434b72c65c6c5a748b7ec47885f840ac0`.
Its [Cursor record conversion](https://github.com/Dicklesworthstone/franken_agent_detection/blob/6b337ba434b72c65c6c5a748b7ec47885f840ac0/src/connectors/cursor.rs#L1146) creates text and structured invocation fields separately.
The [shared text helper](https://github.com/Dicklesworthstone/franken_agent_detection/blob/6b337ba434b72c65c6c5a748b7ec47885f840ac0/src/connectors/utils.rs#L526) renders selected tool descriptions rather than arbitrary arguments and generic result blocks.
The invocation helper clones the full input, so arguments are not simply discarded from the normalized representation.
This source inspection does not establish how every current indexing or retrieval surface uses those fields.
The current main binary was not built or executed.

The reproducer now includes a stronger release baseline.
It scans only the authorized synthetic home for the exact result marker, obtaining a path and physical line without a supplied filename.
CASS physical viewing with one surrounding line then returns the argument, result, and explicit error flag.
Source bytes remain unchanged.
This is deterministic literal recovery, not another model observation or a measured effort comparison.

Therefore, the initial indexed-content gap does not establish an exclusive recovery task.
Keep the corrected export flag, but do not build another adapter or search engine from this result alone.

## Defect corrected here

The comparison also exposed an omission in this repository.
Our Cursor parser retained `is_error: true`, but Markdown rendering omitted the field.
Tool-result headers now preserve explicit boolean error flags.
Missing or non-boolean flags do not become a success or failure assertion.
The cleaned dialogue view still excludes this tool metadata; the raw evidence view retains it.
The flag records source-reported status rather than independent verification.

The reproducible runtime probe completed after that correction, and the full suite passed 312 tests.
Unit checks cover the exported flags, cleaned-view separation, synthetic fixture preservation, and rejection of an unpinned binary.
The unit suite does not require CASS or download a release.

## Reproduce

Obtain and checksum-verify the pinned release outside this checkout, then run:

```sh
python3 -m examples.compare_cass_importer --binary /path/to/cass \
  --output /path/to/new-private-comparison
```

The output directory must be new and outside Git checkouts.
It contains only synthetic fixtures, local indexes, command outputs, and the comparison report.
This run supports a narrow evidence-preservation observation, not a universal capability ranking.
