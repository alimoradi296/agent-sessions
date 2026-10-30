# Import assistant-selected evidence

The assistant can turn its selected source quotes into paragraph anchors in one batch.
The user does not need to locate session IDs or pin each passage.
These commands prepare local data and validate a response. They do not launch a model.

## Prepare a private review packet

The assistant chooses the current archive, query, and explicit project metadata:

```bash
agent-sessions handoff prepare-review "example cache" \
  -d /path/to/private-exports -o /path/to/new-private-review \
  --project /workspace/example-project --max-prompt-chars 32000
```

The new directory contains `review-prompt.txt` and `review-packet.json`.
Recognized Git checkouts and managed symlinks are rejected for private packet output.
POSIX directories use owner-only permissions, and files use owner-only read and write permissions.
Keep packets and responses outside public repositories.

For repeated long evidence, the assistant can add `--compact-review`, with or without `--batch-review`.
This also works with `topic prepare-review`.
Preparation builds both complete plans and selects compact encoding only when total prompt text decreases, all ordinary-plan occurrences remain, and omission count does not increase.
Otherwise it publishes the identical ordinary packet.
The JSON result reports the effective encoding, fallback, and both character totals.

Compact batches contain a local `texts` dictionary and an ordered occurrence structure with `text_ref` indexes.
Roles, source identities, section numbers, and paragraph coordinates remain separate for every occurrence.
Read all occurrences, including repeated text in different contexts.
The effective compact format enters the review ID and packet hash; ordinary packets retain their existing format and identity.
The response schema and source-validation checks are unchanged.
Preparation costs more local work because it compares two plans; fewer characters do not prove equal understanding or lower model cost.

Before reading a large packet, inspect `total_prompt_chars` and `largest_prompt_chars` in the preparation result.
The first includes the routing prompt and every batch; the second reports the largest individual prompt.
The existing `prompt_chars` field measures only the main prompt, which is routing text for batched review.
Compare the complete input with the calling agent's available context, reserving room for its answer and other evidence.
Character counts are not token counts, and zero omissions do not establish that the agent can review everything.
If full review does not fit, keep the review incomplete rather than acknowledging unread batches.

To enforce a declared complete-input character limit, add `--max-total-prompt-chars` to preparation.
The limit includes the main prompt and all batches and is checked after ordinary/compact selection.
If exceeded, the CLI exits 1 with JSON `status: over_budget`, measured sizes, and the amount over budget.
It returns `output: null`, creates no requested packet, and removes its temporary plans.
Saved-topic requirements and earlier captures stay unchanged.
An exact fit is accepted; with compaction, a smaller complete plan may fit even when ordinary input exceeds the limit.
The limit is optional and does not infer a model's token availability.
The assistant can continue a bounded historical lookup without claiming that saved-topic review is complete.

The packet includes complete cleaned paragraphs with source, speaker, section, and hash information.
Explicit project selectors include all matching sessions, even if their text does not repeat the query.
Without selectors, only literal-query sessions supply review text.
Metadata scope does not establish per-message relevance or complete task coverage.

`--max-prompt-chars` limits the complete rendered prompt, including instructions and evidence metadata.
Paragraphs that do not fit are omitted whole and recorded in the packet.
Missing sources also remain explicit omissions.
The packet's prompt and source identities are hash-bound.

## Validate the assistant response

The response format is:

```json
{
  "review_id": "COPY_EXACT_REVIEW_ID_FROM_PROMPT",
  "selected": [
    {
      "session_id": "synthetic-scope",
      "quote": "Discovery only. Do not implement or publish.",
      "reason": "A historical scope restriction."
    }
  ],
  "unresolved_conflicts": true,
  "current_authorization": "read_only"
}
```

The assistant saves its response privately, then imports it:

```bash
agent-sessions handoff import-review /path/to/private-review \
  --answer /path/to/private-response.json \
  -o /path/to/new-private-requirements.json
```

Each quote must match exactly one paragraph shown in the packet for that source ID.
For repeated text, include both `section` and `paragraph_start_line` in the selection object.
Use the packet's section number and the paragraph's `start_line` value.
These lines are relative to the cleaned section, rather than the raw Markdown export.
The importer checks both coordinates and the quote against the same hashed packet record.
Missing coordinate pairs, invalid positions, and mismatched text fail before requirements are written.
Quotes without coordinates still require a unique paragraph match.

For example, two paragraphs can both contain the same synthetic restriction:

```json
{
  "session_id": "synthetic-scope",
  "section": 1,
  "paragraph_start_line": 5,
  "quote": "Discovery only. Do not implement or publish.",
  "reason": "Retain this specific occurrence of the historical restriction."
}
```

Coordinates identify an occurrence; they do not establish authorship or current permission.
The response must echo the packet's exact review ID.
Invented quotes, unknown sources, ambiguous matches, duplicate paragraph selections, and invalid response fields fail before requirements are written.
Reviewed source bytes, source identities, and project membership must still match the prepared snapshot.
The command refuses to overwrite an existing requirements file.
Existing manual pins therefore remain intact.

The imported anchor binds the complete section hash and containing paragraph range.
A short model quote does not authorize shortening that paragraph.
The model's explanation remains an interpretation, not factual verification or permission.
The required `read_only` value describes the evidence-review task and grants no broader action authority.

## Build and audit

```bash
agent-sessions handoff build "example cache" \
  --requirements /path/to/private-requirements.json \
  -d /path/to/private-exports -o /path/to/private-bundle
```

Build inherits the imported project selectors unless the caller explicitly supplies selectors.
The existing source, section, paragraph, and total character limits still apply.
Omitted review input or reported unresolved conflicts prevent readiness.
Known quoted challenges continue to need their separate review notes.

The assistant review is tied to its query, project selectors, source identities, project membership, and reviewed source versions.
Changed queries, selectors, relevant metadata, or source versions reopen the review gate.
This catches an unseen new paraphrased source without claiming that the bounded scanner understands it.
New reviews ignore changes to excluded projects and index formatting.
They retain the original index hash for provenance and add `scope_sha256` for review-visible metadata.
Existing reviews without that field keep their original whole-index freshness rule.
Moving a source into or out of the selected project still reopens review.
Rebuild a review packet and collect a fresh response when that snapshot becomes stale.
No user questionnaire is required.

Audit checks the stored review snapshot against current exports and reports stale assistant review explicitly.
It does not certify source authenticity, model understanding, or the absence of semantic mistakes.
Hashes do not protect against someone deliberately rewriting the packet and all matching hashes.

## Integration observation

The initial version-1 integration reused the [earlier synthetic assistant response](automatic-selection-evaluation.md) against a new packet built from identical source bodies.
It was not a second semantic model trial.
All seven selections became valid anchors, with no review input omitted.
All seven complete evidence paragraphs survived the larger handoff budget.
The bundle remained a draft because the response reported unresolved conflicts and a quoted challenge still needed review.
A tighter per-source budget failed coverage for the oversized paragraph rather than silently keeping only its short quote.
Separate tests reject stale inputs and show that a new paraphrased source invalidates an earlier assistant review.

Current version-2 packets also require the response's matching `review_id`.
[Saved-topic refresh](topic-review-refresh.md) records a fresh response using that format and preserves explicit pins and earlier captures.


## Whole-message evidence review

`handoff prepare-review --view evidence` includes raw exported messages, including tool content and phase headings.
Each record is one complete message with `paragraph_start_line: 1`.
Imported anchors use whole-message units and retain their evidence coordinate namespace.
Default dialogue packets keep their existing paragraph behavior.
Saved-topic refresh infers the active view, preserves explicit pins, and rejects changing a populated contract's coordinates.
See [raw evidence handoffs](raw-evidence-handoffs.md) for budgets, source audit, and examples.
