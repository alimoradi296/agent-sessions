# Subagent output durability screen

Screen date: October 28, 2026. This is a public-source review and one authored synthetic parser probe. No provider session was run, no user was contacted, and no personal archive data was read.

## Reported problem

Claude Code issue [#88621](https://github.com/anthropics/claude-code/issues/88621) reports a more specific case: Claude Desktop displayed “No output captured” for a finished subagent even though a matching transcript existed. The reporter identified a Desktop UI path that did not read agent output files. It was closed as not planned after inactivity. The report names Desktop and CLI versions, but it is not an independent reproduction or proof that the same defect remains in current releases.

Related reports include background results not being viewable like foreground results ([#43829](https://github.com/anthropics/claude-code/issues/43829), closed as not planned) and `TaskOutput` returning raw subagent JSONL instead of a final result ([#17591](https://github.com/anthropics/claude-code/issues/17591), open in the checked page). The latter's author reported partial mitigation in 2.1.47. These reports describe visibility and result-transfer failures across specific versions; they do not establish present prevalence.

## Existing approaches

- [compact-plus](https://github.com/u-ichi/compact-plus) documents transcript backup and a generated state file before compaction, followed by state restoration.
- [compact-handoff-plugin](https://github.com/AnExiledDev/compact-handoff-plugin) documents searchable handoffs, tool ledgers, and handling for subagent compaction. Its documented scope is compaction handoff; it does not establish recovery of a completed Task output that the provider no longer exposes.
- [Tracehouse's local session viewer](https://tracehouse.ai/guides/claude-code-session-history) can open a selected JSONL transcript in the browser without uploading it. Its guide says a separate child transcript must be loaded to inspect subagent work.
- The [Claude transcript parser specification](https://github.com/kfischer-okarin/agent-session-transcript-parser/blob/main/FORMAT-CLAUDE-CODE.md) documents subagent files, while [claude-code-sessions](https://github.com/frederick-douglas-pearce/claude-code-sessions/blob/main/reference/tool-invocation.md) documents the `agentId` link from a parent invocation to its child trace and where to find the final result.
- OpenAI's [reliable agents memory and compaction guide](https://developers.openai.com/cookbook/examples/agents_sdk/building_reliable_agents_memory_compaction) separates working memory from a human-reviewed artifact as the source of truth.

These sources cover compaction, transcript viewing, and the format-level parent-to-child join. They weaken the case for a generic session viewer. It remains unverified whether an automatic, source-cited recovery command for a missing result provides enough value beyond opening the child transcript manually.

## Repository fit

`ClaudeParser.list_sessions()` recursively found both files in the synthetic fixture, but `ClaudeParser.parse()` skipped the child because its records were marked `isSidechain`. The parent parsed, but its synthetic result handle was unavailable. A small isolated extractor then matched the parent `Agent` call's ID to `toolUseResult.agentId`, found the corresponding child file, and recovered one authored final text record. Summary: two JSONL files discovered; parent parsed; one parent tool result; child parser rejected the sidechain; prototype recovered one unique result. The report emitted no synthetic result text.

The expanded synthetic probe passed seven authored controls: recover one uniquely linked completed result; do not recover when the child file is missing, the task failed, no terminal final record exists, the parent link is ambiguous, a nested child owns the result, or an older terminal result is followed by an unconfirmed message. The existing parser still rejects the child sidechain. This confirms code feasibility and conservative behavior only on the probe's authored schema shape. It does not prove compatibility with any current Claude release, real-world format drift, or a competing-tool runtime result. Reproduce with `python -m examples.evaluate_subagent_output_recovery`.

## Decision and next check

Do not build a generic compaction or memory plugin. Keep only the narrow question: can a read-only archive automatically recover a completed subagent's final result when the parent or UI reports it missing, with a verifiable link to the child transcript?

### Manual workflow comparison (October 28, 2026)

The direct workflow is already documented: locate the session and child file, select the relevant transcript in a local viewer, then inspect the delegation, returned result, child records, and parent follow-up. Tracehouse's guide documents parent-to-child expansion when descendants are available and explicitly says a parent summary cannot reconstruct a missing child record. Its history guide says the viewer cannot recover a separate child transcript that was not loaded. The synthetic extractor would automate the file join and select a terminal child result only when its parent link is unique and the task is marked complete.

That is a plausible convenience over manual lookup, but no timing study, runtime comparison, current-version reproduction, or repeated user evidence shows that the saved steps matter. The existing viewer already covers inspection and linkage for available descendants. Therefore close this as a product candidate for now; retain the probe as parser research only. Reopen only if a current provider-generated case demonstrates that the parent-child result is missing in a way existing viewers do not address, and a measured comparison shows meaningful user benefit.

No unique product advantage, current provider defect, repeated need, prevalence, adoption, or willingness to pay is established. The issue report and product documentation are not independent runtime evidence.

## Related but separate: live subagent failure and resumption

Recent Claude Code reports describe a different failure from a missing final result: a background subagent stream can die after a transient network error, then the watchdog kills it without reconnecting or preserving a resumable run ([#87987](https://github.com/anthropics/claude-code/issues/87987), [#88993](https://github.com/anthropics/claude-code/issues/88993)). The authors link earlier reports and repeated incidents, but these remain user-reported cases, not a prevalence estimate or a reproduction on the current release.

Pi now has direct extension coverage for the broad idea. [`pi-durable-subagents`](https://pi.dev/packages/pi-durable-subagents?name=pi-coding-agent) documents a persisted workflow journal, provider rotation, and retrying a call in the same session after transient failures. The [`pi-headless-subagent`](https://pi.dev/packages/pi-headless-subagent?name=compaction) package also documents retries for transient rate-limit, server, and network errors. Anthropic's [Agent SDK dynamic-workflow guide](https://platform.claude.com/cookbook/claude-agent-sdk-08-dynamic-workflows) documents retrying failed stages while reusing completed results, with added cost for rerunning the failed stage. These are documented implementation claims, not independent reliability tests.

This differs from recovering a completed child result from a transcript archive: it requires controlling the live runtime, preserving side-effect boundaries, and knowing whether a retry is safe. Do not turn this repository's read-only history and recovery features into a generic subagent orchestrator. Reopen only for a repeated failure the current provider runtime and durable-subagent tools both miss, with a same-case comparison showing less lost work or spend. No such residual or buyer demand is established here.
