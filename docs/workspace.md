# Reuse a private topic

A topic saves its query, evidence requirements, and handoff limits.
`resume NAME` rebuilds that topic's local handoff and reports readiness.
The command starts no agent and runs no historical request.

[Assistant review refresh](topic-review-refresh.md) now prepares source packets and updates generated evidence through the saved topic.
It preserves explicit pins, review notes, and prior captures without requiring user paragraph selection.
For code or traceback investigation, `topic search NAME --view evidence` retains raw message content and source coordinates.
Those message locators differ from cleaned handoff section numbers.

## Initialize once

Choose an explicit export archive:

```bash
agent-sessions init --archive /path/to/private-exports
```

The default workspace is `~/.agent-sessions/workspace`.
Initialization creates private state only.
It does not discover transcripts, create the archive, install hooks, run commands, or contact a service.
The archive needs an existing `sessions.json` before search, pin, or resume can read it.

A new workspace directory uses owner-only permissions on POSIX systems.
The configuration file also uses owner-only permissions.
Workspace commands reject recognized Git checkouts and managed symlinks.
This guard does not inspect remote visibility or replace a publication review.

Repeated initialization with the same archive preserves the existing configuration.
A different archive needs a different workspace directory:

```bash
agent-sessions init --archive /path/to/another-private-archive \
  --workspace /path/to/another-private-workspace
```

For that workspace, add the same `--workspace` argument to subsequent commands.
The examples below use the default workspace.

## Save a topic

```bash
agent-sessions topic add cache-review --query "example cache"
agent-sessions topic search cache-review
agent-sessions topic search cache-review "discovery publish" --json
```

Topic search uses the saved archive and returns the same cited passages as standalone search.
An explicit search query overrides the saved query for that search only.
The search refreshes its private SQLite cache.

### Declare a project boundary

New topics include all indexed sources by default.
For one project, copy the exact `project_metadata.cwd` and `project_metadata.project_slug` values from search results.
Declare the values that belong in the topic:

```bash
agent-sessions topic set cache-review \
  --project /workspace/example-project \
  --project workspace-example-project
```

The first value can match a Codex working directory.
The second can match a Cursor project slug.
Replace these synthetic values with the recorded metadata values.
Repeating `--project` includes each explicitly selected value.
The tool does not infer aliases, expand path prefixes, normalize case, or inspect Git roots for these selectors.

The boundary applies to topic search, pins, handoff selection, review scans, and candidate-specific review notes.
Review scans still inspect matching sessions outside the literal query.
An unrelated project's similarly worded correction therefore does not reopen this topic.
A required anchor outside the boundary fails coverage instead of entering the pack silently.

The manifest records the selectors and counts of matched, excluded, and metadata-free sessions.
Unknown project metadata does not match an explicit selector.
A missing transcript inside the declared boundary still prevents a complete review scan.
The audit uses the boundary saved in the captured manifest.
Captured changes record later boundary changes.

To explicitly include the full archive again:

```bash
agent-sessions topic set cache-review --all-projects
```

This boundary uses session metadata, not per-message project attribution.
One session can discuss multiple projects.
An omitted alias can exclude relevant evidence, so the declared values need review.
The boundary does not erase data from exports, other caches, or captured history.
It is not a security boundary against someone with access to those local files.

Search matches words. Handoff compilation retains the existing literal-query selection plus explicit evidence pins.
Neither command interprets a retrieved request as current authorization.

## Pin critical evidence

Use source references from a search result:

```bash
agent-sessions topic pin cache-review --id scope \
  --session synthetic-scope --section 2 --unit paragraph \
  --quote "Discovery only. Do not implement or publish."
```

Replace the synthetic source ID, section number, and quote with the intended source reference.
Topic pins use the same section hashes, paragraph rules, and ambiguity guards as `handoff pin`.
The default evidence unit remains a complete section.

For a paraphrased or multilingual challenge that the scanner misses, link the exact passage explicitly:

```bash
agent-sessions topic link cache-review --id proposed-scope-change --target scope \
  --session synthetic-followup --section 1 \
  --quote "The discovery stage is finished. Implementation is proposed next." \
  --note "This proposes a change to the pinned discovery restriction."
```

The topic's project boundary applies to the link.
The challenge becomes required evidence and creates a pending review on `scope`.
Run `resume cache-review --json` to inspect the candidate.
Use `topic review` with that target and candidate ID.
Both passages remain in the pack after review.
The link note explains an operator interpretation and does not accept the proposed change.
[The continuity guide](continuity.md#link-a-challenge-that-the-scanner-misses) describes evidence changes, budgets, and review limits.

## Inspect conversations that the scanner can miss

The automatic scanner recognizes bounded English quoted patterns.
New instructions can escape that scan when they use paraphrases, questions, or other languages.
The inspection queue lists in-scope sources with no current operator inspection note:

```bash
agent-sessions topic inspect cache-review
agent-sessions topic inspect cache-review --session synthetic-followup
```

The second command shows complete cleaned dialogue sections and an inspection snapshot ID.
Both commands read current exports without changing inspection notes.
Rebuilding a handoff also leaves the queue pending.
Conversations outside the saved query still appear if their metadata matches the topic's project boundary.

After inspecting the intended source, record a note against that exact snapshot:

```bash
agent-sessions topic acknowledge cache-review --session synthetic-followup \
  --snapshot INSPECTION_SNAPSHOT_FROM_VIEW \
  --note "Read the current dialogue. A proposed scope change needs a separate challenge link."
```

Replace the source reference and snapshot ID with values from the view.
Changed source bytes, agent identity, working directory, or project slug reject a stale snapshot ID.
A current note removes that source from the pending queue.
Later changes make the note stale and return the source to the queue.
Missing sources remain pending.

An inspection note reports operator activity.
It proves neither understanding nor the absence of a contradiction.
It does not resolve recognized or operator-linked review candidates.
Use `topic link` to retain a challenge and `topic review` to record its separate review.
The inspection queue is independent of readiness, and each pack states its pending count.
A ready pack can therefore still contain uninspected sources.

For a source with a previous inspection note, show only changed complete dialogue sections:

```bash
agent-sessions topic inspect cache-review --session synthetic-followup --changed-only
```

This view omits unchanged surrounding sections and does not establish their irrelevance.
It matches complete section hashes and counts repeated sections separately.
It reports removed sections but cannot show their text.
Inspection notes store section hashes, not previous transcript copies.
Metadata, formatting, or excluded-content changes can reopen the queue without adding a visible dialogue section.
The view reports changed metadata and changes in the order of matching section hashes.
Repeated matches leave order changes ambiguous instead of identifying which occurrence moved or disappeared.
It recommends the full view for unmatched prior sections, reordered dialogue, metadata changes, and changed sources without added dialogue.
This recommendation does not establish that other views contain sufficient context.
Use the full view when context needs inspection.

[The synthetic inspection replay](inspection-volume-evaluation.md) compares displayed volume with complete-source reading.
It also records initial inspection cost and empty changed views.

Each note lives in the private requirements file.
Captured history records queue changes and inspection notes as historical evidence.
An audit reports when captured queue counts differ from current exports.
Use `topic inspect` for the current queue, including notes added after a capture.

Each topic gets a separate requirements file inside the private workspace.
You can also reuse an explicit existing requirements file:

```bash
agent-sessions topic add release-review --query "release plan" \
  --requirements /path/to/private-work/handoff-requirements.json
```

Adding a topic never replaces an existing topic or requirements file.

## Resume daily

```bash
agent-sessions resume cache-review
```

The command rebuilds `handoffs/cache-review/handoff.md` and `manifest.json` inside the workspace.
It applies the existing evidence, review, source-change, and complete-budget gates.
A draft remains inspectable and causes exit code `1`.
The summary lists missing requirements and unreviewed candidate IDs.
Each distinct captured bundle also gets a separate history revision.
A failed readiness gate preserves the previous ready capture for historical inspection.
The command never substitutes that older capture for a failed current pack.

Print a ready handoff for inspection or explicit transfer:

```bash
agent-sessions resume cache-review --print
```

If any gate fails, this form emits no handoff text on stdout.
Diagnostics appear on stderr, and the command exits with code `1`.
`--json` returns a structured report with readiness and private artifact paths.
Saved configuration and requirements hashes detect changes during compilation and cause a retry when they differ.

## Record a review

If a quoted challenge needs review, inspect the draft and its cited evidence first.
Then record a candidate-specific note:

```bash
agent-sessions topic review cache-review --id scope \
  --candidate REVIEW_ID_FROM_DRAFT \
  --note "Keep both statements. The replacement remains an unapproved proposal."
agent-sessions resume cache-review
```

The note does not grant authorization or establish correctness.
Changed evidence or a new challenge can reopen review on the next resume.

## Inspect captured changes

```bash
agent-sessions topic history cache-review
agent-sessions topic changes cache-review --diff
```

History lists complete revision hashes and readiness recorded during capture.
Changes compare the current capture with the previous distinct capture.
The summary separates new requirements, changed evidence, selection changes, and newly pending reviews.
A recorded review note does not establish that a conflict is resolved.
The optional diff shows the actual captured handoff text.

Read a specific capture with its complete revision hash:

```bash
agent-sessions topic show cache-review --revision FULL_REVISION_HASH
```

History views change no files and do not inspect live agent applications.
Their output is explicitly historical.
Recorded readiness does not establish current source validity, factual correctness, or authorization.

Identical captured content reuses its revision instead of creating duplicates.
Revision IDs are manifest content hashes, not agent timestamps or proof of authority.
Entries retain first-seen order. Revisiting an older capture updates the current pointer without inventing a new event date.
The index records the previous distinct capture and most recent ready capture.

Captures live in `history/TOPIC/REVISION/` inside the private workspace.
They contain selected handoff evidence, not complete backups of raw transcripts.
This history can retain older private conversation text after the latest pack changes.
It does not automatically prune captures.

The history index commits after the captured bundle.
Interrupted writes can leave unindexed partial revisions that history views do not list.
A retry can complete that capture when the history index remains valid.
A damaged or missing index with existing captures stops updates instead of silently discarding history.
Corrupted recorded snapshots also stop updates.
Restore the affected private files before retrying.

The latest bundle and history index are not one transaction.
History can contain a complete capture even when replacement of the latest view fails.
A later resume can rebuild the latest view from current inputs.

## Change limits without replacing pins

```bash
agent-sessions topic set cache-review --max-total-chars 80000
agent-sessions topic set cache-review --query "revised cache plan"
agent-sessions topic list --json
```

Topic changes preserve the linked requirements file and its contents.
Topic listing changes no files.
The default limits remain five sources, 24,000 excerpt characters per source, and 64,000 complete handoff characters.
Character limits are not provider token limits.

## Private state

`workspace.json` contains local paths, saved queries, requirements references, and limits.
Requirements and handoffs can contain real conversations and source identifiers.
This state belongs outside public repositories.
No command in this workflow uploads data or configures a model provider.
An explicit transfer to another tool follows that tool's own data handling.

Workspace configuration currently selects the export archive only.
Custom raw agent source roots remain separate roadmap work.
