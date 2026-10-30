# Concurrent coding-agent runtime isolation screen

**Date:** October 28, 2026

**Status:** screened out as a generic product lead; no runtime comparison or demand study performed.

## Problem signal

Git worktrees isolate files, but do not by themselves isolate databases, development servers, ports, caches, environment state, or service processes. Public reports describe agents switching back to a main checkout, concurrent worktree setup races, shared local databases being overwritten, and uncertainty about which agent is waiting for a person. These are individual reports, not estimates of frequency or market size. See [Claude Code issue #64315](https://github.com/anthropics/claude-code/issues/64315), [Cursor forum report](https://forum.cursor.com/t/multi-agent-mode-loose-worktree-and-apply-undo-apply/149072), [Claude Code issue #47266](https://github.com/anthropics/claude-code/issues/47266), and the [multi-agent runtime-collision discussion](https://www.reddit.com/r/AI_Agents/comments/1v53mns/running_multiple_coding_agents_in_parallel_broke/).

## Direct competition

- [workz](https://github.com/rohansx/workz) documents per-worktree environment and dependency setup, ports, database and Compose isolation, process cleanup, stale-worktree cleanup, conflict inspection, and hooks for coding-agent hosts.
- [fed](https://www.service-federation.com/docs/isolation/) documents per-directory containers, volumes, state, parameterized-port allocation, worktree lifecycle commands, and coding-agent setup guidance.
- [AgentSlots](https://github.com/hishamalward/agentslots) documents attaching selected ports, database and queue resources to existing worktrees, plus pause, lease, heartbeat, and cleanup controls.
- [Trellis](https://trellis.dev/docs/) documents worktree-scoped terminals, processes and logs, service supervision, Claude and Codex sessions, session inbox, and local trace/log workflows.

These are vendor or project descriptions, not independent runtime validation. They nevertheless overlap the proposed outcome closely enough that another generic worktree environment manager is not a supported wedge. A claim that no other repository can do this is false on the public evidence reviewed.

## Decision

Do not add runtime isolation, port assignment, per-worktree databases, environment provisioning, agent coordination, or process cleanup to this repository as a product feature. Keep the issue reports as possible regression scenarios only. Reopen only if a specific current-version failure remains after using the closest available tool, a same-case comparison demonstrates an important outcome those tools miss, and target users confirm repeated costly impact and willingness to pay.

**Not established:** prevalence, defect rates in current releases, comparative product quality, buyer identity, adoption, or willingness to pay. No personal session data or private archives were used.
