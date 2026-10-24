# agent-sessions roadmap

Current package version: **0.2.0**. The changes below are unreleased.

## Current priority

Make exports complete and traceable before expanding knowledge extraction.
The Context Bridge prototype uses local transcript excerpts with source links.
It does not treat historical claims as proof of completion.

All public examples and test inputs must be synthetic.
Private transcripts, exports, reports, and context packs stay outside the repository.

## Existing capabilities

| Capability | Status |
|---|---|
| Claude, Codex, and Cursor parsers | Implemented |
| Markdown export and shared indexes | Implemented |
| Single-session and bulk export | Implemented |
| Keyword search and aggregate statistics | Implemented |
| Rule-based distillation | Implemented, heuristic results |
| Session links, reports, and Obsidian export | Implemented |
| Hook installers | Implemented, runtime compatibility needs separate checks |
| Read-only archive diagnostics | Implemented with `doctor`, hook execution remains unverified |
| Concurrent export protection | Implemented with directory locks and atomic replacement per file |
| Selective reconciliation | Implemented with a read-only dry run, private reports, and optional cron instructions |

An implemented feature is not a guarantee of compatibility with every agent version.

## Phase 8 — Reliability and coverage: first

### Implemented in this change

- [x] Merge Codex files by the session ID in metadata.
- [x] Remove identical overlap across resumed files while preserving repeated events within a file.
- [x] Use merged history for bulk export, single-session export, hooks, and distillation.
- [x] Preserve Codex function calls, custom tool calls, outputs, and call IDs.
- [x] Read the Codex branch, model, provider, and event timestamps.
- [x] Prefer response messages over matching legacy event messages within a turn.
- [x] Label Cursor dates as estimates from file modification time.
- [x] Keep Cursor project slugs without inventing working directories.
- [x] Preserve Cursor messages that contain only tool results.
- [x] Export a coverage manifest with a status for each discovered source file.
- [x] Add date limits to bulk export.
- [x] Add synthetic regression tests.
- [x] Ignore common private transcript and export artifacts in Git.
- [x] Add read-only `doctor` checks for source discovery, hook configuration, stale exports, and index consistency.
- [x] Add text and JSON diagnostic reports with exit codes for warnings and errors.
- [x] Check synthetic fixtures for read-only behavior and hook non-execution.
- [x] Lock each output directory during session export and standalone renderer updates.
- [x] Stage and sync all session export files before atomic replacement, with the JSON index last.
- [x] Fail on invalid indexes and lock timeouts without silently discarding existing entries.
- [x] Match Markdown index entries by full session ID and keep each new row on one line.
- [x] Test concurrent processes, write failures, and process termination with synthetic fixtures.
- [x] Install Codex `Stop` and Cursor `stop` handlers with pinned Python launchers and private output destinations.
- [x] Preserve unrelated hooks, back up changed files, and migrate this exporter's legacy Cursor event.
- [x] Accept Cursor conversation IDs and transcript hints. Keep hook stdout valid JSON.
- [x] Test generated launchers from unrelated working directories with synthetic transcripts and isolated homes.

- [x] Add `reconcile` for missing or changed exports, with a read-only dry run and optional cron instructions.

### Remaining

- [ ] Check application-triggered hook execution after reload and trust review on supported agent releases.
- [ ] Define support for child-agent transcripts and their parent relationships.
- [ ] Check locking and interrupted writes on Windows.
- [ ] Surface malformed records and unsupported event types in coverage reports.

### Acceptance criteria

- Every discovered source file has an explicit status.
- Repeated exports preserve history and produce one file per session ID.
- Tool calls retain their arguments, results, and correlation IDs.
- Estimated dates remain visible in exported metadata and reports.
- Tests run without access to developer home directories or private transcripts.
- Concurrent local exports preserve every session entry in both indexes.
- Individual export files remain complete after interruption. A retry restores consistency across files.

Atomic replacement is per file. A crash can leave the transcript and indexes from different export attempts.
`doctor` can detect inconsistencies. `reconcile` can restore content differences from readable sources and valid indexes.
Invalid or missing archive indexes require explicit restoration. Scheduling remains opt-in.

## Phase 4 — More accurate extraction

### Implemented in this change

- [x] Exclude tool payloads, code blocks, quoted text, and common instruction blocks from decision extraction.
- [x] Exclude Codex commentary and analysis from knowledge extraction.
- [x] Remove broad decision patterns based on “instead of” and “do not.”
- [x] Label extracted decisions as candidates and outcomes as unverified in reports and notes.
- [x] Carry date provenance into distilled JSON and Obsidian notes.
- [x] Attach a speaker, exact quote, source coordinates, and extraction method to each new claim.
- [x] Separate requests, proposals, decision candidates, reported results, bug reports, deferred work, and open questions.
- [x] Keep transcript claims marked as not checked, including statements that use verification words.
- [x] Infer outcomes from reported-result claims rather than requests, titles, or proposals.
- [x] Evaluate English extraction rules with manually labeled synthetic positive and negative cases.
- [x] Show claim references in reports and Obsidian notes. Load older distilled files without inventing citations.

### Remaining

- [ ] Add an independent evidence-review workflow before producing checked results.
- [ ] Improve file and PRD extraction. Mentions do not prove that a file changed.
- [ ] Add optional `distill --llm` with a strict output schema.
- [ ] Require explicit provider configuration before sending transcript data to an API.
- [ ] Support a local model as an optional extraction backend.

English rules can miss unfamiliar wording and other languages. Labels remain heuristic candidates.
Checked results require independent evidence review, which is not implemented.

### Acceptance criteria

- Each result identifies its evidence and extraction method.
- A request to implement a feature never counts as proof of implementation.
- A passing local test never counts as proof of deployment.
- Private evaluation data stays outside the repository.

## Phase 11 — Context Bridge, graph, and rewind

### Context Bridge prototype: implemented

```bash
agent-sessions context "example cache" --last 5 \
  -d /path/to/private-exports \
  -o /path/to/private-context.md
```

- [x] Search local conversation text across agents with a literal query.
- [x] Rank matching exchanges and nearby clarifications instead of selecting unrelated latest turns.
- [x] Include session IDs, dates, date provenance, and links to local exports.
- [x] Label excerpts as historical and unverified.
- [x] Keep tool payloads and commentary out of excerpts.
- [x] Write to stdout or an explicitly selected local file.
- [x] Include cleaned section references, selection reasons, and explicit budget omissions.
- [x] Preserve complete turns within a configurable character budget.
- [x] Use synthetic regression tests for topic drift, nearby corrections, ranking, and long deliverables.
- [x] Add an optional structured handoff with cited historical requests, decision candidates, reported blockers, results, and next actions.
- [x] Preserve unclassified source excerpts and exclude shortened fragments from claim classification.
- [x] Keep checked results explicitly unestablished until independent verification exists.
- [x] Link explicit quoted corrections, supersession, and conflicts to matching selected evidence.
- [x] Preserve missing and ambiguous references without choosing authority from dates.

Ranking uses literal matches and English clarification cues. Structured fields use English extraction rules.
Relationship links locate explicit quoted references. Neither format resolves conflicts or establishes verified decisions.
Independent fresh-session evaluation remains open.

### Context Bridge remaining

- [ ] Broaden relationship extraction beyond explicit English quoted statements.
- [ ] Evaluate a handoff in a fresh session before claiming that it prevents repeated explanations.
- [ ] Add optional target formats after checking actual integration requirements.

### Graph and rewind: planned

- [ ] Generate a local HTML graph of sessions and their relationships.
- [ ] Filter the graph by topic, agent, and date.
- [ ] Generate a local activity summary with honest labels for missing data.
- [ ] Use synthetic data for public screenshots, demo recordings, and documentation.

## Phase 5 — Workflow links

- [ ] Link sessions to commits with explicit repository and revision references.
- [ ] Distinguish timestamp-based associations from confirmed commit relationships.
- [ ] Add optional links between sessions and specification files.
- [ ] Add a trace command for sessions, specifications, files, and commits.

## Phase 6 — Semantic search

- [ ] Define a small query dataset and measure retrieval quality.
- [ ] Add a local index for summaries and distilled fields.
- [ ] Add optional transcript chunks for detailed searches.
- [ ] Keep remote embedding providers opt-in.

## Phase 7 — Usage analytics

- [ ] Preserve missing usage as unknown rather than estimating unsupported costs.
- [ ] Separate session elapsed time from active work time.
- [ ] Add configurable model prices with dates and source references.
- [ ] Add topic and project usage summaries.
- [ ] Avoid productivity rankings based only on token counts or elapsed time.

## Phase 9 — Obsidian synchronization

- [ ] Add incremental synchronization with a local state file.
- [ ] Update existing notes without creating duplicates.
- [ ] Add optional topic, project, and weekly index notes.
- [ ] Preserve date provenance and evidence labels in notes.

## Phase 10 — Packaging and release

- [x] Add a descriptive README title, canonical package URLs, discovery keywords, and the declared MIT license file.
- [x] Remove retired script versions, an unused ignore template, and superseded helper code from the current tree.

- [ ] Add a configuration file for source paths and output directories.
- [ ] Add an initialization command with explicit local output destinations.
- [ ] Check installation and CLI behavior on supported Python versions.
- [ ] Review repository contents and Git history for private data before publishing.
- [ ] Publish a release only after release checks pass.

## Execution order

1. Complete ingestion checks and generate a private coverage manifest.
2. Use `doctor` to inspect private exports and `reconcile --dry-run` to review missed or changed exports. Enable scheduling only after review.
3. Evaluate the Context Bridge prototype with a real local handoff.
4. Improve extraction and evidence references.
5. Add workflow links, semantic search, analytics, and Obsidian synchronization as needed.
6. Prepare synthetic demonstrations and release checks.

## Non-goals

- A hosted transcript service.
- Automatic publication of transcripts, reports, or context packs.
- Unrequested edits to agent instructions or project documentation.
- Claims of verified outcomes based only on transcript text.
- Automatic redaction guarantees. Git ignore rules do not sanitize files or remove tracked history.
