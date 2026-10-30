# Text-output investigation holdout

Run date: October 26, 2026. All records are authored synthetic data.
The fixture differs from [the first investigation comparison](investigation-reader-results.md).
It changes the identifiers, supplied versions, source roles, and verification result.
One current version matches a captured failing line; another matching earlier snippet appears under User rather than Assistant.
A queued-work response replaces the earlier timeout.

The evidence driver uses the product's ordinary text renderer, with an added export heading-line locator.
The literal driver still uses `rg -n -F`.
Both drivers provide the same numbered context reader.
Gold source lines and expected labels were saved before either fresh reader responded.
Setup checks are separate from observation logs.

## Raw observations

| Arm | Original scorer result | Recorded driver calls | Recorded output characters |
|---|---:|---:|---:|
| Literal search | 3 / 4 | 13 | 23,441 |
| Evidence text | 4 / 4 | 10 | 38,167 |

These raw scores are preserved rather than rewritten after inspection.
They do not establish an accuracy advantage because the question contains an attribution ambiguity.
Both readers supported the three unambiguous checks: current version, unestablished fix, and current read-only authorization.

## Protocol ambiguity

The question asks whether the earlier source is unique or ambiguous, without saying it must be assistant-supplied.
The expected label nevertheless assumes assistant origin.
The literal reader cites the User heading and matching earlier snippet, then answers `earlier_version`.
The evidence reader cites the same User origin and answers `unattributed` for assistant-origin attribution.
It also explicitly identifies the wording ambiguity in its report.

Both interpretations fit the supplied question.
The source-attribution item therefore cannot support an accuracy ranking.
A separate post-response protocol review records this finding; the original response files and scores remain unchanged.
Future actor-attribution questions must name the actor before the run starts.

## Decision and limits

The text arm used fewer recorded calls but more output characters than literal search in this run.
Its workload and fixture differ from the earlier JSON run, so those output totals are not a controlled format-only comparison.
No reduction in diagnosis time, total model work, human effort, or cost has been established.
Neither driver is an OS sandbox or a complete activity audit.
The exact model build and runtime settings were unavailable; both fresh readers inherited parent defaults.

Keep the useful heading-line locator and exact-source evidence search.
Do not add a matching service or claim a product advantage from these results.
Prioritize a small investigation workflow with explicit actor and execution-evidence boundaries before expanding the interface.
General reliability, adoption, willingness to pay, and exclusivity remain unproven.

## Reproduce

```sh
python3 -m examples.investigation_text_holdout prepare /path/to/new-private-holdout
```

Give each fresh reader only its arm's request and driver.
Keep the reference and sibling arm hidden.
After both answers are saved:

```sh
python3 -m examples.investigation_text_holdout score /path/to/private-holdout
```

This intentionally preserves the original ambiguous protocol for auditability.
Treat a clarified future protocol as a separate experiment.
