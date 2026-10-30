# Supervisory work and coding-agent task switching screen

Screen date: October 28, 2026.

## Signal

The workplace shadowing study [Developers as Managers of AI Agents](https://arxiv.org/abs/2610.33588) observed 11 professional developers across approximately 15 hours. It reports that participants spent an average of 33.4% of observed time formulating prompts or checking agent responses; observed task-switch rates ranged from 0 to 101.6 per hour. The authors describe three patterns: direct supervision, delegation with dialogue, and learning with agents.

This is a useful signal that agent work includes supervision and coordination. Its small, short observation sample does not establish population prevalence, a specific unsolved task, user time loss attributable to switching, or buyer demand. The study's reported range also cautions against treating all developers as having the same workflow.

## Existing coverage

- [VS Code agent sessions](https://code.visualstudio.com/docs/agents/run/overview) documents following agent tool calls, output, questions, and approval requests, then reviewing results before integration.
- [Microsoft Scope](https://microsoft.github.io/scope/introduction/what-is-scope/) documents running the same coding task across different agents and comparing artifacts, activity, criteria, and reports.
- [Paperclip](https://paperclip.app/product/) documents task ownership, plans, review stages, and verification evidence for agent teams.
- [runshift](https://runshift.ai/docs) documents coordination across coding-agent harnesses, with agent status, task outcomes, cost tracking, and trust gates.

These are product-documentation claims, not independent tests of effectiveness or proof of adoption. Together they make a generic supervision dashboard, agent manager, or task-switching view a poor product bet for this repository. This screen does not establish that every costly supervision problem is solved.

## Decision

Do not build a generic supervision dashboard, task dispatcher, orchestration layer, or agent-activity monitor. Reopen only around a repeated, costly supervision failure that these current tools do not address, demonstrated on real user workflows with a same-case comparison and measured outcome. No such failure, unique advantage, prevalence, adoption, or willingness to pay is established here.

Keep all real agent histories, personal paths, and user-specific work out of this public repository. Future public examples must be synthetic.

## Narrower residual checked: unattended-run spend and recovery

Recent Claude Code issue reports describe an agent continuing to consume usage after the user believed it had stopped, a stale “Running” indicator after the work was gone, and background agents killed after a no-progress watchdog timeout without preserving work. These are issue reports with one reporter and related issue links, not an independent frequency estimate. One report is closed as not planned; another as completed. Their issue status does not establish current behavior in the latest release.

Existing coverage includes Claude's own agent view for background work, [AgentLoops](https://docs.agentloops.dev/how-to/limit-spending/) for per-agent and daily spend limits, and its [background-work view](https://docs.agentloops.dev/how-to/watch-background-work/) for seeing and stopping supported shells/subagents across its clients. Its docs state that only runtimes which report their background work appear there, currently Claude and Codex. [Tourniquet](https://tourniquet.dev/) provides Anthropic API spend caps; [onpath](https://onpath.run/) provides local stall and repeated-failure monitoring; [codex-task-watchdog](https://github.com/TanChuping/codex-task-watchdog) provides Codex progress evidence and a safe recovery boundary; [amux](https://amux.io/demos/self-healing-watchdog/) describes session restart and replay. These products use different control surfaces and runtime contracts. The coverage gap for a native provider remote session that is not surfaced to the current client remains untested; a tool cannot independently stop work or reconcile cost without access to its control plane.

Do not build a generic budget monitor, stall detector, or auto-restart controller. A narrower candidate would have to reconcile provider-reported remote task state with real spend after logout/relaunch, then recover work safely when a stalled task ends. The repo has no provider control-plane integration; public reports do not show that third-party access can observe or stop hidden remote runs. This is an unresolved product boundary, not a validated opportunity. No gap, prevalence, unique capability, or willingness to pay is established.
