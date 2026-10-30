# Fresh-session evidence exercise

This exercise compares query-selected context, a requirements pack, and all original sources over the same invented conversations.
It measures evidence-supported answers to five fixed questions.
It does not measure general model understanding, engineering task completion, or commercial demand.

[One actual three-session run](fresh-session-results.md) is now recorded, including raw scores and post hoc citation review.
The requirements and full-source readers each supported all five answers after that review.
The query-selected reader supported two answers and correctly abstained on three omitted details.
Full-source reading remained shorter for this tiny history.

## Prepare

After package installation, run:

```bash
python examples/continuation_evaluation.py prepare --output /path/to/new-private-evaluation
```

The output directory must not exist.
The script creates synthetic exports, requirements, three prompts, and a reference file.
It reads no real agent history and calls no model provider.

The `baseline` arm uses `context --format handoff` selection.
The `required` arm pins scope, an unresolved question, and a timing qualification.
The `full_source` arm supplies every original synthetic export without selection or claim grouping.
All prompts use identical questions and read-only instructions.
They differ in evidence presentation and length.
This is not a token-matched experiment.
The preparation records evidence and complete prompt character counts for every arm.

The full-source arm is a stronger baseline than intentionally limited query selection.
It tests whether direct reading is sufficient when the source history fits comfortably in context.
It is not a human-authored manual handoff or a comparison against another tool.

## Run separate sessions

Give `baseline-prompt.md` to one fresh session.
Give `required-prompt.md` to another fresh session.
Give `full_source-prompt.md` to a third fresh session.
Do not provide `reference.json`, earlier conversation history, or another arm's answer.
Use the same model, settings, and tool restrictions for all sessions.
Record the actual settings and any deviation from this procedure.

The prompts prohibit tools, file changes, and service contact.
They request five categorical answers with verbatim supporting quotes.
An answer can abstain when the supplied evidence does not establish the requested detail.

Save the returned JSON objects as separate answer files.
The preparation script does not launch sessions or establish that any session ran.

## Score

```bash
python examples/continuation_evaluation.py score /path/to/private-evaluation \
  --baseline-answer /path/to/baseline-answer.json \
  --required-answer /path/to/required-answer.json \
  --full-source-answer /path/to/full-source-answer.json \
  --model-label "actual model and settings"
```

The scorer checks the prepared prompt hashes before assessment.
It reports supported answers, abstentions, and unsupported answers separately.
A correct guess without the required evidence does not count as supported.
A transcript claim that says “verified” cannot establish an independently checked result.
The optional `--full-source-answer` adds the stronger baseline to the score report.
Without it, the report explicitly states that the full-source baseline was omitted.

## Preparation overhead observed

One local preparation on October 25, 2026 produced these evidence sizes:

| Arm | Evidence characters | Complete prompt characters |
|---|---:|---:|
| Query-selected handoff | 2,740 | 4,187 |
| Requirements pack before evidence-only rendering | 4,551 | 5,998 |
| Requirements pack after evidence-only rendering | 2,307 | 3,754 |
| All original synthetic sources | 838 | 2,285 |

These counts depend partly on temporary source path lengths and can change after formatting updates.
The revised pack uses the same unchanged synthetic sources and source path lengths.
It removes duplicate claim summaries and empty classification groups while retaining evidence, citations, review notes, and gates.
No receiving model or human participant ran in this measurement.
For this tiny history, the requirements pack contains substantially more text than the full sources.
This does not establish worse understanding, but it contradicts any assumption that the pack always reduces context size.
The requirements workflow must justify its maintenance effort through measured continuation outcomes.
Do not recommend it solely to shorten an already small source history.

Exact-quote scoring is stricter than semantic assessment.
The unit tests use scripted answers to assess the scorer, not to claim model performance.
Results from one exercise do not establish statistical significance or product superiority.
Private archive studies require separate reference review and must keep their inputs and results outside public repositories.

[The reader pilot protocol](reader-pilot.md) describes human participation, setup steps, timing, and commercial feedback.
