# Imported review maintenance comparison

Run date: October 25, 2026. All inputs and relevance labels are authored synthetic controls.
This replay measures software signals, without testing a receiving agent or semantic interpretation.

Run:

```sh
python3 -m examples.evaluate_review_maintenance
```

Each case starts with a source-bound assistant-review contract and a ready handoff.
The selection response is scripted; it is not another fresh assistant observation.
An independent baseline records source bytes and agent/project metadata within the same exact project scope.

Eight updates include five intended review needs and three unrelated changes.
Review needs include new paraphrased and Persian permissions, an edited qualification, changed agent identity, and new project membership.
Unrelated changes append naming text to cited or uncited sources, or add an excluded-project source.

## Result and correction

Before correction, the imported review flagged all five intended needs and all three unrelated changes.
The scoped checkpoint flagged all five needs and two unrelated changes.
The extra review alert came from hashing the complete index, including excluded projects.

New review packets now bind review-visible identities and membership through a scoped metadata hash.
Source bytes remain bound separately, including unselected sources within the project.
Packet import, handoff compilation, and audit use the same boundary.
Existing packets and contracts retain their original freshness rules.

| Signal after correction | Intended needs flagged | Missed needs | Unrelated alerts |
|---|---:|---:|---:|
| Scoped byte and metadata checkpoint | 5 / 5 | 0 / 5 | 2 / 3 |
| Imported review freshness | 5 / 5 | 0 / 5 | 2 / 3 |

Excluded-project updates now preserve the current review and handoff readiness.
Moving a source into scope still invalidates review, even when its text is unchanged.
Changed source versions within scope still require review, including unrelated appends.
The tool does not infer which changed statements matter.

## Product implication

This correction removes an avoidable alert; it establishes no detection advantage over the simple checkpoint.
Freshness detection alone does not justify the additional workflow or a paid product claim.
The next comparison needs actual continuation and repair behavior after changed context.
Both arms should receive equivalent changed evidence and current authorization.
Measure unsupported actions, retained constraints, and total recovery work before adding more review machinery.

## Refresh text volume

An October 26 follow-up adds one known message to a synthetic session with 25 existing messages.
The script verifies that the cleaned conversation prefix remains identical.
The old review becomes stale, and preparing a new review presents all 27 paragraphs again without omissions.

| Input | Characters |
|---|---:|
| Updated full-review routing prompt and batches | 10,093 |
| Complete updated Markdown export | 6,666 |
| Scripted restriction notes, known appended message, and brief framing | 218 |

The same reproduction command now includes `refresh_volume` in its JSON result.
These are decoded character counts, rather than tokens, latency, or measured reader effort.
The notes are scripted, and the appended message is known from fixture construction.
This control does not implement incremental review or establish equivalent semantic coverage.
Edited earlier messages, deletions, changed identities, and conflicting updates require separate treatment.

[Pi's compaction reference](https://pi.dev/docs/latest/compaction) documents reusing a previous summary while summarizing a later message span.
[Its session format](https://pi.dev/docs/latest/session-format) preserves entries and branch relationships.
[Its extension API](https://pi.dev/docs/latest/extensions) supports custom context and compaction behavior.
These are documented capabilities, rather than a Pi runtime comparison performed here.
Incremental summarization alone therefore does not establish an exclusive capability for this repository.

The full-review path has substantial text overhead in this control.
Keep strict source freshness, but require evidence of better continuation before expanding this workflow.
## Append information controls

The reproduction now includes `append_information`, using authored examples without model calls.
Two histories retain identical notes: discovery-only scope and a 60-second default timeout.
They differ in an omitted profile definition: Amber means 17 seconds in one history and 43 in the other.
Both then receive the same append: use the earlier Amber profile timeout instead of the default.
The script verifies that both original cleaned prefixes remain unchanged.

The reduced notes-and-append text is identical, while the full histories support different timeout values.
Thus, that reduced text cannot determine which value the source history contains.
Source hashes would differ, but a digest does not supply the omitted definition.
Both literal lookup and the existing indexed search recover the exact definition in each history.
This is a constructed information-loss example, rather than an observed model error or general retrieval benchmark.

A direct conflicting permission statement remains visible alongside the retained restriction in another constructed input.
No model was asked to interpret or resolve that conflict.
An earlier-message edit fails the exact-prefix comparison; an append-only method cannot treat it as a verified append.

Do not replace full source review with notes-and-append reading while claiming equivalent coverage.
Use existing source retrieval when a later request depends on omitted history.
No new retrieval engine or exclusive product capability is established by these controls.

## Focused lookup boundaries

The `lookup_boundaries` control uses the existing search API on three synthetic histories:

| Case | Observation |
|---|---|
| Two different definitions | Both match; limiting output to one returns one while reporting two total hits |
| A reference to an earlier definition | The first query finds only the reference; a follow-up query retrieves the definition |
| A definition under another name | The literal query returns no matches; absence of the concept remains unestablished |

These checks measure retrieved text, rather than receiving-agent understanding or answer correctness.
The bundled continuation skill now routes specific historical questions to focused lookup first.
It requires checking limits, inspecting qualifications, and retaining uncertainty.
Full handoff review remains a separate workflow with its existing source and readiness checks.
This avoids requiring a complete review packet for every factual lookup without claiming equivalent task coverage.
