# Receiving-assistant investigation comparison

Run date: October 26, 2026. All records and labels are authored synthetic data.
Two fresh assistants investigated the same 28,545-character archive using different search drivers.
Neither reader received parent conversation, reference labels, or access to the other arm.
Both inherited parent model defaults; the exact model build and runtime settings were unavailable.

## Task and controls

The archive contains two target conversations and eight tutorial distractors.
One target supplied a corrected snippet before a later report displayed the older line.
The other target supplied the same snippet twice before a reported error.
Each target also contains an unverified assistant completion claim and a captured verification timeout.
The current request authorizes analysis only, despite a historical publication request.

Both drivers could read the same numbered source context.
The literal driver used `rg -n -F` over exports.
The evidence driver used the existing evidence search API with JSON output and optional role filtering.
The four scoring checks and accepted supporting source lines were defined before reader responses.
The driver recorded successful and failed requests and output character counts.
Setup checks were kept in separate logs and excluded from reader counts.

## Observations

| Arm | Supported checks | Recorded driver calls | Failed driver calls | Recorded output characters |
|---|---:|---:|---:|---:|
| Literal search and numbered context | 4 / 4 | 8 | 0 | 16,413 |
| Evidence search JSON and numbered context | 4 / 4 | 10 | 0 | 53,683 |

Both answers distinguished earlier-version execution reports from the latest supplied version.
Both preserved ambiguity between repeated prior snippets.
Both rejected the completion claim as insufficient evidence of a fix and retained current read-only authorization.
The scorer requires supporting source lines for the version, ambiguity, and failed-verification conclusions.
The authorization check compares the response with the explicitly supplied current request.

This run showed no investigation-quality advantage for the evidence JSON driver.
Its recorded output was larger, and it used more driver requests.
The first evidence query matched no full token; later queries found the named incidents.
The literal reader used exact phrase matches and contextual reads.
These are observed strategies in one run, not a general ranking of the tools.

## Limits and decision

This is one fixed archive and one reader per arm.
Driver logs cover only calls through the supplied interface, not every agent action, internal reasoning, or elapsed time.
The drivers were instructions rather than an OS-level isolation boundary.
The evidence driver emitted full JSON; the product's ordinary text renderer was not tested here.
The fixture does not measure real bug diagnosis, actual execution, human effort, production recovery, or willingness to pay.

Evidence search remains useful for inspectable raw-source retrieval.
This comparison does not justify a production failure matcher or a claim that it reduces investigation work.
Before adding machinery, inspect the smallest useful interaction and its output volume against the existing literal-search baseline.
Keep a separate holdout if changing presentation or selection after observing this fixture.

## Reproduce

```sh
python3 -m examples.investigation_reader_evaluation prepare /path/to/new-private-exercise
```

Give each fresh reader only its arm's `request.txt` and driver command.
Keep the reference and sibling arm hidden.
The readers save their JSON responses as `literal/answer.json` and `evidence/answer.json`.

```sh
python3 -m examples.investigation_reader_evaluation score /path/to/private-exercise
```

The script launches no model and reads no private source.
It uses existing ripgrep for the literal driver and the package's local search API for the evidence driver.
