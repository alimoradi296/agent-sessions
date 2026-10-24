# Structured local handoffs

A structured handoff groups selected conversation claims and retains their evidence excerpts.
It does not decide which historical statements are correct or authorize work in a new session.

## Generate a handoff

```bash
agent-sessions context "example cache" --format handoff --last 2 \
  -d /path/to/private-exports/ -o /path/to/private-handoff.md
```

The command reads local exports. It does not contact an API, run transcript commands, or change agent configuration.
An explicit output file uses atomic replacement with owner-only permissions on POSIX systems.
The output contains real quotes, session IDs, and local paths. Keep it outside public repositories.

`--format excerpts` remains the default. Both formats use the same literal query, source ranking, section limit, and character budget.
The default limits are five sources, eight sections per source, and 24,000 excerpt characters per source.
Use `--last` and `--max-chars` to change the source and character limits.
Summary claims repeat selected evidence text, so the excerpt budget does not limit the total handoff size.

## Read the groups

| Group | Evidence included |
|---|---|
| Historical requests and scope | Recognized user requests and statements about deferred work or scope exclusions |
| Decision candidates | Explicit decision statements, with acceptance and current applicability unverified |
| Reported blockers | Explicit labels such as `Blocker:`, `Blocked by:`, or `Waiting for:` |
| Reported results | Claims about execution or results, without independent verification |
| Proposed next actions | Explicit labels such as `Next action:` or `Next step:` |
| Other proposals | Recognized suggestions and intentions |
| Open questions and reported bugs | Recognized questions, bugs, and causes |
| Checked results | Explicitly empty because the command performs no independent evidence review |
| Conflicts and supersession | Explicit quoted relationship candidates, source matches, and unresolved authority |

The rules recognize a limited set of English wording. They can miss implicit statements, other phrasing, and other languages.
“Not established” means that the selected complete excerpts did not supply a recognized claim for that group.
It does not establish that the project has no blockers, decisions, or next actions.
A reported blocker can be historical or resolved. The command does not establish its current state.

## Follow the evidence

Each claim identifies the speaker, original quote, export path, and cleaned conversation section number.
Section numbers refer to the original export's cleaned sections. Filtering does not renumber them.
Source dates retain their provenance. Cursor file modification dates do not establish exact conversation times or cross-session authority.

The evidence appendix preserves selected complete excerpts, including wording the rules cannot classify.
A shortened excerpt remains visible, with a warning, but never feeds claim classification.
Omitted candidate sections remain listed. The handoff does not inspect them to fill missing fields.
The command does not load distilled JSON to invent checked results or use claims outside the selected evidence.

“Verified” in a conversation remains a reported result. A claim about deployment is not a deployed-revision check.
Conflicting decisions remain attributed to their speakers. Ordering by date does not select a winner.
Independent verification and broader relationship detection remain separate roadmap work.

## Explicit relationship candidates

The handoff recognizes these English forms in selected complete excerpts:

```text
Correction: Replace "Keep the example cache local." with "Use the example queue instead.".
"Use the example queue instead." supersedes "Keep the example cache local.".
"Use the example queue instead." corrects "Keep the example cache local.".
Conflict: "Keep the example cache local." conflicts with "Use the example queue instead.".
```

The replacement form produces `proposed_correction`. The other forms produce reported relationships.
These labels describe what a speaker proposed or reported. They do not establish adoption, agreement, truth, or current authority.
A proposal to replace a statement never deletes or changes the original claim.

Quotes must contain at least eight characters. Matching is exact and case-sensitive.
The parser accepts straight quotes, paired curly quotes, and single backticks.
It skips short quotes, questions, identical endpoints, multiple quoted alternatives, and unsupported framing.
Unrecognized wording remains visible in the evidence excerpts.

Each candidate cites its full relationship quote and its speaker, export, conversation section, and cleaned section line.
Each target reference retains its complete context line. Qualifications and negation remain visible.
Cleaned section lines are not raw transcript or file line numbers.
A substring match locates a reference. It does not establish semantic agreement with the quoted statement.

| Status | Meaning |
|---|---|
| `linked` | Each required reference has one matching source line in selected evidence. This is not verification. |
| `ambiguous` | More than one matching source line exists. Every match remains attributed. |
| `unresolved` | A required reference is absent from selected evidence. It can exist elsewhere. |

For correction and supersession, the replacement statement is quoted in the relationship witness itself.
The original statement requires a reference outside recognized relationship lines.
For conflicts, both references must occur outside those lines.
Repeated relationship quotes cannot supply each other's missing originals.
Copied statements across agents remain separate matches. Dates never choose a winner.
Omitted and shortened sections do not supply relationship evidence.

Relationship summaries repeat source text beyond the excerpt character budget.
The command performs no semantic conflict detection. It cannot resolve unquoted corrections or decide which speaker has authority.

## Review before resuming

1. Read the coverage notes and omitted-section warnings.
2. Read the cited source excerpts for each material claim.
3. Resolve conflicting statements against current task requirements and evidence.
4. Check current code, test results, and deployment state when the task depends on them.
5. Establish the next action from the current user's instructions.

Historical requests and proposed actions do not replace current authorization.
The fresh-session evaluation must stay separate from these source-content checks.
Synthetic regression tests establish grouping and evidence behavior. They do not establish successful understanding by a new agent.
