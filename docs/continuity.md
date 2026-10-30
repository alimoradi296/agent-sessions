# Keep critical evidence in a handoff

A short handoff can omit a scope restriction, correction, or unresolved question.
Evidence requirements let you name the exact source text that must survive.

The compiler gives those requirements priority over query relevance.
If a limit excludes required evidence, the compiler writes a draft and exits with code `1`.
The draft names each requirement that failed.

## Try the synthetic example

After package installation, run:

```bash
python examples/continuity_demo.py
```

The example creates a new private temporary directory.
It uses invented conversations from three agents.
It reads no agent history and installs no hooks.

The example shows four cases:

1. A literal-query handoff omits a scope restriction that does not repeat the query.
2. A small budget fails the requirements gate.
3. A larger budget retains all three required quotes.
4. A later change to a source export fails the read-only audit.

It also appends an unrelated message without invalidating selected evidence.
A quoted challenge from another agent reopens review.
A synthetic operator note records review while both statements remain unverified.

The example changes only its synthetic export to demonstrate the last case.
The final bundle therefore needs review when you audit it again.

## Find the evidence

The assistant can first collect [automatic cited proposals](automatic-evidence.md) instead of asking the user to locate individual passages.
The proposals remain unaccepted and expose their selection limits.

Search the archive for the constraint or decision:

```bash
agent-sessions search "discovery publish" -d /path/to/private-exports --json
```

Each hit includes a session ID, cleaned section number, exact text slice, and source hash.
Search uses words by default. It does not interpret regular expressions or Boolean operators.
`--match phrase` requires the query words in order. `--match any` accepts any query word.

## Pin a requirement

Use a session ID and section number from a search hit:

```bash
agent-sessions handoff pin --id discovery-only \
  --session synthetic-scope --section 2 \
  --quote "Discovery only. Do not implement or publish." \
  -d /path/to/private-exports \
  -o /path/to/private-work/handoff-requirements.json
```

Replace the synthetic values with the intended local source reference.
If you omit `--quote`, the command pins the entire cleaned section.
Each subsequent pin appends a requirement with a different ID.
The command rejects quotes absent from the selected section.
It records the current source hash, agent, speaker, and complete section hash.
The section hash includes qualifications outside the selected quote.

### Select a paragraph from a long turn

Section pins require the complete turn by default.
If the turn is too large, explicitly select its containing paragraph:

```bash
agent-sessions handoff pin --id discovery-only \
  --session synthetic-scope --section 2 --unit paragraph \
  --quote "Discovery only. Do not implement or publish." \
  -d /path/to/private-exports \
  -o /path/to/private-work/handoff-requirements.json
```

Paragraph mode requires an explicit quote that identifies exactly one paragraph.
Blank lines define paragraph boundaries.
The pack retains every line in that paragraph and cites its cleaned section line range.
Multiple selected paragraphs remain separate excerpts with separate source ranges.
The pack states that the complete section is absent.
Paragraph excerpts do not feed complete-section claim classification.

The pin still binds the complete section hash and speaker.
A changed qualification elsewhere in that section therefore requires inspection.
Paragraph mode does not establish that omitted context is irrelevant.
The compiler never changes a section pin into a paragraph pin automatically.

### Limit sessions by recorded project metadata

`handoff pin`, `handoff link`, `handoff build`, and `handoff review` accept repeatable `--project` selectors.
Each selector matches an exact recorded working directory or project slug.
Use the same selectors for build and review so that candidate IDs refer to the same evidence set.
The saved manifest binds these selectors, and audit reuses them.
Selectors do not infer that different agent paths belong to the same project.

```bash
agent-sessions handoff build "example cache" \
  --requirements /path/to/private-work/handoff-requirements.json \
  --project /workspace/example-project --project workspace-example-project \
  -d /path/to/private-exports -o /path/to/private-work/handoff
```

Out-of-scope required anchors fail coverage.
Excluded sessions do not contribute quoted review candidates or handoff excerpts.
The pack records exclusion counts and missing project metadata.
This is a session-metadata filter, not proof that each retained message concerns that project.

Unrelated appended messages do not invalidate an unchanged section.
An identical section can move only when one complete text-and-speaker match exists.
The pack records the old and current section numbers.
Changed qualifications, changed speakers, and ambiguous duplicates require inspection.

The requirements file contains quotes and session IDs.
It belongs outside public repositories and outside the export archive.
Owner-only file permissions apply on POSIX systems.

## Link a challenge that the scanner misses

The automatic scanner recognizes bounded English quoted patterns only.
It can miss paraphrases, questions, and other languages.
A passing review gate does not establish the absence of contradictory instructions.

For an exact passage that challenges a pinned requirement, add an explicit link:

```bash
agent-sessions handoff link --id proposed-scope-change --target discovery-only \
  --session synthetic-followup --section 1 \
  --quote "The discovery stage is finished. Implementation is proposed next." \
  --note "This proposes a change to the pinned discovery restriction." \
  --requirements /path/to/private-work/handoff-requirements.json \
  -d /path/to/private-exports
```

Replace the synthetic source reference with the intended local passage.
For scoped work, use the same `--project` selectors as build and review.
The target must already exist and have current complete-section evidence.
Legacy quote-only requirements need a new complete-section pin before linking.
The link needs a new ID, an exact source quote, and an operator explanation.
Links cannot target other links.

The command pins the challenge as mandatory evidence alongside the target.
Both passages consume the existing source and character budgets.
`--unit paragraph` uses the same paragraph rules and complete-section binding as ordinary pins.
A missing or changed challenge fails coverage instead of disappearing silently.
Unrelated appends and unique section relocations preserve the review identity.

The link records the operator's interpretation, not automatic contradiction detection or accepted replacement.
It creates a pending candidate on the target requirement.
Build a draft to obtain its review ID, then use `handoff review` on the target.
Record whether the two statements remain unresolved in the review note.
Review retains both passages and establishes neither factual correctness nor current authorization.
Changing the link explanation requires a new review.

## Build the handoff

```bash
agent-sessions handoff build "example cache" \
  --requirements /path/to/private-work/handoff-requirements.json \
  -d /path/to/private-exports \
  -o /path/to/private-work/handoff
```

The bundle contains `handoff.md` and `manifest.json`.
The version 2 manifest records source hashes, selected section hashes, requirement statuses, and the handoff hash.
It also contains its own canonical content hash.
The handoff renders selected evidence directly, without duplicate claim summaries or empty classification groups.
Every retained excerpt keeps its source, speaker, section number, and applicable paragraph range.
Coverage gates, review candidates, and operator notes remain visible.
The manifest records the rendering method and a character-count breakdown.
Selected excerpt characters and framing, review, and citation characters sum to the complete handoff length.
Character counts are not model token counts or evidence of improved understanding.
The compiler writes each file atomically. Replacement across both files is not one transaction.
The audit detects a mismatch after an interrupted replacement.

Required sections take priority, including sections that do not match the query.
Requirements retain whole sections so that qualifications remain visible.
Defaults remain five sources and 24,000 excerpt characters per source.
Ranked context normally includes at most eight sections per source.
Explicit required evidence can exceed that count when it fits the character budgets.
The manifest records the resulting section-count allowance.
`--last` and `--max-chars` change the source and character limits.
If a limit excludes a required section, the bundle remains a draft.

The default total handoff limit is 64,000 characters, including framing, citations, and review evidence.
This limit covers `handoff.md`, not the separate JSON manifest.
`--max-total-chars` changes that limit.
The compiler removes optional passages before required sections.
If required content and framing still exceed the limit, the bundle remains a draft.
The draft can exceed the limit so that the failure remains inspectable.
A ready handoff never exceeds the stated total limit.
Character counts are not provider token counts.

## Review a quoted challenge

The compiler scans all indexed, cleaned conversations for explicit quoted corrections, supersession, and conflicts.
This scan includes sources that do not match the query.
A new candidate can reopen review even when the pinned source remains unchanged.
The scan does not infer authority or acceptance from a date, speaker, or proposed replacement.

`coverage_passed` means required text survived selection.
`review_passed` means the scan completed and every recognized or operator-linked challenge has an explicit review note.
`total_budget_passed` means the complete handoff fits the total character limit.
`ready` requires all three gates.

Packs also show the count of sources without current operator inspection notes.
This count is independent of readiness and does not certify understanding.
[Topic inspection](workspace.md#inspect-conversations-that-the-scanner-can-miss) exposes uninspected and changed conversations, including sources outside the literal query.

If the draft lists a challenge, inspect its source and both quoted statements.
Record a review note with its review ID:

```bash
agent-sessions handoff review --id discovery-only \
  --candidate REVIEW_ID_FROM_DRAFT --note "Keep both statements. The replacement remains a proposal." \
  --requirements /path/to/private-work/handoff-requirements.json \
  -d /path/to/private-exports
```

The note does not authorize implementation or establish factual correctness.
Both statements remain visible in subsequent packs.
A changed witness, agent, or matching reference changes the review ID and reopens review.
The command rejects review IDs that do not currently affect the requirement.

## Audit before use

```bash
agent-sessions handoff audit /path/to/private-work/handoff \
  -d /path/to/private-exports --json
```

The audit reads the bundle and current exports.
It changes no files, runs no quoted commands, and contacts no service.
These checks cover indexed exports, not uncaptured changes in an agent application.
Before the audit, use reconciliation to inspect missed or changed exports.
Exit code `0` means the retained evidence remains current and no recognized or operator-linked challenge needs review.
Exit code `1` means the bundle needs review or an input error occurred.

Unrelated source changes produce notes when all selected sections remain identical at their cited positions.
Moved sections require a rebuild so that citations use current section numbers.
The audit also scans other indexed sessions for new quoted challenges.
A missing indexed export makes that scan incomplete and prevents readiness.

| Status | Meaning |
|---|---|
| `covered` | The required quote occurs in a complete retained section |
| `source_missing` | The indexed source is absent or is a symlink |
| `outside_project_scope` | The required session does not match the declared metadata selectors |
| `source_changed` | The current export differs from the pinned hash |
| `evidence_changed` | The complete pinned section or its speaker changed |
| `source_agent_changed` | The indexed agent identity differs from the pin |
| `anchor_ambiguous` | Multiple identical section matches prevent a unique relocation |
| `paragraph_changed` | The explicit paragraph locator does not match the current section |
| `section_missing` | The requested cleaned section does not exist |
| `quote_mismatch` | The quote does not occur in that section |
| `source_limit_exceeded` | The source limit excludes a required source |
| `section_budget_exceeded` | The character or section limit excludes a required section |

## Limits

Coverage measures retained evidence. It does not measure model understanding or factual accuracy.
A quoted statement that says “verified” remains a reported result.
These commands do not establish test success, deployment, customer acceptance, or current authorization.

Requirements cover only the evidence that you explicitly pin.
The compiler does not discover every critical constraint automatically.
Requirement packs preserve evidence without automatic claim grouping.
The separate `context --format handoff` command retains English claim grouping and its evidence appendix.
An unclassified statement can still serve as a required quote.

A source hash detects changed bytes. A section hash distinguishes unchanged evidence from unrelated source updates.
Neither hash establishes source authenticity or freshness against a live repository.
This audit compares exports, not raw agent files or deployed code.
It does not protect against a user who rewrites the manifest and all matching hashes.
Hash comparison cannot prevent a source change after the audit finishes.

Required evidence can exclude otherwise useful query matches under a small source limit.
The coverage gate does not certify that the pack contains every relevant passage.
Each manifest lists the selected sources and sections for review.

The relationship scan recognizes only explicit English quoted forms documented in [the handoff guide](handoff.md).
Implicit contradictions and unrecognized wording can remain undetected.
An explicit review note covers one recognized candidate, not every possible contradiction.
Version 1 bundles need a rebuild before the version 2 audit can read them.
