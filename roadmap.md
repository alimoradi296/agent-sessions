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

### Remaining

- [ ] Add a scheduled reconciliation command or documented cron/systemd setup.
- [ ] Check hook behavior against supported agent releases.
- [ ] Define support for child-agent transcripts and their parent relationships.
- [ ] Add atomic index updates and concurrent export protection.
- [ ] Surface malformed records and unsupported event types in coverage reports.

### Acceptance criteria

- Every discovered source file has an explicit status.
- Repeated exports preserve history and produce one file per session ID.
- Tool calls retain their arguments, results, and correlation IDs.
- Estimated dates remain visible in exported metadata and reports.
- Tests run without access to developer home directories or private transcripts.

## Phase 4 — More accurate extraction

### Implemented in this change

- [x] Exclude tool payloads, code blocks, quoted text, and common instruction blocks from decision extraction.
- [x] Exclude Codex commentary and analysis from knowledge extraction.
- [x] Remove broad decision patterns based on “instead of” and “do not.”
- [x] Label extracted decisions as candidates and outcomes as unverified in reports and notes.
- [x] Carry date provenance into distilled JSON and Obsidian notes.

### Remaining

- [ ] Define evidence references for each extracted claim.
- [ ] Separate requests, proposals, decisions, reported results, and checked results.
- [ ] Evaluate extraction with a manually labeled synthetic dataset.
- [ ] Improve file and PRD extraction. Mentions do not prove that a file changed.
- [ ] Add optional `distill --llm` with a strict output schema.
- [ ] Require explicit provider configuration before sending transcript data to an API.
- [ ] Support a local model as an optional extraction backend.

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
- [x] Include the latest request and response from each matching session.
- [x] Include session IDs, dates, date provenance, and links to local exports.
- [x] Label excerpts as historical and unverified.
- [x] Keep tool payloads and commentary out of excerpts.
- [x] Write to stdout or an explicitly selected local file.

### Context Bridge remaining

- [ ] Rank relevant turns instead of selecting the latest request and response.
- [ ] Connect conflicting or superseded decisions with their evidence.
- [ ] Add a structured handoff with decisions, blockers, and checked results.
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

- [ ] Add a configuration file for source paths and output directories.
- [ ] Add an initialization command with explicit local output destinations.
- [ ] Check installation and CLI behavior on supported Python versions.
- [ ] Review repository contents and Git history for private data before publishing.
- [ ] Publish a release only after release checks pass.

## Execution order

1. Complete ingestion checks and generate a private coverage manifest.
2. Use `doctor` to inspect private exports. Add atomic writes and scheduled reconciliation.
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
