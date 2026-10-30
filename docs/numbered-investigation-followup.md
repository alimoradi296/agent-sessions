# Numbered evidence follow-up

Run date: October 26, 2026. All records are authored synthetic data.
This follow-up reuses the cases from [the text holdout](investigation-text-holdout.md).
It is a clarified development experiment, not a new independent holdout.
Original requests, raw scores, and protocol reviews remain separate.

## Changes before the new readers

Both requests explicitly restrict source attribution to prior Assistant code in the same conversation.
User-pasted code does not establish that the Assistant supplied it.
The rule is an exercise boundary, not authentication of exported role headings.

Evidence text now labels excerpt lines with export line numbers.
Partial first or last lines carry a fragment marker, rather than appearing as complete source lines.
JSON retains the exact quote and source character offsets.
The request clarifies that display prefixes are not part of cited source text.

Two new fresh assistants received the separate requests without parent context or reference labels.
Both inherited parent model defaults; the exact model build and runtime settings were unavailable.
Supporting lines, conclusions, and setup checks were fixed before their responses.
Setup observations are excluded from the driver counts below.

## Observed results

| Arm | Supported checks | Recorded calls | Recorded output characters |
|---|---:|---:|---:|
| Literal search and context | 4 / 4 | 8 | 30,623 |
| Numbered evidence text and context | 4 / 4 | 11 | 36,568 |

Both readers identified the latest Assistant version in one case and missing Assistant-source attribution in the other.
Both kept the fix unestablished and current authorization limited to analysis.
Their source-line citations were checked against the exports.

The numbered evidence arm still used more calls and output than literal search in this run.
No investigation-effort advantage has been established.
The interface change and clarified question were tested together, so the run cannot isolate either effect.
Character counts are not tokens, cost, total model work, or elapsed time.
Driver logs do not establish every action taken by an assistant.

## Decision

Keep source line numbering as a practical citation improvement.
Do not claim that it improves overall investigation efficiency or justifies a matching service.
Additional experiments on this same fixture would be development checks rather than new holdouts.
Before adding more search features, verify that the packaged workflow works through the intended agent setup and private workspace.
Uniqueness, adoption, and willingness to pay remain unestablished.

## Reproduce

```sh
python3 -m examples.investigation_text_holdout prepare /path/to/new-private-followup --clarify-actor
```

Give separate fresh readers only their request and driver.
Keep sibling directories and reference labels hidden.
After saving their answers, score the saved reference:

```sh
python3 -m examples.investigation_text_holdout score /path/to/private-followup
```

The preparation flag marks the artifact as a clarified follow-up rather than a holdout.
