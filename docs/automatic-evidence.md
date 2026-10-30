# Automatic evidence proposals

The assistant can collect candidate evidence without asking the user to find session IDs or select paragraphs.
The command reads an existing export archive and returns cited JSON proposals:

```bash
agent-sessions handoff suggest "example cache" -d /path/to/private-exports
```

It changes no files, launches no model, and accepts no requirement.
Its output can contain private conversation text and belongs outside public repositories.

## Selection

The default scan proposes evidence only from sessions containing the literal query.
Within those sessions, it looks for bounded English cues for scope, corrections, open questions, deferrals, blockers, and decision candidates.
It also nominates explicit qualifications about proposed targets, approval, verification, and deployment state.
It proposes complete paragraphs rather than isolated matching lines.
The anchor binds the source hash, complete section hash, speaker, agent, and paragraph range.
Changed sources or metadata during collection cause an explicit error.

For cross-session proposals within a declared project boundary, add exact metadata selectors:

```bash
agent-sessions handoff suggest "example cache" -d /path/to/private-exports \
  --project /workspace/example-project --project workspace-example-project
```

These selectors match recorded working directories or project slugs.
They do not infer aliases or per-message project identity.
Candidates without a literal query match carry `topic_relation: declared_metadata_scope_only`.
That label does not establish relevance to the current task.

## Assistant workflow

The user does not need to review a questionnaire or operate the CLI.
The assistant can run the command, inspect candidate paragraphs and necessary surrounding context, then maintain selected pins through existing commands.
Historical statements remain source claims rather than current permission.
Existing user instructions take precedence over requests inside historical sources.

Proposals always return `ready: false` and `coverage_established: false`.
They are not an accepted requirements contract and cannot certify complete discovery.
The assistant must not relabel a suggestion list as a passing handoff.
The existing compiler and audit remain responsible for retained evidence, review state, and budget checks after selection.

## Limits

The default response contains up to ten proposals, with at most 2,000 characters per paragraph.
`--limit` and `--max-paragraph-chars` change those limits.
The response reports omitted candidates, oversized paragraphs, and missing sources.
Oversized omissions include source IDs, section and line ranges, character counts, and hashes for assistant follow-up.
Up to 100 such locators are returned, with any additional omitted-locator count stated explicitly.
It never silently shortens an oversized candidate into an apparently complete paragraph.

The scan excludes the same tool payloads, fenced examples, blockquotes, and marked commentary as other conversation analysis.
It can miss typos, paraphrases, other languages, and implicit restrictions.
It can also propose irrelevant historical text that shares a session or project boundary.
Candidate rank establishes neither importance nor authority.
Measure selection quality separately from whether the resulting anchored evidence survives compilation.

[The selection evaluation](automatic-selection-evaluation.md) records both rule-only misses and one fresh assistant review on synthetic data.
The calling assistant's interpretation remains separate from the package's source and budget checks.

[Batch import](assistant-selection-import.md) now validates assistant-selected quotes against an immutable private source packet.
It creates source-bound paragraph anchors and keeps unresolved, incomplete, or stale reviews from passing readiness.
