# Bounded long-history reader exercise

Run date: October 25, 2026. All inputs are invented.
The three reader prompts and acceptable citation variants were prepared before the readers ran.
The initial requirements attempt hit a provider usage limit.
A later fresh-agent retry completed on the unchanged prepared prompt and reference.
The original failure and partial results remain preserved alongside the completed result.

## Reproduce preparation

From the repository root, run:

```sh
python3 -m examples.long_history_evaluation prepare \
  --output /path/to/new-private-exercise --max-prompt-chars 5000
```

The script starts no model and reads no private history.
The output directory must not exist.
It creates 21 synthetic sources totaling 62,875 export characters in this run.
Critical paragraphs occur inside long sections alongside unrelated design text.
A query-matching source also mentions approval for an explicitly unrelated example ledger.
The target remains the example cache.

All three complete prompts, including shared questions and instructions, must fit a 5,000-character ceiling.
The script rejects preparation if any prompt exceeds that limit.
This is a common ceiling, not equal-length or token-matched input.
Although the source archive is long, the receiving prompts remain short after selection.

## Selection policies

| Presentation | Policy | Complete prompt characters |
|---|---|---:|
| Query-selected | Existing literal-query handoff, up to three sources, 1,000 excerpt characters per source | 4,924 |
| Requirements | Same query and excerpt limit, with three author-chosen paragraph requirements | 3,678 |
| Manual | Author-selected complete critical paragraphs with source coordinates | 1,851 |

Both requirements and manual selection use the known reference.
This is a best-case operator control, not a measurement of constraint discovery.
Requirement paragraphs retain complete-section hash binding, while the displayed text omits other paragraphs.
The manual control preserves the same critical statements without the automated gates or audit workflow.
The sources cannot fit in full under this ceiling, so this experiment does not include an all-source reader.
It also does not test adaptive recall or Qarinah's full-recall workflow.

## Completed results

| Presentation | Reader status | Supported answers | Correct abstentions | Unsupported answers |
|---|---|---:|---:|---:|
| Query-selected | Completed | 2 / 5 | 3 | 0 |
| Requirements | Completed on fresh retry | 5 / 5 | 0 | 0 |
| Manual | Completed | 5 / 5 | 0 | 0 |

Three fresh agents received separate prompts using `fork_turns: none` and inherited parent defaults.
Reference answers and parent conversation were not supplied.
Exact underlying model builds were not exposed by the collaboration interface.
The prompts prohibited tools, file changes, and service contact.
Only final responses were collected, without an independent tool-use trace.
Assignment order was fixed, with one successful observation per presentation.
The requirements presentation had two attempts because the first returned no answer.
The retry occurred after the other readers completed and used another fresh agent without their answers.
Timing was not measured.

The query-selected reader correctly abstained on scope, timing, and manual exclusions.
It did not mistake the unrelated ledger's approval for permission to implement the cache.
The manual reader supported all five answers from the supplied evidence.
The requirements retry also supported all five answers with exact citations accepted by the predeclared reference.
The failed initial attempt produced no score and remains separate from that successful reader response.

The reference declared both unchecked-results citation variants before the run:
`All extracted claims are not checked.` and `None independently checked by this command.`
No post hoc citation adjustment was required for any completed reader.
The previous exercise's reference and raw scores remain unchanged.

## Consequence

A carefully selected manual handoff remains a strong, shorter baseline.
The requirements presentation matched that manual baseline, with a longer prompt.
This run establishes no advantage over careful manual selection on this archive.
Discovery effort, ongoing review cost, human usability, and willingness to pay remain unmeasured.
The [maintenance replay](maintenance-evaluation.md) adds changed-source checks against simple hash baselines.
Compare adaptive recall and actual human maintenance effort before drawing broader product conclusions.
