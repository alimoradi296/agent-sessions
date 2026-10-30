# Refresh assistant evidence in a saved topic

The assistant can prepare and import a review through the saved topic.
It reuses the topic's archive, query, project selectors, and later handoff limits.
The user does not need to select source paragraphs or edit configuration.
These commands do not launch a model or upload transcripts.

## Assistant workflow

The assistant prepares private review input:

```bash
agent-sessions topic prepare-review cache-review --json
```

The result includes the private packet directory, total and largest prompt sizes, omissions, and `review_id`.
For batched review, `prompt_chars` alone is the routing prompt; use `total_prompt_chars` to assess complete input size.
An optional `--max-total-prompt-chars` enforces a complete-input character allowance.
Over-budget preparation exits 1 with JSON diagnostics and no packet; the active topic and prior captures remain intact.
The assistant reviews the packet's `review-prompt.txt` and saves its JSON response privately.
The response must echo that exact `review_id`.
The ID binds the archive, source versions, query, scope, displayed evidence, omissions, budget, and review instructions.
An answer from another packet is rejected even if its selected quote still exists.

The assistant imports the response and rebuilds the topic:

```bash
agent-sessions topic import-review cache-review /path/to/private-packet \
  --answer /path/to/private-response.json --json
agent-sessions resume cache-review --json
```

The packet must match the saved topic's current archive, query, and exact project selectors.
Stale sources or mismatched response IDs stop the update before the active topic changes.
All existing full-paragraph, conflict, omission, budget, and source-review gates still apply.
Import itself never certifies readiness.

## Preserve explicit work

New imported anchors carry an explicit generated-selection marker.
A later refresh can replace selections with that marker.
Ordinary pins remain protected, including legacy anchors without a generated marker.
An assistant selection cannot overwrite protected evidence with different content under the same ID.
Manual challenge links retain their targets even when the new assistant selection omits those targets.

Candidate review notes carry forward only when the generated evidence identity is unchanged and unambiguous.
Changed witness candidates still require their current candidate-specific review.
Source inspection notes remain separate from assistant interpretation and challenge review.

An original external requirements file stays unchanged.
After refresh, topic commands use a new private active requirements file.
Editing a previous file directly does not edit the current topic.
Explicit topic pins, links, review notes, and inspection notes share the refresh lock and resolve the active file after locking.
This prevents an edit waiting behind refresh from landing in the superseded file.

## Preserve captures and publish the pointer last

Previous and new requirement bytes are captured privately under content hashes.
Existing damaged captures cause an error instead of silent replacement.
The active requirements file uses a separate path and remains mutable through topic commands.
The configuration pointer changes only after the new file and captures exist.
An interrupted or failed update can leave unused private files, while the previous pointer remains intact.
No automatic cleanup deletes earlier evidence.

Reimporting the same packet and identical response preserves the active pointer and file timestamps when the combined requirements are unchanged.
Earlier handoff captures remain available through `topic history` and `topic show`.
`resume` creates a new distinct capture only when captured content changes.

## Synthetic integration observation

One fresh assistant reviewed the synthetic source packet without answer labels or parent conversation.
Its response echoed the provided review ID and selected seven source passages.
The import created seven generated anchors.
A scripted explicit timing pin then survived another import of that response.
All eight anchors retained their evidence, including the shared timing paragraph.
The resulting handoff remained a draft because reported conflicts were unresolved.
Reimporting again was a no-op, and the earlier handoff bytes remained unchanged.

The refresh and explicit-pin operations were scripted controls, not observed human effort.
This demonstrates saved-topic routing and preservation, not general semantic accuracy, reduced reading time, adoption, or willingness to pay.
