# Review trigger evaluation

Run date: October 25, 2026. These results describe the unreleased local implementation.
The inputs contain invented conversations only.
No model, private archive, or external service participated.

## Reproduce

From the repository root, run:

```sh
python3 -m examples.evaluate_review_burden
```

The script creates temporary exports and removes them after the run.
Each case starts with the same pinned restriction and one new conversation.
Both modes use the same cases, query, evidence, and character budgets.
The scoped mode includes explicit Codex and Cursor project metadata.

Labels in [the fixture](../tests/fixtures/review_burden_cases.json) state the author's intended interpretation and rationale.
They are not independent expert judgments or a representative sample of conversation updates.
The question case deliberately requires review of a proposed change without treating that change as accepted.

## Observed results

| Outcome | Unscoped | Scoped |
|---|---:|---:|
| Intended challenges detected | 4 / 9 | 4 / 9 |
| Intended challenges missed | 5 / 9 | 5 / 9 |
| Nonchallenges that triggered review | 2 / 8 | 1 / 8 |
| Nonchallenges that stayed quiet | 6 / 8 | 7 / 8 |

The scanner detected explicit quoted replacement, correction, supersession, and conflict statements.
It missed a plain reversal, a paraphrased target, capitalization changes, a Persian reversal, and a proposed change phrased as a question.
All five missed cases produced a ready pack despite the scenario's intended challenge.

Project scoping excluded an unrelated project's correction with identical wording.
It did not fix the other misses or the remaining unnecessary review.
A fictional correction in ordinary prose still triggered review despite an introductory sentence identifying it as an example.
Fenced and blockquoted examples stayed quiet because conversation cleaning excludes them.

## Product implication

`ready` establishes the implemented coverage, budget, and recognized-review gates only.
It does not establish that no contradictory instruction exists.
The bounded English scanner is insufficient as a general contradiction detector.
These results do not establish real-world detection rates, review time, reduced rework, or willingness to pay.

## Explicit operator intervention

The script also runs an `operator_assisted` arm against the same labels.
For each scoped miss labeled as a challenge, it adds an exact operator link.
The labels select these interventions automatically in the experiment.
This is an oracle control, not an independent user study or automatic detection improvement.

Five explicit links make all nine intended challenges require review.
The remaining fictional prose example still triggers an unnecessary review.
Both original scanner arms retain their five misses.
The output reports the five interventions separately from automatic results.
It does not measure discovery effort, reading time, review time, or whether users find the missed passages.

Explicit links provide a way to retain known challenges that the scanner misses.
They do not solve discovery of unknown challenges.

The next product work must address this gap before broader reliability claims:

1. Show which changed conversations received only the bounded pattern scan.
2. Evaluate the implemented exact operator links without requiring recognized relationship wording.
3. Check that both passages and the operator's reasoning remain visible without inferring authority or adoption.
4. Measure whether this workflow reduces missed challenges without excessive review work.

Keep these labels stable during comparison runs.
Report changed labels separately instead of presenting them as detection improvements.
Do not add phrase rules solely to increase this small fixture's score.
