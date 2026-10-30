# Automatic evidence selection evaluation

Run date: October 25, 2026. All sources and relevance labels are authored synthetic cases.
No manual requirement pins were created for this evaluation.
No private transcript was given to the fresh reviewer.

## Rule-only nomination

From the repository root, run:

```sh
python3 -m examples.evaluate_suggestions
```

The fixture contains eleven sources, with seven intended relevant paragraphs and four distractors.
One relevant source uses a paraphrase, one uses Persian, and one exceeds the default paragraph limit.
The distractors include another feature, another project, a plain design description, and a claimed test result.
One labeled paragraph occurs per source, so source and paragraph nomination counts agree in this fixture.

| Rule-only result | Before qualification cues | After qualification cues |
|---|---:|---:|
| Relevant paragraphs proposed | 3 / 7 | 4 / 7 |
| Relevant paragraphs absent from proposals | 4 / 7 | 3 / 7 |
| Irrelevant paragraphs proposed | 1 / 4 | 1 / 4 |
| Oversized omissions with source locators | 0 / 1 | 1 / 1 |

The added cues recognize explicit qualifications such as a proposed target, unapproved release, or undeployed state.
This is a measured change on an authored development fixture, not an independent generalization result.
The selector still misses the paraphrase and Persian wording.
The oversized paragraph remains omitted, with an exact source, section, line range, character count, and source hashes for follow-up.
An unrelated feature inside the same metadata scope still becomes a false proposal.
Every proposal report remains unaccepted, with `ready: false` and no claim of complete discovery.

## Fresh assistant review

One fresh agent received all eleven synthetic records, their project metadata, the target topic, and selection criteria.
It did not receive relevance labels, previous conversation, rule results, or reference answers.
It was instructed to load one synthetic task file, then return JSON without further tools or actions.
No independent tool-use trace was collected.
It used inherited parent defaults, with no exact underlying model build exposed by the collaboration interface.

The task requested source IDs, verbatim supporting quotes, unresolved-conflict status, and current authorization.
It excluded ordinary design text, reported test results, other features, and other projects from the intended selection.
The agent selected all seven intended sources and none of the four distractors.
Every returned quote occurred verbatim in its cited source.
It marked conflicting permissions unresolved and current authorization as read-only.

This was one fixed-order observation against author labels.
It was not a token-matched comparison: the reviewer received full source records, including the oversized paragraph.
The rule-only output deliberately excludes that paragraph under its character limit.
Reading cost, latency, discovery on real private archives, and commercial value were not measured.
This tests a calling assistant's review, not a built-in semantic model in the package.

## Consequence

Assistant review can handle nomination work in this exercise without asking the user to select paragraphs.
Source IDs and short quotes are not sufficient to certify a ready handoff.
The oversized source still needs complete-paragraph expansion and budget checks before any retention claim.
Conflicting permissions remain unresolved rather than becoming replacement instructions.
[Validated transfer is now implemented](assistant-selection-import.md), with stale-source, exact-quote, ambiguity, full-paragraph, and review-gate checks.
The existing reviewer response imported seven anchors, while unresolved conflicts correctly kept the resulting bundle in draft state.
Keep model interpretation separate from source retention, current authorization, and factual verification.
