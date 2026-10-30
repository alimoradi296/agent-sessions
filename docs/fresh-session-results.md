# Three fresh AI reader sessions

Run date: October 25, 2026. This exercise used invented conversations only.
Three actual AI agents ran with `fork_turns: none` after explicit user authorization.
Each received one prepared prompt, without the parent conversation, reference answers, or another reader's response.
No model or reasoning override was requested.
The collaboration interface did not expose the exact underlying model build or settings.

## Inputs and procedure

The [evidence exercise](continuation-evaluation.md) supplied three presentations of the same small history:

- Query-selected context omitted scope, a timing qualification, and an open question.
- The requirements pack retained those three explicitly pinned details.
- The full-source presentation retained every original source without selection.

Each reader answered the same five categorical questions and supplied exact supporting quotes.
Every prompt prohibited tools, file changes, and service contact.
Only final answer messages were collected, without an independent tool-use trace.
Prepared prompt hashes were checked before the run and again during scoring.
Prompt text was copied into the task messages without a separate transport-level hash receipt.
Assignment order was fixed, with one observation per presentation.
Elapsed reading time and human setup effort were not measured.

## Results

| Presentation | Canonical quote matches | Correct abstentions | Valid alternative citations | Supported answers after citation review |
|---|---:|---:|---:|---:|
| Query-selected | 1 | 3 | 1 | 2 / 5 |
| Requirements pack | 4 | 0 | 1 | 5 / 5 |
| Full original sources | 5 | 0 | 0 | 5 / 5 |

The query-selected reader abstained on historical scope, timing, and manual exclusions because its input did not establish those details.
It correctly identified that results were not independently checked and that the current evaluation authorized reading only.
Both other readers answered all five questions with supporting evidence after citation review.
No unsupported conclusion remained after that review.

### Scoring qualification

The unchanged exact-quote scorer rejected two valid citations for the unchecked-results answer.
Its canonical reference was `All extracted claims are not checked.`
The query and requirements readers instead cited supplied text containing `None independently checked by this command.`
Both citations support the same answer and occur verbatim in the respective prompts.

Raw scores were preserved before review: one, four, and five canonical matches respectively.
The parent assistant accepted the two alternative citations after seeing all responses.
That review was post hoc, unblinded, and not an independent human assessment.
The table keeps the original canonical counts visible alongside the reviewed support counts.
The prepared reference, responses, raw scores, and review notes remained in the local temporary evaluation directory.

## Interpretation

Required evidence survived this query-selection omission and remained usable by one fresh reader.
The full-source reader achieved the same reviewed answer support with a shorter prompt:

| Presentation | Evidence characters | Complete prompt characters |
|---|---:|---:|
| Query-selected | 2,740 | 4,187 |
| Requirements pack | 2,307 | 3,754 |
| Full original sources | 838 | 2,285 |

This does not establish an advantage over full-source reading for small histories.
The query-selected reader's correct abstentions are not invented answers or unsafe actions.
The requirements were selected in advance by the exercise author, and their discovery and maintenance cost remains unmeasured.
One tiny exercise does not establish general understanding, successful engineering continuation, statistical significance, or willingness to pay.
No human reader or paying user participated.

## Roadmap consequence

Keep full-source reading as the baseline for histories that fit comfortably in context.
The next continuation experiment needs longer histories, realistic competing topics, later corrections, and matched character limits.
Include the nearest alternative's full-recall workflow, whose [source recovery already passed the pinned probe](context-selection-probe.md#qarinah-full-recall-counterexample).
Predeclare acceptable citation alternatives before the next run and preserve raw responses.
Measure requirement-selection effort separately from reader answer quality.
Actual repeated use and pricing feedback remain separate product gates.

[The bounded long-history exercise](long-history-results.md) now has three completed readers after a provider-limited retry.
Requirements and the strong manual baseline each supported all five answers under citation rules declared before the run.
