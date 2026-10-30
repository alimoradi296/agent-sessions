# Review size and reuse comparison

Batching increased total input text in all three synthetic archive sizes.
It limits individual prompt size without establishing lower total work.

| Sources | Full-source prompt characters | Batched review characters | Batches | Omitted paragraphs |
|---|---:|---:|---:|---:|
| 8 | 4,342 | 5,221 | 1 | 0 |
| 24 | 18,444 | 23,206 | 4 | 0 |
| 72 | 60,762 | 78,732 | 14 | 0 |

The batched total includes the routing prompt and every batch prompt.
The baseline includes its instructions and complete exported source text.
Both contain the same authored historical statements.
Characters are not tokens, latency, cost, or effort.

## Fresh selection comparison

Two fresh assistants reviewed the 24-source exercise, one per arm.
They received their prompts without reference labels or parent conversation.
The exact model build and runtime settings were unavailable; both inherited the parent defaults.
There were six relevant paragraphs, including conflicting historical permissions and a Persian statement.
Distractors included another feature's restrictions, design notes, and claims that checks passed.

Both readers selected all six intended paragraphs without extra or ungrounded selections.
Both retained unresolved conflicts and reported read-only authorization.
The batch response imported into six anchors and produced a 2,849-character handoff.
The handoff remained a draft because the conflicting historical statements were unresolved.

This was one fixed-order run per arm using authored relevance labels.
Prompt framing and response schemas differed, and inputs were not matched by tokens or compute.
The larger and smaller exercises measured text size only; they had no fresh reader runs.
No general accuracy advantage was shown.

## Reuse arithmetic

For unchanged sources and the same task, compare repeated full reading, saved notes, and review followed by handoff reading.
These totals exclude outputs and tool traffic from all strategies.
They assume the handoff remains suitable; they are arithmetic rather than observed repeated sessions.
The saved-notes baseline uses the full reader's actual selections, expanded into complete paragraphs with source coordinates.
The script creates these 746-character notes without using reference labels.
They lack the requirements workflow's freshness and coverage gates.

| Uses | Repeated full source | Initial full read plus saved notes | Initial review plus handoff |
|---|---:|---:|---:|
| 1 | 18,444 | 19,190 | 26,055 |
| 2 | 36,888 | 19,936 | 28,904 |
| 5 | 92,220 | 22,174 | 37,451 |
| 10 | 184,440 | 25,904 | 51,696 |

The one-use workflow costs more input text.
Saved notes cost less input text at every tested reuse count.
Reuse alone therefore does not establish an advantage for the requirements workflow.
Receiving-agent understanding and refresh work remain unmeasured here.
The draft handoff is not proof that a later agent can safely execute the task.
The remaining question is whether explicit checks prevent enough stale or unsupported continuation to justify their overhead.

## Reproduce

Prepare only synthetic archives outside Git:

```sh
python3 -m examples.review_scaling_evaluation prepare --output /path/to/private-exercise
```

Give separate fresh readers `size-24/full-prompt.txt` and the main prompt in `size-24/packet`.
Keep `reference.json` and the other arm hidden from each reader.
Save responses as `size-24/full-answer.json` and `size-24/batch-answer.json`.

```sh
python3 -m examples.review_scaling_evaluation score /path/to/private-exercise --model-label 'actual reader setup'
```

The script launches no models and reads no private archive.
This result does not establish demand, willingness to pay, or an exclusive capability.

## Exact-text compaction control, October 26

An experimental encoder stores each distinct paragraph text once and retains the original ordered source/section/paragraph structure.
References replace only the text field; roles, locators, wrapper hints, and other occurrence metadata remain separate.
The decoder must reconstruct exactly the original grouped review payload.
Text equality does not merge authority or make repeated statements independent evidence.
The default packet format is unchanged; optional integration is described below.

Each synthetic case has 240 paragraphs across 20 fictional sources.
The comparison minifies both encodings equally and includes instructions for resolving references.

| Content | Existing prompt characters | Compact characters | Characters saved |
| --- | ---:| ---:| ---:|
| Unique paragraphs | 114,649 | 116,632 | −1,983 |
| Repeated short statement | 26,439 | 24,945 | 1,494 |
| Repeated long paragraph | 211,959 | 25,718 | 186,241 |

Every case round-trips exactly.
Four regression tests check occurrence identity, roles, wrapper hints, ordering, exact case-sensitive equality, and invalid references.
Simple distinct-text-only output is smaller but omits occurrence metadata; it is not an equivalent evidence report.
The encoder itself is ordinary exact-text interning, not a new matching or summarization capability.

The benefit depends on repetition and paragraph length; unique content grows.
These are hypothetical single prompts, not evidence that they fit a receiving agent's context or improve understanding.
Independent batches need their own resolvable text references; single-prompt savings cannot be assumed for a batch workflow.
No fresh reader, token count, latency, or total review-effort measurement was performed.
Do not change the production format on these character counts alone.

Reproduce without private input or network access:

```sh
python3 -m examples.compare_review_compaction
python3 -m unittest tests.test_review_compaction
```

## Bounded self-contained batch plans

The follow-up packs the same synthetic records into prompts limited to 6,000 characters and 32 batches.
Both strategies use the same greedy packing rule and minified ordinary payload.
The adaptive candidate chooses the smaller of ordinary text and exact-text references independently for each batch.
Each compact batch includes its own dictionary, so it can be decoded without another batch.
Totals include all repeated instructions and a routing prompt.

| Content | Ordinary batches / omissions | Adaptive batches / omissions | Ordinary total characters | Adaptive total characters |
| --- | --- | --- | ---:| ---:|
| Unique | 26 / 0 | 26 / 0 | 147,873 | 147,873 |
| Short repeated | 6 / 0 | 6 / 0 | 33,249 | 32,588 |
| Long repeated | 32 / 80 | 7 / 0 | 183,037 | 39,501 |

The long-repetition totals contain different amounts of evidence: the adaptive plan retains 240 paragraphs, while ordinary packing retains 160.
Every emitted batch is decoded from its serialized JSON and compared with its original grouped evidence.
Every input occurrence is assigned once to a batch or an explicit omission; retained order is checked.
Oversized individual paragraphs remain omissions instead of being truncated.
The final strategy falls back to ordinary packing if the candidate adds omissions or increases total characters.
This is an explicit selection rule, not proof that adaptive greedy packing is always superior or optimal.
The routing protocol is experimental; it is not the production review packet generator.

Eight regression tests now cover the codec and planner, including limits and omissions.
No model reviewed these encodings, and JSON round-trip equality does not establish equal comprehension.
Preparation runtime and receiving-agent token costs remain unmeasured.

```sh
python3 -m examples.compare_review_compaction --batches
```

## Preparation and importer compatibility

The compatibility probe exports one fictional session containing 40 repeated long paragraphs.
It runs the actual packet preparation, packet reader, and answer importer.
Only the prompt renderer is temporarily replaced inside the isolated Python process.
An experimental protocol instruction enters the review identity; the two encodings produce distinct review IDs.
At this measurement stage, the renderer was confined to the probe.
This probe includes an additional protocol instruction in every experimental prompt.
The simplified planner above uses different routing and identity framing, so its totals cannot substitute for this actual-generator measurement.

| Observation | Ordinary | Experimental |
| --- | ---:| ---:|
| Retained paragraphs | 40 | 40 |
| Batches, at a 4,000-character limit | 14 | 3 |
| Routing plus batch characters | 53,845 | 11,100 |
| Median preparation seconds | 0.0066 | 0.0159 |

Each timing is the median of three runs in one Python process; strategy order alternates between repetitions.
Preparation includes source reads, rendering, hashing, and private output writes.
It excludes fixture export, answer import, model review, and process startup.
These small local measurements do not establish archive-scale performance.

Scripted answers select two separate occurrences of the same quote.
Both encodings import identical anchors, including roles, source hashes, section identity, and paragraph coordinates.
The unchanged validator rejects an answer with another review ID, a missing batch acknowledgement, an ambiguous quote, or an incorrect location.
It also rejects a modified batch and a subsequently changed source.
These controls test compatibility and corruption detection, not security against a process that can rewrite the tool and its state.
The ninth regression test exercises this actual preparation/import path.
No receiving-model comprehension or commercial advantage follows from the successful import.
Protocol overhead can outweigh small encoding savings; integration needs a complete-plan comparison with identical framing and a fallback, not the best synthetic ratio alone.

```sh
python3 -m examples.compare_review_compaction --compatibility
```

## Aligned framing and optional integration

An aligned follow-up keeps ordinary source prompts and routing unchanged.
Only compact batches receive decoding instructions; the format choice separately affects review identity.
The same 40-paragraph fixture retains all occurrences and imports identical anchors with distinct review IDs.
All six malformed/stale controls remain rejected.
Ordinary preparation uses 53,845 characters in 14 batches; the aligned prototype uses 10,920 in three.
Medians over three alternating runs were 0.0065 and 0.0168 seconds respectively, with the same timing exclusions as above.

```sh
python3 -m examples.compare_review_compaction --aligned-compatibility
```

The CLI now supports optional `--compact-review` for handoff and topic review preparation.
It prepares both complete plans privately and checks their current source snapshots and scoped metadata.
Compact input is selected only with a strictly smaller routing-plus-prompt total, no added omissions, and every ordinary-plan occurrence retained.
Otherwise the ordinary packet is copied unchanged, preserving its review ID.
Only the selected packet is published to the requested private output directory; temporary plans are removed.
The codec reconstructs and compares every serialized occurrence payload before use.
Source changes between plans fail before that output is created.

The actual CLI-to-import regression selects a late repeated occurrence using its original coordinates.
Other regressions check byte-identical fallback packets and source changes during preparation.
These establish mechanical compatibility rather than independent semantic-review quality.
Default preparation remains ordinary, and no real archive data is included in these public controls.

## Integrated archive-size controls

The complete CLI comparison uses 24 synthetic sources with 40 paragraphs each, a 6,000-character prompt limit, and at most 32 batches.
Source metadata alternates Codex and Cursor; these are rendered fixtures, not a native-importer comparison.
Each case is exported once, then each strategy runs three times in a new Python process with alternating strategy order.
The operating-system cache is not reset.

| Content | Ordinary retained / omitted | Adaptive retained / omitted | Ordinary / adaptive characters | Median CLI seconds, ordinary / adaptive |
| --- | --- | --- | --- | --- |
| Unique | 160 / 800 | 160 / 800 | 185,924 / 185,924 | 0.1921 / 0.5063 |
| Repeated | 160 / 800 | 960 / 0 | 179,404 / 140,978 | 0.1785 / 0.7710 |
| Mixed | 160 / 800 | 280 / 680 | 181,684 / 176,519 | 0.1805 / 0.5823 |

Every case has 960 input occurrences.
The repeated case contains the same long paragraph at distinct source and role locations; it does not represent 960 independent facts.
Mixed input alternates one unique paragraph with two occurrences of shared text.
The adaptive totals include both plan preparations and final selection; the unique case falls back to the identical ordinary packet.
Character totals include the routing prompt and every displayed batch, not the larger private packet JSON.

The probe decodes actual emitted prompts and checks text, role, source metadata, paragraph locators, wrapper hints, order, and retained coverage against the validated packet.
It verifies that every input occurrence is retained or explicitly omitted, and that adaptive selection retains ordinary evidence without extra omissions or total text.
Unchanged runs also produce stable review identities.
These post-command checks and initial fixture exports are excluded from the measured CLI duration.
CLI time includes process startup, source reads, source hashing, rendering, output writes, and adaptive comparison.

The mixed and unique cases remain incomplete input; passing the codec checks does not remove their omissions.
No model review, semantic-coverage score, token cost, or willingness to pay was measured.
The additional local preparation time is a measured cost, including when the result falls back.

```sh
python3 -m examples.evaluate_compact_review
```

Use `--sources`, `--messages`, `--repeats`, and `--budget` for other synthetic sizes.
The regression test uses a smaller complete CLI run and does not assert timing thresholds.

## Default-budget comparison and complete-input size

Repeating the same 24-source, 960-occurrence protocol at the default 32,000-character limit removes input omissions in every case for both strategies.
This shows that the earlier omissions depend on the configured prompt limit and batch cap.
No source scope, readiness check, or paragraph content is changed.

| Content | Ordinary / adaptive batches | Ordinary / adaptive characters | Median CLI seconds, ordinary / adaptive |
| --- | --- | --- | --- |
| Unique | 29 / 29 | 896,159 / 896,159 | 0.2753 / 1.0031 |
| Repeated | 28 / 3 | 855,248 / 95,701 | 0.2603 / 3.5644 |
| Mixed | 28 / 13 | 868,774 / 389,668 | 0.2788 / 1.4146 |

Each cell retains all 960 occurrences without omissions.
Longer compact batches increase preparation work; reduced text does not imply faster local preparation.
As before, timings are medians of three complete commands, with alternating order and no operating-system cache reset.

The unique case still presents almost 900,000 characters across its batches.
A per-prompt limit and zero omissions do not establish that the receiving agent has enough context to review all of it.
Preparation now reports `total_prompt_chars` and `largest_prompt_chars` for ordinary and compact requests.
These count actual output strings; the existing `prompt_chars` field remains the main routing prompt for compatibility.
Regression tests verify both batched and single-prompt accounting, and the scale probe compares reported counts with emitted files.
The continuation skill instructs the assistant to check these sizes before reading and not acknowledge unread batches.
Fresh-session compliance with that instruction has not been measured.
No token-fit or semantic-review result is claimed.

```sh
python3 -m examples.evaluate_compact_review --budget 32000
```

## Existing lossless-compression mechanisms

Primary-source review on October 26 found direct overlap with the compression mechanism:

| Project | Documented mechanism | Evidence boundary here |
| --- | --- | --- |
| [Context-fold](https://github.com/Joshuaakaspace/Context-fold) | Hash repeated blocks, replace them with references, and unfold with a registry | Pinned core executed below |
| [sqz](https://github.com/ojuschugh1/sqz) | Repeated-output references, original-content expansion, and local recall | Documentation reviewed; binary not run |
| [Distil](https://github.com/dshakes/distil) | Recoverable content references, agent-facing expansion, and behavioral/cost comparisons | Documentation reviewed; runtime and reported results not independently reproduced |

These sources do not establish that every transform or recovery surface is equivalent.
They do establish that deduplication with recoverable originals is an existing approach.
Do not claim exclusive compression capability or infer billed savings from smaller review text.

### Pinned Context-fold execution

Revision: `5599380548328deb54c713b149889100b4c9eabb`.
The downloaded [core](https://github.com/Joshuaakaspace/Context-fold/blob/5599380548328deb54c713b149889100b4c9eabb/src/context_fold/core.py), initializer, tokenizer wrapper, and tests were inspected before execution.
Core SHA-256: `8111071085da79578132a61a2cfde2857b5acb950f8171061be0c5e5eab79457`.
The six upstream test functions passed in an isolated process.
No package was installed, no model called, and no private history supplied.

Six additional authored controls used an explicit whitespace estimator solely to exercise folding thresholds.
No tokenizer accuracy, token savings, or billed-cost result follows.

| Synthetic control | Native fold/unfold exact | JSON-wrapped fold/unfold exact |
| --- | --- | --- |
| Ordinary repeated long block | Yes | Yes |
| Literal short reference to a known block | No | Yes |
| Literal short reference header | No | Yes |
| Literal unknown reference header | No | Yes |
| Repeated Unicode and whitespace | Yes | Yes |
| Empty and short blocks | Yes | Yes |

Short literal marker text can bypass folding, then be interpreted by unfolding as a control marker.
This observation applies to the pinned revision and these inputs, not all versions or other projects.
A standard JSON envelope avoids the ambiguity while retaining ordinary deduplication:

```python
encoded = [json.dumps(text, ensure_ascii=False) for text in blocks]
folded, _ = folder.fold(encoded)
restored = [json.loads(text) for text in folder.unfold(folded)]
assert restored == blocks
```

The wrapped baseline passed all six controls without a new matching engine.
Our structured codec's regression also preserves literal reference markers through serialized JSON.
This is a useful boundary check, not a distinct paid capability or evidence of receiving-model comprehension.
Keep compact review available as an integration improvement; defer a general compression product on this evidence.
