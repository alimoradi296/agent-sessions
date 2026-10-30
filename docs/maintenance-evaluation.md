# Maintenance signal comparison

Run date: October 25, 2026. All inputs and labels are authored synthetic controls.
No human inspected these updates, and no time or commercial feedback was measured.

## Reproduce

From the repository root, run:

```sh
python3 -m examples.evaluate_maintenance
```

Each case starts with a current pinned restriction, an unrelated source, and a saved ready handoff.
Scripted source inspection notes establish an empty queue at the initial checkpoint.
Those notes do not represent real human inspection.
The script then applies one update and compares three software signals:

1. Changes to the manual handoff's cited source bytes or agent/project metadata.
2. Changes to any indexed source bytes or agent/project metadata.
3. Findings from the tool's bounded handoff audit.

The first two are simple local checkpoints, not semantic detectors or complete manual workflows.
The comparison does not use an unchecked, forgotten manual note as its only baseline.

## Observed signals

The six cases contain four intended review needs and two unrelated updates.
The intended review needs are an explicit quoted challenge, a paraphrased reversal, an edited qualification, and changed agent identity.
The unrelated updates append separate naming discussions to cited or uncited sources.

| Signal | Intended review needs flagged | Missed review needs | Unrelated updates flagged |
|---|---:|---:|---:|
| Cited-source checkpoint | 2 / 4 | 2 / 4 | 1 / 2 |
| Whole-archive checkpoint | 4 / 4 | 0 / 4 | 2 / 2 |
| Bounded handoff audit | 3 / 4 | 1 / 4 | 0 / 2 |

The bounded audit ignored both unrelated appends while detecting a new explicit quoted challenge outside the cited source.
The cited-source checkpoint missed that new challenge because the cited source remained unchanged.
The whole-archive checkpoint flagged every update, without interpreting its relevance.

The bounded audit missed the paraphrased reversal and the rebuilt handoff still passed readiness.
The inspection queue nevertheless showed one pending source after every update, including both unrelated updates.
Its broader warning burden therefore matched the whole-archive checkpoint in this replay.
The specialized audit's lower alert count is not evidence that the complete product eliminates review of unrelated updates.

## Product implication

The measurements expose a detection and review-burden trade-off.
They do not establish superiority over a simple archive checkpoint plus careful manual review.
The archive checkpoint detected the challenge that the bounded audit missed.
An empty audit result does not establish that a new instruction cannot contradict the handoff.

The valuable hypothesis remains selective, inspectable maintenance with less actual review effort and fewer missed constraints.
That hypothesis needs readers to compare updating a manual handoff with maintaining pins, inspection notes, and challenge reviews.
Record reading time, command attempts, missed changes, and whether the resulting handoff stays useful across repeated work.
Keep raw task evidence and individual feedback outside the public repository.
