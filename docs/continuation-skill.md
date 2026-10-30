# Assistant-operated continuation

The package includes a skill for recovering context from saved topics.
The assistant selects evidence, imports its response, and rebuilds the handoff.
The user does not need to select passages or complete a questionnaire.

Print the bundled instructions:

```sh
agent-sessions skill
```

The command prints text without changing agent configuration.
An assistant can read this output or the bundled `SKILL.md` directly.
Automatic skill discovery depends on the receiving client and has not been established by this command.

## Local client setup

Both clients document a shared user skill directory: `~/.agents/skills/`.
See the [Codex skill documentation](https://learn.chatgpt.com/docs/build-skills) and
[Cursor skill documentation](https://cursor.com/help/customization/skills).
Place the bundled instructions in `agent-sessions-continuation/SKILL.md` under that directory.
An assistant can perform this setup; the user does not need to copy passages.
Preserve an existing different skill instead of overwriting it.
Keep archive paths and workspace configuration separate from the generic skill.
Installing export hooks does not install this skill.

An existing local archive and workspace are required for saved-topic continuation.
Keep their paths and generated files outside Git checkouts.
The skill uses saved topics, source-bound review packets, validated imports, and current handoff checks.
It preserves explicit pins and earlier captures during selection refresh.

Historical instructions remain evidence rather than current authorization.
Unresolved conflicts, omitted input, and stale reviews keep the handoff in draft state.
The assistant can continue other authorized work while explaining these limits.
Repeated reviews cannot establish missing authority.

Review prompts group source and section metadata to reduce repeated framing.
Displayed paragraphs remain complete, and validation packets retain full source hashes.
This improves available space without changing the meaning of complete review.

For histories that exceed one prompt, use `topic prepare-review --batch-review` with the topic and workspace arguments.
`--max-prompt-chars` limits each batch.
The main prompt lists every batch, and the final response must acknowledge them through `reviewed_batches`.
The assistant compares selections across batches before reporting conflicts.
The importer checks all batch hashes and rejects missing acknowledgements.
An acknowledgement records the assistant's report; it does not prove understanding.
Preparation stops at 32 batches, and oversized paragraphs or remaining input stay listed as omissions.
The existing limit of 100 selected anchors still applies to the combined response.

See [topic review refresh](topic-review-refresh.md) for the underlying commands and preservation rules.

## Fresh assistant observation

One fresh assistant used the skill from an isolated wheel installation.
It listed topics, built an initial capture, prepared a review, imported its response, and rebuilt the topic.
It selected three synthetic paragraphs and preserved the existing explicit pin.
All four anchors retained their evidence, with no review input omissions.
The assistant left conflicting historical permissions unresolved and reported the current handoff as a draft.
It retained the earlier capture without substituting it for the current result.
The response file had owner-only permissions, and source archive hashes remained unchanged.
No user selection or questionnaire was needed during this run.

This single small synthetic run does not establish general selection accuracy, automatic client activation, or reduced total work.
Private archive evaluation remains separate from this public observation.

## Batched continuation observation

A second fresh assistant read an eight-batch synthetic packet from another isolated wheel installation.
It returned all batch acknowledgements and selected the restriction, timing qualification, open question, and conflicting later permission.
The importer preserved one explicit pin and added three generated anchors.
Coverage and budgets passed, while the unresolved conflict kept the result in draft state.
Source archive hashes stayed unchanged, and the response file had owner-only permissions.

The batches limit individual prompt size rather than total assistant context or work.
This single run does not establish reliable selection across arbitrary long histories.
