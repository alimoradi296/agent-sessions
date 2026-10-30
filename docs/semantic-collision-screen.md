# Multi-agent semantic integration failure screen

Date: 2026-10-28

## Decision

Do not build a general multi-agent coordination, conflict-prevention, or post-run failure-diagnosis tool. Public reports and research support the existence of semantic integration failures, but direct tools now target intent sharing, conflict warnings, shared state, trajectory diagnosis, failure attribution, and local incident reports. The two-session cross-worktree intersection remains technically untested against current diagnostics products; it is not a product direction and uniqueness is not established.

This is a research hypothesis, not a product direction. No user frequency, willingness to pay, or unique capability is established.

## Public evidence

| Evidence | What it supports | Limit |
|---|---|---|
| [Codex issue #23515](https://github.com/openai/codex/issues/23515) | A user report describes Codex CLI turns failing when working across a base checkout and Git worktree; comments report related failures. | An issue thread is not a prevalence estimate or independent reproduction across current releases. |
| [Claude Code issue #76250](https://github.com/anthropics/claude-code/issues/76250) | A detailed report describes concurrent subagents silently changing a shared working-directory context and cites related worktree-state reports. | Claims and reproductions in one issue thread do not establish general incidence or independent confirmation. |
| [STale semantic coordination benchmark](https://arxiv.org/abs/2609.25396) | Its authors report constructed semantic-interference cases where individually passing patches fail when combined. | In 417 mined Django PR pairs, only one interference remained after correcting grading; constructed-case rates do not estimate ordinary-work frequency. |
| [Foremerge](https://foremerge.com/) | Documents cross-provider intent, semantic-scope, dependency, and changeset coordination across worktrees before changes land. | The project says its checks are heuristic and that it has no published coordinated-versus-uncoordinated benchmark results yet. |
| [Comity conflict detection](https://comity.so/product/conflict-detection) | Documents checks for same-file, symbol, contract, dependency, protected-path, and team-decision conflicts before edits or commands. | Product documentation is not an independent evaluation of detection quality or customer outcomes. |
| [Worktree coordination](https://tryworktree.com/docs/agent-coordination) | Documents shared project threads where people and agents can view, message, steer, or stop work. | The current documentation says a standalone cross-agent MCP coordination service is not released. |
| [TrajAudit](https://github.com/LogAnalysisTech/TrajAudit) | Open source investigator-agent diagnosis for software-maintenance trajectories, with RootSE failure cases and trajectory filtering. | Its benchmark and paper are not an evaluation of this repo's cross-provider two-session case. |
| [AgentRx](https://github.com/microsoft/agentrx) | Open-source framework and benchmark for locating agent failure steps from execution trajectories. | It does not establish demand for another diagnosis tool or the exact cross-session integration outcome here. |
| [AgentDebugX](https://github.com/AgentDebugX/AgentDebugX) | Documents local-first diagnosis, root-cause attribution, recovery, reruns, and portable reports for multiple agent systems. | Project claims do not independently prove accuracy; the overlap is still direct. |
| [agenttrace](https://luoyuctl.github.io/agenttrace/) | Documents local multi-agent history analysis, failure diagnosis, incident timelines, and reports across many agent formats. | Its documentation does not establish detailed cross-session semantic cause attribution, but it makes generic local multi-agent diagnosis a crowded position. |
| [onpath](https://onpath.run/) | Documents local multi-provider event capture, failure detectors, recovery reports, MCP context, and team analytics. | Claims are product documentation, not independent outcome evidence; broad failure monitoring already has direct competition. |

## Possible residual outcome

Existing products primarily coordinate before or during edits. The possible remaining job is different: after two independently executed tasks appear successful but their combined result fails, produce an auditable explanation that links:

1. each agent's source-recorded assumptions and tool activity;
2. each change and its source session;
3. the first combined test failure and the exact integration point; and
4. uncertainty where logs do not establish causality.

This repository already reads local histories from multiple coding agents and has source-linked inspection and captured-change analysis. That is a reason to investigate the fit, not evidence that the capability works or is unique. Foremerge and other tools can prevent or surface many mismatches, while TrajAudit, AgentRx, AgentDebugX, agenttrace, and onpath cover adjacent trajectory diagnosis and local incident reporting. The synthetic packet described below is not yet compared against those systems, and may be only a small specialization of an existing job.

## Local capability check

Read-only source inspection found useful building blocks, but no current end-to-end diagnosis:

| Existing component | Current documented/code behavior | Missing for this hypothesis |
|---|---|---|
| Claim extraction (`agent_sessions/analysis/claims.py`) | Labels selected statements and binds them to transcript message or export coordinates. The module explicitly does not check truth. | Does not infer an agent's code-level assumption or compare assumptions across sessions. |
| Relationship linking (`agent_sessions/analysis/relations.py`) | Links exact quoted corrections or conflicts when the references are uniquely located. | Does not detect unquoted semantic/API conflicts or relate them to code changes. |
| Source inspection (`agent_sessions/analysis/inspection.py`) | Tracks hashes and changes in one session's exported dialogue. | Does not build a cross-session causal timeline or cite changed code and CI output. |
| Captured file recovery (`agent_sessions/analysis/captured_files.py`) | Reconstructs selected captured patch operations and correlates tool results when available. | Does not establish current Git integration or prove that a session's action caused a later combined test failure. |

So the current repository cannot yet deliver the proposed report by composing existing commands. It would need a new cross-source data model and a conservative way to associate session evidence, code states, and verification results. Whether that additional work can improve a user's decision enough to justify a product remains unknown.

## Synthetic probe

Two synthetic Claude sessions worked in separate Git worktrees. Agent A changed `get_user()` from a string to a dictionary and updated its service assertion. Agent B changed a client to uppercase the returned string and updated its own assertion. Each branch's local assertion passed. Both changes were committed in separate files and merged without a textual conflict. The combined client check failed with `AttributeError: 'dict' object has no attribute 'upper'`.

The repository's Claude parser preserved both requests, both assistant statements, and both exact edit calls. `claims_from_session` returned no claim labels for the assumption statements, and `find_relations` produced no cross-session relationship. Git reported no conflict. This demonstrates a synthetic gap between raw source preservation and automatic diagnosis; it does not show that users encounter this often or that a diagnosis product would be valuable.

| Baseline | Probe result | Evidence limit |
|---|---|---|
| Git merge/conflict detection | Both separate-file changes merged cleanly; it did not flag the type mismatch. The combined assertion failed. | This is one authored Python case, not a broad test of Git or semantic tools. |
| This repository's parser and current analysis | Preserved the synthetic statements and tool inputs, but returned no assumption label or cross-session relationship. | No incident report was generated; a reviewer could manually compare the raw statements and failure. |
| Foremerge coordination | Its public documentation says it shares declared semantic intents and can warn on symbol/contract collisions before edits. | Foremerge was not installed or run. Whether it catches this particular pair depends on agents declaring the relevant intents; its live detection quality is unverified here. |

## Next gate

Do not implement the local incident packet yet. First compare this synthetic case against the actual diagnosis capabilities and input requirements of TrajAudit, AgentRx, AgentDebugX, agenttrace, and onpath. Current public documentation establishes substantial adjacent capability, but not comparative performance on this exact multi-session example. Reopen only if a measured cross-session result materially improves source coverage, correctness, review time, or privacy over those tools. Until then, close the general failure-diagnosis lead and continue screening a different outcome category.

Only after that synthetic advantage is shown should public issue/changelog research look for repeated instances of the exact failure. Public reports alone do not establish a buyer. Keep all probes wholly synthetic and temporary; do not include private session data or local paths in repository artifacts.
