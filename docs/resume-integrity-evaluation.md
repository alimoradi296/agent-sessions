# Synthetic resume-integrity evidence probe

Evaluation date: October 27, 2026. The six cases and all identifiers are fictional. The probe reads no agent archive, repository index, worktree, process table, network, or external service. Run it with:

```sh
python -m examples.evaluate_resume_integrity
```

## Cases and observed signals

| Case | Status note | Transcript result | Current tree | Proposed result |
|---|---|---|---|---|
| Old running record; prior result and tree match | Running | Success | Matches recorded tree | Stale, completed; do not dispatch |
| Old pending record; prior result and tree match | Pending | Success | Matches recorded tree | Stale, completed; do not dispatch |
| Running record; no live worker or terminal event | Running | None | Differs from expected tree | Unknown; do not dispatch |
| Current generation; worker observed live | Running | None | Differs from expected tree | Active |
| Success event; repository changed afterward | Completed | Success | Differs from recorded tree | Recheck current tree |
| Current terminal result; tree matches | Completed | Success | Matches recorded tree | Completed for that recorded tree |

The note, transcript, and repository columns expose their raw signal, not an independently implemented competitor. A task note cannot identify a stale generation; a transcript success cannot prove the current tree still matches; a matching tree does not show whether a worker is still active. The proposed rule combines task generation, terminal event, worker observation, and repository fingerprint. It returned the authored expected label for all six cases.

## What this supports

The probe makes the required evidence explicit. A safe check needs a stable task identity and generation, a trustworthy lifecycle event, and a fingerprint of the current repository result. A live-worker observation can distinguish some active work. If any required signal is missing, the result must stay `unknown` and must not trigger a rerun or completion claim.

The fixture's `task_generation` means a durable generation assigned by the task authority. It is not Cursor's `generation_id`: Cursor documents that value as changing with each user message. A normal follow-up therefore cannot, by itself, prove the earlier task is stale. A real adapter needs a durable task-store identity or its own task lease/version and must not infer one from a conversation-generation token.

## Synthetic hook-contract probe

Run the docs-shaped payload probe with:

```sh
python -m examples.probe_resume_hook_contracts
```

| Provider event pair | Shared identity in documented fields | Probe result |
|---|---|---|
| Cursor `subagentStart` → `subagentStop` | Start has `subagent_id` and `tool_call_id`; stop repeats task text/status but documents neither ID | A single task can be joined by task-text fingerprint, but identical parallel tasks are ambiguous and return `unknown` |
| Codex `PreToolUse` → `SubagentStart`/`SubagentStop` | Pre-tool has `tool_use_id` and tool input; subagent lifecycle has `agent_id` and turn/session IDs | Start and stop can pair by `agent_id`; the original invocation cannot be linked from these documented payloads alone |

The Codex pre-tool hook can block a supported tool call, but its `SubagentStart` event cannot block a spawn by returning `continue: false`. Cursor's `subagentStart` can deny a spawn. See the [Cursor hook contract](https://cursor.com/docs/hooks) and [Codex hook contract](https://learn.chatgpt.com/docs/hooks). These differences rule out treating the current hook payloads as one shared durable task identity. Task text must not be stored in the ledger; hashing it allows only a weak match and does not solve collisions or paraphrases.

This probe did not install hooks or run either provider. The existing archive parser might supply a missing link, but that would need its own format-level evidence and runtime test. If the transcript-to-hook mapping is absent or unstable, this cross-provider candidate should be dropped rather than guessed.

## What it does not establish

The proposed rule was written against these authored cases, so matching their labels is not evidence of general accuracy. No agent, task board, or hook was run. The probe does not establish hook parity across providers, runtime reliability of task IDs or worker observations, false-alert rate, reduced user effort, user demand, commercial value, or uniqueness. This is a design probe, not a production guard or privacy certification.

## Synthetic transcript-spawn join

Run the authored Codex transcript probe with:

```sh
python -m examples.probe_transcript_spawn_joins
```

The probe joins a parent `spawn_agent` function-call result to a child rollout using only explicit identifiers: parent `call_id` selects the result, its returned `agent_id` matches the child's `session_meta.payload.id`, and the child's `parent_thread_id` must match the expected parent thread. A child `task_complete`, `turn_completed`, or `turn_aborted` record supplies a terminal marker. It checks interleaved siblings, missing calls, absent child IDs, duplicate child IDs, wrong parents, and missing terminal events. Ambiguous or incomplete cases return `unknown`.

This path is supported by [Codex spawn implementation](https://github.com/openai/codex/blob/main/codex-rs/core/src/tools/handlers/multi_agents/spawn.rs), which returns the spawned thread ID as `agent_id`, and [Codex thread metadata](https://github.com/openai/codex/blob/main/codex-rs/thread-store/src/types.rs), which defines `thread_id` separately from the tree-shared `session_id` and stores `parent_thread_id` for subagents. Codex rollout records serialize that metadata. This distinction matters: `session_meta.payload.session_id` identifies the shared tree, while `payload.id` identifies the current thread. The existing parser previously preferred `session_id`, which could merge child rollouts with the root. The parser now keys each rollout by `id` and records explicit `parent_thread_id`. Exported Markdown says “Spawned by,” and the relationship graph uses `spawned_from` for Codex instead of mislabeling the edge as a fork. This authored probe checks the join logic but does not establish that every Codex version or runtime preserves these fields.

Cursor currently remains unresolved. A [staff-confirmed public report](https://forum.cursor.com/t/subagentstop-never-fires-for-background-subagents-documented-summary-modified-files-agent-transcript-path-missing-or-null/166681) describes missing background `subagentStop` events, a null `agent_transcript_path`, and a `subagent_id` that equals the parent tool-call ID rather than the child transcript filename. That is operator evidence from a reported Cursor version, not a universal guarantee. It is enough to reject a cross-provider completion claim until independent runtime evidence establishes a stable Cursor join.

This narrows the next experiment to validating the corrected Codex transcript lineage reader against provider-generated synthetic records, including separate child threads and parent links. It does not yet establish user benefit, distinctiveness, or willingness to pay.
