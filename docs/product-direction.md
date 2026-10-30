# Product direction and comparison

This document records product hypotheses and comparisons, not proof of demand or uniqueness. Current evidence supports no active product wedge.
The first users are solo engineers with multiple coding agents and people who research agent history.

### Shipped infrastructure MVP (October 28–30): cited session-family continuation workflow

**Built:** `agent-sessions family` is now a one-command continuation workflow over exported archives:
lineage digest, continuation signals, pin suggestions with command templates, requirements materialization (`--requirements-out`), one-command handoff bundle (`--bundle-out` + `--audit-family-bundle`), profile presets (`balanced`/`questions`/`blockers`/`strict`), signal filters, priority controls, and `--require-signal-kind` gates that refuse bundle generation when critical signals are missing. Synthetic demo covers the full path. User docs: [family-digest.md](family-digest.md).

**Intended user outcome:** After a fork or spawn, a solo engineer can recover related sessions, see carry-over constraints/questions, and generate an auditable handoff bundle without manually opening every transcript or writing pin commands by hand.

**Evidence behind the choice:** Existing `link` needs distillation and does not cite dialogue. Pi documents tree navigation inside its own session files; this repo already stores Claude `forkedFrom` and Codex `parent_thread_id` as export `parent_id`. Competing lineage browsers (`ah`, Agent Trail, AgentsView, `codex-threads`) cover broader native trees. The MVP therefore completes export-side continuation infrastructure rather than claiming a new product category.

**Known gaps:** No native Pi message-tree parsing; missing parents are reported only; quotes/signals are cleaned-dialogue heuristics; no live process status; no measured time savings; no buyer or willingness-to-pay evidence.

**Next validation gate:** With authorized private exports only, check whether one real fork/spawn continuation decision changes when the gated one-command family workflow is available versus `search`/`link` alone. Do not treat synthetic pass rates as demand.

### Context at the moment of an agent decision (screened October 28; no active product lead)

The proposed job is to explain a bad coding-agent action using the exact model request that preceded it: what instructions and tool results reached the provider, what was compacted or truncated, and what repository state the action changed. This is narrower than browsing transcripts or collecting generic traces. The user outcome would be faster diagnosis of whether an agent made a poor decision from complete evidence or acted on incomplete/stale context.

There is a credible problem signal, but not demand evidence. Pi's extension API exposes `before_provider_request`, session branch state, and session entries; a public Pi package, [pi-provider-trace](https://github.com/Dwsy/pi-provider-trace), already records provider payloads and Pi lifecycle events. Anthropic's [Claude Code OpenTelemetry documentation](https://platform.claude.com/docs/en/manage-claude/opentelemetry) describes recording request messages in content mode. Its [official cookbook](https://platform.claude.com/cookbook/observability-opentelemetry-tracing) says large content spans are truncated by dropping earlier messages and the system prompt. These capabilities make raw prompt capture and trace viewing table stakes.

The Pi-only case has been tested with Pi 1.4.0 and `pi-provider-trace` 0.1.1 against a synthetic local endpoint. A request-time change removed one constraint from the provider payload while the saved session retained it; the fake provider then produced a matching file change. The existing trace captured the altered payload and session events, and the changed file confirmed the outcome. The combined Pi baseline was sufficient to explain this authored case. See [the synthetic comparison](context-at-decision-evaluation.md).

The cross-agent version is also a weak product hypothesis. [AgentPlay](https://github.com/Entelligence-AI/agentplay) documents local session maps and timelines across Claude, Codex, Cursor, Copilot, OpenCode, Kiro, Gemini CLI, and Antigravity. [Microsoft's Grafana guide](https://learn.microsoft.com/en-us/azure/managed-grafana/grafana-opentelemetry-app-insights) documents a multi-agent telemetry pipeline for Copilot, Claude, Codex, OpenClaw, OpenCode, and Gemini CLI, with content capture options that vary by client. Pi's provider trace and Claude's and Codex's own telemetry add request-level evidence for those clients. These are distinct products and configurations, not one proven universal system, but they cover enough of the proposed workflow that a missing integration is not a product gap by itself. No runtime comparison across the combined stack, analyst-time study, buyer check, or willingness-to-pay evidence was done. Close this feature direction; reopen it only for a specific current incident that those tools cannot explain and target-user evidence that a simpler local workflow is worth paying for.

An October 27, 2026 study sharpens the technical question: it reports that coding-agent instruction stacks change across releases, and that a system prompt or model name alone does not fully describe the model input ([arXiv:2610.37332](https://arxiv.org/abs/2610.37332)). The proposed product angle would be release-aware capture and comparison of the effective instruction stack, tied to observed actions and repository changes. It is not established as a usable solo-engineer workflow: the study instrumented agents to capture first requests; end-user access to full hidden prompts varies or is unavailable. Existing tools already document broad overlap—[EvalKit](https://syntropylabs.ai/docs/coding-agents/vendors) documents full prompt/reply capture for several coding-agent clients, and [Capsule](https://docs.capsulesecurity.io/guides/agent-management) documents collecting loaded instruction files and some exposed system prompts. These are vendor capability descriptions, not independent comparisons, and they do not prove that either product versions hidden stacks or explains behavior changes. Still, the access constraint and adjacent coverage make a new product claim premature. Do not implement a prompt-stack recorder or another trace viewer; reopen only if a real target user can provide the relevant stack and a same-case comparison shows a concrete outcome current tools miss. No user frequency, distinctive result, or willingness to pay is established.

### Withdrawn candidate: preserve failed-verification evidence across a resumed task (October 27)

The [SWE-Residual preprint](https://arxiv.org/abs/2610.25899), submitted October 19 and marked under review, reports 198 residual states from 111 tasks. Across its evaluated agents, success fell by 20.6–53.5 percentage points on DeepSWE and 20.6–34.9 points on Terminal-Bench compared with clean starts. On DeepSWE, 58.9–88.2% of failed residual runs ended with the same tests still failing. These are benchmark results, not estimates of how often this happens in normal development. The authors publish the [benchmark and harness](https://github.com/userljz/SWE-Residual); reproducing the benchmark is not our product opportunity.

The product question was whether a local, source-cited continuation check could carry an earlier failed command and its result into the next session, then distinguish it from a fresh result. This candidate is now withdrawn after competitive review.

A synthetic parser-shape probe confirmed that all three parsers preserve supplied call IDs, arguments, results, and source lines when those fields exist in authored records. That does not prove provider exports always contain complete evidence. A [Cursor staff response](https://forum.cursor.com/t/accessing-the-full-agent-transcript-in-cursor/157311) says native JSONL transcripts omit tool outputs and suggests a `postToolUse` hook for separate capture. Native Cursor history therefore cannot be assumed to support this feature.

The [Aether Agent command reference](https://github.com/AetherAI3/Aether-Agent/blob/main/COMMANDS.md) documents verification-backed handoffs for tasks run in its own runtime. More directly, [deja-vu](https://github.com/vshulcz/deja-vu) documents cross-agent indexing of local histories, task-state and passed-check summaries, plus lookup of prior commands and what happened after a matching error. Together these cover both prospective and retrospective forms of the idea. The remaining difference—source-linked extraction from a particular archive format—is not by itself user value. Do not implement this candidate unless a concrete user-reported failure remains unsolved by these tools and a baseline comparison demonstrates an actionable benefit. No real-world prevalence, demand, or uniqueness is established.

### Rejected alternative: repository-policy audit

The [SWE-CC preprint](https://arxiv.org/abs/2610.06193) reports policy violations in evaluated contribution tasks and publishes deterministic checkers for repository rules across agent trajectories and final artifacts. [RepoComplianceBench](https://arxiv.org/abs/2607.26819) coded 455 contribution rules from 102 communities; in its 106-instance benchmark, unaided refusal and human-handoff compliance were zero for each tested agent. This is a strong behavior signal, but it is a benchmark result, not evidence of real-world violation frequency or customer demand. The paper also reports that disclosure and verification improved substantially with reminders or rule excerpts, while refusal and handoff remained difficult.

Existing mechanisms overlap the likely product response: [no-autopilot](https://github.com/eljojo/no-autopilot) and [Codex Guard](https://github.com/marketplace/actions/codex-guard-pr-quality-gate) provide pull-request checks; [Knox](https://github.com/qoris-ai/knox) and [agentctl](https://github.com/itslab42/agentctl) provide cross-agent hooks or policy enforcement. An adoption study of popular GitHub projects reports a median of one to two agent-authored PRs per repository over three months, with intensive use concentrated in a small subset; that sample does not represent private enterprise development. Keep this as a parked problem signal. Do not build a generic policy audit, contribution gate, or hook layer. Reopen only if a specific high-volume maintainer workflow remains uncovered by those controls and shows a measurable reduction in policy-violating submissions or review effort.

### Rejected alternative: authority-set approval integrity

The [authority-set integrity preprint](https://arxiv.org/abs/2610.15137) reports that, in its 20-repository corpus, 296 of 542 commits that changed an input to a reviewed workflow left the entrypoint unchanged. The share was concentrated: three repositories accounted for 203 of those 296 commits, and one contributed 130. Its agent experiments also found inconsistent file-set selection for one Terraform deployment. This is a specific, technically meaningful approval gap, but the corpus does not establish how often it causes production incidents or whether buyers will pay.

There is already a direct open-source proof of concept, [ShadowInputs](https://github.com/adarsh-singh106/shadowinputs), for hashing reviewed local inputs and rejecting drift. Its author explicitly limits it to partial static dependency discovery and an unsigned manifest; it does not guard a real deployment. GitHub's [workflow dependency lockfiles](https://docs.github.com/en/actions/concepts/security/workflow-dependency-lockfiles) cover transitive external action dependencies, and GitHub's [CodeQL guidance](https://codeql.github.com/codeql-query-help/actions/actions-untrusted-checkout-toctou-critical/) recommends executing the reviewed commit to close the checkout race. These controls do not solve every standing-approval or local agent-command case, but a generic authority-set scanner would duplicate existing work and require a new deployment-security product surface outside this repository's core. Do not implement it here. Reopen only around a named deployment tool and buyer workflow where an independently derived input set plus immutable execution measurably improves on its native plan and approval controls.

### Rejected alternative: skill effectiveness analytics

[skill-evals](https://github.com/maxvandenhoven/skill-evals) and [agent-skill-eval](https://github.com/tardigrde/agent-skill-eval) document cross-harness skill evaluation; [Skill Runtime Intelligence](https://github.com/hellogxp/skill-runtime-intelligence) describes evidence-graded activation and outcome reconstruction across agents and runs. This directly covers the candidate of determining which installed skills activate and help. Do not build generic skill analytics or lifecycle tracking.

### Rejected alternative: generic stale-rule and skill-conflict checks

The [One Skill Too Many study](https://arxiv.org/abs/2610.11647) reports that similar co-installed skills can displace an intended skill and suppress its exclusive requirements, even when task completion still passes. The authors' synthetic study also reports that a first-read hook can improve fidelity. This establishes a research result, not real-world incident frequency or buyer demand. Direct tools already document static conflict review: [Agensi](https://www.agensi.io/skills/skill-conflict-detector) compares Claude Code skills, instruction files, and hook scripts; [context-audit](https://swipe.md/tools/context-audit) inventories instructions across Claude Code, Codex, Cursor, and Kimi; and [`review-skills`](https://github.com/tomzx/agents/blob/main/skills/review-skills/SKILL.md) checks skill duplication and composability. A separate [stale-instructions study](https://arxiv.org/abs/2610.30571) reports that one user-level sentence substantially changed results in its 40 synthetic projects, so a checker is not necessary for that demonstrated mitigation. Runtime skill selection and lost-requirement evidence could be a narrower distinction, but [Skill Runtime Intelligence](https://github.com/hellogxp/skill-runtime-intelligence) already documents activation and outcome analysis. Correction-to-rule learning is also directly covered: the [TRACE study](https://arxiv.org/abs/2606.13174) compiles user corrections into runtime checks; [Tellonce](https://github.com/YujunZhou/tellonce), [Reflexio](https://www.reflexio.ai/docs/coding-agents), and [Pathrule](https://www.pathrule.io/) document persistent correction or project-rule workflows. These are research and product claims, not independent quality or sales evidence, but correction learning is not a distinct gap for this repository. The [AgentPluginZoo study](https://arxiv.org/abs/2609.23809) reports overlapping capability names across public plugin bundles, but its corpus does not establish user incidents or buyer demand. The [Agent Plugins standard](https://agent-plugins.org/plugin-authors/skills) defines portable package layout, while [agent-skills' setup check](https://github.com/azmym/agent-skills) already documents cross-category skill, plugin, and rule overlap auditing. Building plugin inventory and composition analysis here would add a separate local configuration scanner without an established connection to session export or a distinct buyer workflow. No uncovered workflow is established; do not add generic conflict scanning, correction mining, plugin auditing, or skill dashboards.

### Rejected alternative: agent-linked code durability dashboards

The proposed product outcome was to tell a team which agent, model, or configuration produced changes that survived later maintenance. This is already directly served by [Git AI](https://usegitai.com/docs/team-usage/data-schema), which joins sessions and line attribution to PR churn, rework, and review outcomes; [DX](https://docs.getdx.com/reports/ai-code-overview/), which compares AI-attributed PR outcomes including rework and reversions; [Ballast](https://ballast.now/), which scores repository durability from Git history; and [Hokusai](https://hokus.ai/), which markets post-merge rework-risk scoring and model matching. [Codethrift](https://codethrift.ai/) also markets model/harness configuration comparisons across cost, speed, and defects. These are product descriptions, not independent evidence of accuracy, adoption, or revenue.

There is a commercialization signal in this category: [Git AI](https://usegitai.com/for-teams) documents a free open-source attribution client alongside a commercial teams/enterprise platform, with self-hosting requiring a license ([licensing](https://usegitai.com/docs/team-usage/self-hosting)). [Hokusai](https://hokus.ai/) describes Model Match as live and Rework Risk as early access. This shows a plausible open-core/team-sales model exists in the broader category; it does not prove customer count, realized revenue, or willingness to pay for this repository. Because the outcomes directly overlap, this is market evidence to learn from, not a reason to build a competing dashboard.

Research offers a more specific interpretation of maintenance cost. [SWE-Maintain](https://arxiv.org/abs/2610.14768) reports 5.6 percentage points lower later-task resolution when agents build on their own earlier changes across its evaluated episodes. The difference grows when all earlier tests must pass, and disappears when inherited tests pass and the later task is not already solved; the authors attribute the main cost to earlier failing tests rather than a measured code-maintenance disadvantage. This does not prove the same effects in ordinary repositories, but it weakens a generic “agent code rots” pitch. A product decision beyond attribution, rework, durability, and test-health gating is not established.

## Competitive reset (October 27)

The broad claim that transcript-based file recovery is distinctive is withdrawn. Public project documentation already describes:

| Project | Documented overlap | Remaining boundary in this comparison |
|---|---|---|
| [codex-recover](https://github.com/agustif/codex-recover) | Codex file reconstruction from patches, shell writes, and full reads; exact, partial, patch-only, deleted, and unresolved outcomes; evidence manifests and isolated ZIP output | Its README describes Codex rollout inputs. It does not document reconstruction from Claude and Cursor together. |
| [claude-file-recovery](https://github.com/hjtenklooster/claude-file-recovery) | Claude transcript replay, point-in-time recovery, tool-result correlation, diffs, and batch extraction | Its README describes Claude Code sources. It does not document Codex and Cursor recovery together. |
| [Cursor checkpoints](https://docs.cursor.com/en/agent/chat/checkpoints) | Restore the workspace to a checkpoint in the Agent conversation and track agent changes | The official guide describes in-product checkpoint recovery; it does not document an offline restore from retained native transcripts after the checkpoint UI is unavailable. |
| [Cursor Cloud MCP](https://cursor.com/docs/cloud-agent/capabilities#cursor-cloud-mcp) | Lists visible Cloud Agent runs and fetches transcripts, tool calls when available, and diff metadata for prior runs | Directly covers Cloud Agent history access. The docs describe diff metadata, not file diffs or deterministic project-file reconstruction. |
| [SessionArk](https://github.com/julescules/sessionark) | Integrity-first snapshots, consistency checks, byte-preserving salvage, and isolated restore for Claude Code and Codex continuity stores | Its README targets session-store corruption and resumability, rather than reconstruction of arbitrary project workspaces from tool operations. Runtime behavior was not tested here. |
| [ectype](https://github.com/chaybits/ectype) | Reads, filters, redacts, exports, and transfers native conversation sessions across ten coding agents and three chat apps | Its README documents broader provider coverage and session portability; it does not establish project-file reconstruction from tool evidence. Runtime behavior was not tested here. |
| [cacli 0.2.4](https://pypi.org/project/cacli/0.2.4/) | Recovers direct Claude/Codex file operations and literal apply-patch text in recognized shell-command records; emits reviewable patches and stops at unreconstructable mutations | Static inspection and a synthetic run of its pinned extraction module found that its Codex `custom_tool_call` path does not recognize a tool named `exec` as a shell command. On the exact synthetic nested-wrapper case, that module emitted no action; this repo's restore CLI recovered the literal file bytes and reported execution and latest state as unknown. A second synthetic native `response_item` envelope with a direct patch was also not recognized by that module. This is a bounded parser difference, not a user-valued advantage. The full cacli package and CLI were not installed or run. |
| [Agent History (`ah`)](https://github.com/nihen/ah) | Cross-agent discovery, search, browsing, resume, and MCP across eight agents, including Claude, Codex, and Cursor | Its README describes history access; it does not document project-file reconstruction. |
| [Magents](https://github.com/abnegate/magents) | Shared session bus for Claude Code, Codex, Cursor, and other agents; transcript search, memory, handoff, file-touch lookup, and cross-session messages | Its README documents broad cross-agent coordination and session access. Runtime completeness and trust properties were not independently tested. |
| [Hermes Agent](https://github.com/NousResearch/hermes-agent) | File tools track reads and file versions, warn about stale writes, and coordinate file state across concurrent tasks inside the Hermes runtime | Directly overlaps stale-observation and cross-agent file-state control within Hermes. This repository has not tested Hermes or established a gap across separate agent runtimes. |
| [Pi Ensemble](https://github.com/sztlink/pi-ensemble) | Local shared workspace coordination with agent claims, handoffs, audit history, and a Pi extension plus CLI adapters | Directly overlaps coordination across agents sharing a checkout. Its documented boundary does not establish file-version-bound observation freshness. |
| [Atlas](https://github.com/pacifio/atlas) | Local multi-agent workspace with shared memory, history capture, file changes and patches, session-to-commit checkpoints, transcript import, and secret scrubbing | Its README documents the exact combination of shared agent context and project change history that weakens our cross-agent state hypothesis. It describes history and checkpointing, not a verified restore flow for arbitrary project trees. Runtime behavior and customer demand were not independently verified. |
| [agent-files](https://github.com/ericpardee/agent-files) | Shared project memory for Claude Code and Codex, with automatic session ledgers and cross-session recap | Its README describes a small, local-first implementation of shared cross-agent memory; it does not establish source-anchored file-version freshness. |
| [AICTX](https://aictx.org/) | Repo-local operational continuity across agents, including current goal, next action, failures, validation evidence, and stale-state quality signals | Direct overlap with the proposed next-action and continuity workflow; its public site does not establish comparative performance or commercial demand. |
| [AI Project Board](https://github.com/hpigu/AIProjectDashboard) | Local task coordination for Claude Code and Codex, with dependency-aware claims, blockers, and verification/commit evidence | Direct overlap with roadmap progress and evidence-backed completion; its README documents a board workflow, not retrospective source reconstruction. |
| [cot.](https://cot.run/docs) | Self-hosted observability with local hooks for Claude Code, Cursor, Codex, and other agents | Direct overlap with local multi-agent event capture and dashboards; it does not by itself establish source-verified historical conclusions. |
| [agent-monitor](https://github.com/Halo-Welt/agent-monitor) | Hook-based live local panel across Cursor, Claude Code, Codex, and agents supporting command hooks | Direct overlap with cross-agent local event capture; documented panel behavior is not a state-reconciliation comparison. |
| [Recall](https://github.com/H-XX-D/recall-memory-substrate) | Pushes typed memory into every turn, marks contradictions and stale beliefs, and can hold a turn open until flagged memory is consulted | Strong overlap with automatic, contradiction-aware continuation and turn gates. Its README describes a broad memory runtime, not a public-diff scan against private archives. |
| [projmem](https://github.com/m4ll0k/projmem) | Grounds project memory in code, revalidates it, and refuses tool calls that violate project rules across several coding agents | Strong overlap with source-grounded constraints and action gates. Its README does not establish scanning staged text against private transcript corpora. |
| [coding-agent-flight-recorder](https://github.com/spiatrenka/coding-agent-flight-recorder) | Locally analyzes agent sessions against the repository, including unbacked completion claims and unverified edits | Direct overlap with post-hoc agent forensics; it does not document private-transcript-to-staged-diff matching. |
| [Agentmine](https://agentmine.io/overview/) | Local transcript corpus, search, extracted facts, and agent-facing recall across a broad set of coding agents | Its documented scope overlaps generic archive search and memory; the current source page does not establish operation-by-operation project recovery. |
| [Agent Sessions](https://github.com/jazzyalex/agent-sessions) | Local-first macOS browser for search, analysis, and resume across 16 agent histories, with a local index | Its documented scope overlaps browsing, search, and continuation; it does not establish the exact nested-wrapper recovery behavior measured here. |
| [SessionFolio](https://sessionfolio.com/) | Local Mac app for unified prompt/code/tool-output search and one-click session resume across Codex, Claude Code, and OpenCode; currently free during alpha | Direct consumer overlap on the simple solo-developer job of finding and resuming a past session. Its current alpha offer does not establish future pricing or adoption. |
| [Sessions Viewer](https://sessions-viewer.js-bridge.com/) | Free, MIT-licensed desktop app for Windows, macOS, and Linux; reads, searches, exports, and resumes local histories across seven listed coding agents, with additional project and tool management | Direct overlap on local multi-agent history browsing and continuation. Its public feature page does not establish adoption or willingness to pay. |
| [Coding Agent Sessions History](https://marketplace.visualstudio.com/items?itemName=Methodox.coding-agent-sessions-history) | Local VS Code extension for Claude Code and Codex: search, bookmarks, stats, export, and terminal resume | Direct overlap for users who want session history inside their editor; its published scope is narrower than universal multi-agent support. |
| [agent-history](https://github.com/d3layd/agent-history) | Local cross-agent semantic search and automatic verbatim context injection from prior sessions | Direct overlap with automatic history recall. Its README does not establish whether injected constraints are checked against changed or superseding source evidence. |
| [deja-vu](https://github.com/vshulcz/deja-vu) | Local memory and cross-agent search, automatic recall at session start and before tools, with promoted `rejected`, `superseded`, and `stale` lifecycle states surfaced in retrieval | Direct overlap with cross-agent, lifecycle-aware recall. Its documented lifecycle is not a runtime comparison with our task-level requirement gate. |
| [statelessagent](https://github.com/sgx-labs/statelessagent) | Documents source hashes, `validated`/`stale`/`contradicted`/`unknown` trust states, and trust-aware retrieval that tags uncertain context | Direct overlap with provenance and stale-context handling. Its changelog does not establish equivalent requirement-coverage and ready-state gates; inspect behavior before making that distinction. |
| [dejavu knowledge reference](https://github.com/AlohaYos/dejavu/blob/main/docs/REFERENCE.md) | Notes carry accepted/proposed/superseded status and can be marked stale when code changes | Direct overlap with lifecycle-managed knowledge. Its documented scope is a project memory and Obsidian workflow, not a measured cross-agent requirement handoff. |
| [contextberg/agent-history](https://github.com/contextberg/agent-history) | Cross-agent history, links to Git commits, commit knowledge, and MCP handoff | Its README does not document reconstruction of project files from agent transcripts. |
| [Hansard](https://www.hansard.dev/getting-started/how-it-works/) | Provider-neutral archives, file and commit history, tool-operation records, and recovery of selected memory files from archived operations with explicit history gaps | Strong overlap with cross-agent history and file provenance; its memory-recovery description does not establish recovery of arbitrary project trees from every provider. |
| [SessionVault](https://github.com/rush-skills/sessionvault) | Backup and restore of transcript stores from dozens of agent products | Its README describes store backup and restore, not replaying project-file operations into a historical project tree. |
| [Session-Bench](https://jazzyalex.github.io/agent-sessions/bench/) | Scores session-format signal, completeness, stability, openness, and tooling across agent harnesses | It measures source-session quality, not the value of this repository's handoff or restoration workflows. |
| [Handover continuity benchmark](https://handover.sh/research) | Reproducible comparison of continuation-critical information in transcripts, compressed memory, and structured handoffs | Its published pilot is small and first-party; it still overlaps directly with our proposed handoff evaluation. |
| [agent-eval](https://github.com/fitchmultz/agent-eval) | Transcript-based cross-provider usage evaluation, static reports, and synthetic calibration | The repository is archived and unsupported; its published scope still overlaps with our evaluation/reporting branch. |
| [Pi coding agent](https://github.com/earendil-works/pi) | Native session branching and branch navigation | Branch history is a different operation from recovering project files from other agents' transcripts. |
| [pi-codemode-diff 0.1.5](https://pi.dev/packages/pi-codemode-diff?name=pi+codi) | Captures and displays diffs for successful nested Pi `edit`/`write` calls, persists display metadata, and supports Pi codemode plus an optional OpenCode codemode tool | Its package documentation excludes bash/Python/external writes and calls the feature visibility tooling rather than undo, backup, or byte-exact recovery. This is real overlap with nested-operation evidence; it is not evidence of cross-agent archive recovery. We reviewed its published package description, not source or runtime behavior. |
| [AgentXRay](https://www.npmjs.com/package/@alloevil/agent-xray) | Reads local coding-agent traces and links tool calls, background exits, and checks to source records using deterministic evidence rules | Direct overlap with execution-evidence reading and handoffs. Its package documentation does not claim live monitoring, automatic repair, or completion judgment. |
| [Agent Action Capsule](https://agentactioncapsule.org/) | Describes signed, privacy-preserving action capsules with an independent witness and offline-verifiable evidence | Direct overlap with tamper-evident evidence and audit handoff. Its site says it is early and not a turnkey compliance product; source behavior and customer demand were not tested here. |
| [Tracekit](https://github.com/Cygnux-Labs/Tracekit) | Describes a signer between agents and tools, policy gates, tamper-evident records, and witness levels; includes coding-agent hooks | Direct overlap with independent action capture. Its README notes that without an independent witness, an operator can rewrite the log. We reviewed the published README, not source or runtime behavior. |
| [AgentUndo](https://github.com/peaktwilight/agent-undo) | Local filesystem snapshots, session attribution, reversible restore, and line-level provenance | Direct overlap with file recovery and provenance. Its local watcher and project-state design does not establish resistance to a same-user agent modifying that state; this is a threat-model boundary, not a tested exploit. |
| [vct-core Codex parser](https://docs.rs/vct-core/latest/src/vct_core/session/codex.rs.html) | Source includes a test where `custom_tool_call(name="exec")` contains nested `tools.apply_patch`; it deliberately records the whole input as one shell cell and reports no edit | This is an analytics parser, not a recovery product. It documents one implementation that does not descend into this wrapper shape, not a market-wide gap. |
| [agenteval](https://github.com/lukasmetzler/agenteval) | Lints agent instruction files, harvests tasks from Git history, runs several coding agents, and compares/regression-checks results | Its documented input is Git and instruction files; extraction of source-bound correction episodes from local transcripts is not established. |
| [agent-belt](https://github.com/jfrog/agent-belt) | Runs reproducible multi-turn scenarios against installed coding-agent CLIs in isolated worktrees | Scenarios are authored as scenario files; automatic creation from private history is not established. |
| [agentslog](https://github.com/MohammadYusif/agentslog) | Indexes Claude Code sessions and records a lesson after a command fails repeatedly, then warns future sessions | This overlaps with learning from history; the documented capability is Claude-focused and command-failure-based. |
| [TRACE](https://arxiv.org/abs/2606.13174) | Research pipeline mines user corrections, turns them into atomic rules, and compiles those rules into runtime checks | This is close to the proposed correction-learning workflow; its evaluated scope and product availability differ, but the core idea is not unique. |

| [Chub secret scanning](https://chub.nrl.ai/guide/scanning) | Agent-aware secret scanner for Git history and staged diffs, with a documented pre-commit hook | Direct overlap with an agent-specific publication gate for credential leaks. |
| [Agent Scrub](https://github.com/thesubtlety/agent-scrub) | Local scanning and redaction of secrets in coding-agent prompts, transcripts, tool output, and saved memory | Direct overlap with private-history secret cleanup; its documented surface is history files. |
| [redact-transcripts](https://github.com/crossvault/redact-transcripts) | Local redaction of secrets and personal data from agent transcripts and JSONL logs | Direct overlap with transcript sanitization before sharing. |
| [Agent Trace Privacy Scrubber](https://github.com/JacobLinCool/Agent-Trace-Privacy-Scrubber) | Local review flow that redacts secrets and optionally classifies PII before packaging traces for sharing | Direct overlap with preparing agent traces for publication; the documented flow includes manual review. |

These are boundaries in the checked documentation, not proof that no implementation or newer project exists.
Generic multi-agent session discovery, search, recall, handoffs, shared project memory, and local event dashboards are
crowded capabilities; Magents, Atlas, agent-files, cot., agent-monitor, and the entries above make that boundary
concrete. Do not position this project by the number of parsers or supported transcript formats.
The proposed provider-neutral recovery case is withdrawn as a differentiator: Hansard and cacli already cover
important parts of cross-provider history, file provenance, and transcript-based edits. No product capability
in this repository is currently established as unique or commercially valuable.

The pinned `cacli 0.2.4` wheel was downloaded to a temporary directory and its published SHA-256
(`abe2209a04a0deb56cda299d1ef1e103a13ded51f46137fc95c23674d6e0f245`) matched the PyPI release record.
Static inspection found that `custom_tool_call` dispatch recognizes shell names `bash`, `shell`,
`exec_command`, and `command_execution`, but not `exec`. A synthetic run of the wheel's standalone extraction
module confirmed that a nested literal patch under `exec` yielded no action. The same module did not recognize
the repo's native `response_item` envelope in a direct-patch fixture. This repo's restore CLI recovered one
synthetic nested `Add File` exactly and marked both execution and latest state unverified. No archived operation
was run, and the full cacli package or CLI was not installed or executed. These results compare two synthetic
record shapes; they do not establish superiority across real projects, commercial value, or uniqueness.

### Closed product lead: agent-secret blast radius in Git history

Generic multi-agent search, injected memory, stale-state labels, source provenance, and tool-call gates already
appear in [agent-history](https://github.com/d3layd/agent-history), [deja-vu](https://github.com/vshulcz/deja-vu),
[statelessagent](https://github.com/sgx-labs/statelessagent), [Recall](https://github.com/H-XX-D/recall-memory-substrate),
and [projmem](https://github.com/m4ll0k/projmem). The source-cited handoff remains useful infrastructure, but current
evidence does not support it as this repository's differentiated product.

The previous pre-publication text-overlap candidate is not a current product direction. Existing tools cover staged and
repository-wide disclosure scanning, while transcript-to-code attribution is also available. Any new proposal must show
an incremental outcome against those combined baselines, not just detect a secret or identify an agent session.

Existing tools cover adjacent parts: [Chub](https://chub.nrl.ai/guide/scanning) documents staged Git scanning and a shared secret-rule engine for transcript redaction; [Agent Scrub](https://github.com/thesubtlety/agent-scrub) scans and redacts secrets in local history; [redact-transcripts](https://github.com/crossvault/redact-transcripts) redacts secrets and personal data; [hooprs](https://github.com/hoophq/rs) scans local Claude, Cursor, and OpenCode sessions for PII and secrets; and [Skarn](https://getskarn.com/research/ai-session-secret-exposure/) documents multi-agent session risk analysis and cross-session secret correlation. New direct/adjacent coverage is now documented by [prepublish-guard](https://pypi.org/project/prepublish-guard/), which checks repository files and full Git history for secrets, personal data, local paths, and configured confidential terms; [AgentSweep](https://github.com/Ishannaik/agent-sweep), which scans local histories across many agent products and provides a pre-commit hook; [Agent Guard](https://github.com/jeongjaesoon/agent-guard), which documents Claude Code and Codex hooks plus fail-closed staged-line scanning through its native pre-commit hook; and [Confessor](https://github.com/ninjahawk/Confessor), which reconstructs sensitive-read-to-network-call paths from Claude session logs. These are published project claims, not runtime comparisons or proof of adoption.

The screened hypothesis was **local secret-to-code blast-radius lineage**: after an agent reads a sensitive value from a local file, determine whether the value—or a common reversible encoding of it—reached committed code, and point to the destination file, line, and commit without printing the secret or transcript. [GhostCommit](https://labs.cloudsecurityalliance.org/research/csa-research-note-ghostcommit-image-prompt-injection-ai-code/) is a controlled research PoC in which an agent encoded `.env` contents as integer constants that conventional credential-pattern scanners did not recognize. It is not a confirmed production incident or prevalence estimate.

The category has serious overlap. [Skarn](https://getskarn.com/) scans local multi-agent histories, links sensitive reads with later activity, and markets paid Pro/Team controls. Its [editions page](https://getskarn.com/editions/) lists a paid annual per-developer Team tier with a five-developer minimum. This confirms a commercial product proposition, not verified sales. Its published risk research uses an authored synthetic corpus and is not a prevalence measure. The current public [Skarn scan example](https://getskarn.com/) demonstrates a secret read in one agent, later use in another, and encoded data flowing to a network command; this is stronger evidence of cross-session and encoding-related coverage than the older guard-event documentation alone. [ctx blame](https://ctx.rs/blame/) maps changed lines to agent sessions with transcript citations, and [nicknisi/sessions](https://github.com/nicknisi/sessions) correlates a file, line, or commit to sessions. [AgentLogs](https://agentlogs.ai/) links sessions to Git commits and scans transcripts before upload; [DeepBlame](https://github.com/deepblame/deepblame) traces changed lines to agent runs. [agent-blast-radius](https://github.com/0xelitesystem/agent-blast-radius) reconstructs file, Git, and network side effects from transcripts. These cover the main pieces of the proposed incident workflow. Before a same-case comparison, public descriptions did not establish whether a tool linked a specific transformed session secret to the exact committed destination line. That documentation gap motivated a bounded synthetic comparison; lack of documentation was not treated as proof of a product gap.

#### Published-baseline synthesis (October 27)

Source review sharpened the combined baseline, but did not replace a runtime comparison. Skarn's public report sample shows masked findings for a sensitive-file read, secret echo, cross-agent taint-linked use, and encoded data sent through a network command; its measured precision work uses a curated synthetic corpus and separately says its binary/source method is not independently reproducible. [DeepBlame's README](https://github.com/deepblame/deepblame) documents prompt, tool-call, and edit capture, then line-level attribution to an agent and prompt. Together, these documented capabilities could let an analyst notice a suspicious session and locate agent-authored lines. The cited material does not show automatic correlation of a secret read from tool output, its integer-tuple transformation, and the exact committed destination line. This is a documentation gap only: runtime behavior, manual analyst effort, and whether that join matters to buyers remain unknown. The incremental proposition is therefore limited to a verified, masked cross-source correlation that saves incident-triage effort over running and reading those tools together. Do not build until an isolated synthetic comparison establishes that result and a real buyer signal exists.

The original synthetic overlap probe supports exact/case/spacing text matches and two authored prompt-to-diff links. A separate AST-based probe links one synthetic UTF-8 integer tuple from a tool-result secret to its exact committed file line and commit; the literal matcher, user-prompt matcher, and small credential regex miss it, while one benign tuple does not link. The secret is not emitted. This validates one implementation mechanism, not realistic detection quality or a market gap. A later combined October 28 synthetic run found that Gitleaks 8.30.1 detected the raw fake token in `.env` but not its encoded destination; Skarn 0.33.0 reported five session incidents, including a dotenv read, but no destination line or attack chain; and DeepBlame 0.5.0 attributed the generated line from an authored Agent Trace record without linking the sensitive read. This is one artificial fixture, not evidence of general tool limitations. A human may join those outputs, but reviewer effort and decision impact were not measured. Keep post-incident blast-radius mapping closed as a product lead; retain the probe as research. Reopen only if a realistic comparison demonstrates lower analyst effort and a decision-changing outcome beyond current tools. No adoption or willingness-to-pay evidence is established.

#### Incident signal check (October 27)

Two recent sources confirm that the threat shape deserves attention, but they support different claims. LiteLLM's [canonical incident report](https://docs.litellm.ai/blog/security-incident-oct-21-2026-attack-chain) says an agent-platform master key was committed to a public repository on May 27 and not revoked; a later compromise used it to obtain a GitHub organization owner's token and ultimately publish a poisoned release. This is a confirmed incident involving an agent configuration secret and severe downstream impact, but it does not document an agent transforming that secret into committed source code. ASSET Research Group's [GhostCommit disclosure](https://asset-group.github.io/disclosures/ghostcommit/) demonstrates that narrower transformation path: a vision-enabled coding agent encoded `.env` bytes as an integer tuple in source, which ordinary secret scanners missed. It is a controlled research demonstration, not a production incident or frequency estimate.

GitGuardian's [2026 report](https://www.gitguardian.com/state-of-secrets-sprawl-report-2026) reports roughly twice the baseline secret leak rate in Claude Code co-authored public commits, based on its analysis of public GitHub commits. This is category-level signal from a security vendor's dataset, not evidence of demand for local archive lineage or willingness to pay for this repository's product. The combined runtime baseline now has one synthetic case; it does not establish prevalence, analyst-time savings, or demand. Do not turn these incident reports or isolated probes into a product claim.

The synthetic check is recorded in [archive-disclosure-evaluation](archive-disclosure-evaluation.md). It exercises the existing Claude, Codex, and Cursor parsers, then scans staged additions in disposable Git repositories. Matching all roles found exact and case/spacing-altered prompt text, but also flagged shared public wording and permitted code from assistant messages; it missed a reworded statement and short unregistered text. Restricting matches to user-role messages removed those two assistant-origin false alerts in this fixture while retaining the exact and case/spacing cases. The report now binds those two detections to a source-message fingerprint and exact staged-file line without emitting source text. That filter also excludes tool output and assistant content, where sensitive data can appear. Manual registered values and a small credential-pattern rule caught separate authored cases. This establishes source-to-diff linkage on authored fixtures only, not incremental product value against the published baseline. Review burden was not measured.

An October 28 synthetic matrix additionally linked seven authored Python literal/common-encoding forms from a fictional sensitive tool result to exact committed lines and rejected three controls. This expands mechanism coverage only. A separate combined Gitleaks/Skarn/DeepBlame run on one synthetic case found no exact source-to-destination link in their combined outputs, but the controls do not estimate false-positive rates and reviewer effort and buyer demand remain unknown.

The pinned Gitleaks runtime comparison is complete for one synthetic case. It found the raw token in `.env`, not the encoded destination; Skarn reported session exposure and a dotenv read; DeepBlame attributed the destination line from an authored trace. The exact join remains a technical residual in this fixture, but incremental decision value, reviewer-time savings, realistic performance, and buyer demand are unestablished. Keep this lead closed; do not implement based on the one-case gap.
Do not claim a privacy guarantee, uniqueness, adoption, or willingness to pay from synthetic controls.

An October 28 competitive refresh adds direct forensic overlap: [AgentDFIR](https://github.com/efij/AgentDFIR) documents attack chains including sensitive-read-to-upload and injection-to-commit/push, plus an offline decoder for executed payloads; [Chronicle](https://getchronicle.dev/) reconstructs code state at each imported session message and includes a secret scan; and [GitHub Secret Protection's MCP tools](https://docs.github.com/en/code-security/how-tos/use-ghas-with-ai-coding-agents/scan-for-secrets-with-github-mcp-server) scan changed files and staged diffs before commit. These sources do not demonstrate the exact transformed-value-to-committed-line join, but they cover the surrounding security decision. With no measured reduction in analyst work or buyer evidence, close this as a product lead; retain the synthetic probe as research only.

The nested-wrapper comparison is complete for the selected synthetic records. Do not expand recovery coverage from
this parser difference alone. Neither recovery nor the project-intent candidate establishes external adoption or
willingness to pay.

Do not describe nested-operation diff visibility as a unique capability: `pi-codemode-diff` already documents
successful nested edit/write diffs and persisted display metadata for Pi and optional OpenCode codemode. Its published
scope does not establish byte-exact recovery, arbitrary shell-write capture, or cross-agent archive recovery. The
remaining question is whether history-to-regression-case preparation adds measurable value after these existing
recovery, diff, and eval tools are included in the comparison. The `cacli` source result above does not establish
that our nested-wrapper behavior is a durable advantage across other tools, source formats, or real tasks.

### Independent trace integrity: problem confirmed, wedge withdrawn

The paper [LLM Agents Can Easily Tamper With Their Own Traces](https://arxiv.org/abs/2609.30266) reports trace
tampering in tested full-access harnesses and recommends independent interception. This is research evidence for a
serious problem, not a customer-demand measurement or a proof about every current harness.

[AgentUndo](https://agent-undo.com/papers/agent-undo-paper.pdf) already documents continuous local filesystem capture,
content-addressed snapshots, session attribution, rollback, and blame. That overlaps substantially with file
provenance and recovery. Its paper describes a per-project local state directory and a hook-written session marker;
it does not establish resistance to a same-user agent that can modify or delete that state. The exact threat boundary
requires source-level and runtime comparison. This is an inference from the published design, not a verified exploit.

AgentUndo covers local file provenance and rollback; Agent Action Capsule and Tracekit already document independent
or witnessed action evidence; AgentXRay covers deterministic evidence reading from existing logs. These products
overlap enough that a generic “trusted agent recorder” is not a defensible wedge. Their public descriptions do not
prove equivalent implementations or customer adoption, but they invalidate a claim that this problem area is empty.
Do not build a generic recorder without a specific interoperability gap and evidence that users need it.

### Withdrawn candidate: generic execution-state freshness

The paper [Turning Interaction History into Execution State](https://arxiv.org/abs/2608.00808) reports improved
task success and lower cost when an online ledger tells a coding agent what it has observed, modified, and attempted,
then checks actions before execution. This is a stronger value signal than archive search: it ties history to fewer
stale observations and repeated actions, with benchmark results. It remains a paper result, not proof this repository
can reproduce the gains or that buyers will pay.

The paper's results are not evidence that this repository's users have this problem. Repeated calls or retries in
a transcript do not, by themselves, prove stale observations, wasted work, or user pain. Any private archive review
must remain local; source text, paths, identifiers, outcomes, and counts do not belong in this public repository.

Hermes Agent now documents read tracking, file-version checks, stale-write warnings, and cross-agent file-state
coordination within its runtime. This directly covers the generic stale-state problem that motivated the earlier
hypothesis. Do not build a competing generic ledger. Any remaining cross-runtime gap must be demonstrated from
independent source evidence and compared against current alternatives before prototyping.

Pi's current [extension contract](https://pi.dev/docs/latest/extensions) exposes pre-execution `tool_call` events
that can block calls, post-execution `tool_result` events, and tool-execution lifecycle hooks. [Pi Ensemble](https://github.com/sztlink/pi-ensemble)
already uses Pi extensions alongside file-based CLI coordination. Hooks are an integration surface, not a
differentiator. A new extension would need to prove a user-relevant outcome that Hermes, Pi Ensemble, and native
client features do not already provide.

### Agent lifecycle hooks are documented across current clients

The [Claude Code lifecycle documentation](https://support.claude.com/en/articles/14554000-claude-code-power-user-tips)
describes `SessionStart`, `PreToolUse`, `PostToolUse`, `Stop`, and `PostCompact` hooks. The [Codex hooks guide](https://learn.chatgpt.com/docs/hooks)
describes `PreToolUse`, `PostToolUse`, `PreCompact`, `PostCompact`, `Stop`, and other events. [Cursor's hooks guide](https://prod.cursor.com/docs/hooks)
documents pre/post tool, shell, MCP, file, prompt, and session hooks, including allow/deny decisions before some actions.
Pi documents pre-tool interception and post-tool results above. These are documentation checks, not runtime tests.

Therefore a recorder, context injector, or generic file-version ledger is a crowded direction. The remaining
question is whether a specific failure across *different runtimes* survives comparison with Hermes, Pi Ensemble,
and native client capabilities. Current local evidence and public documentation do not establish such a gap,
customer demand, or willingness to pay. Do not prototype this direction without a source-backed failure and a
demonstrated advantage over those existing workflows.

## Current decision (October 27)

Keep focused historical lookup as the default for small questions.
The [repeated-use control](raw-evidence-handoffs.md#repeated-investigation-control-october-27)
retains the same expected evidence through full-source inspection with substantially less text.
Raw-evidence handoffs remain available for explicit retention requirements;
reader performance and commercial benefit remain unproven.

The existing bounded investigation is isolated text-project restoration from surviving tool evidence.
It is an implementation capability under evaluation, not the product's claimed differentiator.
Reuse the existing recovery parser and editor instead of adding another interpreter.
The [scoped compatibility prototype](regression-tool-comparison.md#scoped-editor-bridge-prototype-october-27)
restores the authored checkout correctly and retains the two demonstrated uncertainty cases.
All 43 upstream runtime tests pass, while arbitrary shell effects and latest-state certification remain unsupported.
No production recovery feature is enabled.

[Captured file restoration](captured-file-restoration.md) adds one narrow command for complete `Add File` strings
nested inside an outer `exec` record. A synthetic CLI comparison confirmed exact recovery of the supplied bytes
while keeping execution and latest-state status unknown. Private archive outcomes, counts, and identifying paths
are excluded from this public product direction. This establishes behavior for one synthetic wrapper shape, not
historical completeness, independent correctness, a universal uniqueness claim, or commercial demand.

The bounded nested-wrapper comparison is complete for these synthetic records. Do not extend recovery coverage from
this result alone. The current competitive scan also found direct products for cross-agent session sharing, memory,
task progress, and session-store backup: [Magents](https://github.com/abnegate/magents),
[Atlas](https://github.com/pacifio/atlas), [AICTX](https://aictx.org/), [AI Project Board](https://github.com/hpigu/AIProjectDashboard),
and [SessionArk](https://github.com/julescules/sessionark), alongside provider-specific project recovery tools.
The remaining narrow question is whether after-the-fact recovery of project edits from already-existing native
histories solves a real failure that Cursor checkpoints, session-store backups, and existing recovery tools do not.
This is not established; compare the full workflows before extending the restore command. Keep original sources
read-only and restored files outside Git. Do not substitute regenerated plausible code for original bytes.

Cross-agent session sharing and roadmap progress are not current product candidates: multiple tools document those
workflows, including shared memories, task claims, handoffs, and evidence-backed completion. A documentation scan
does not establish their runtime quality or customer demand, but it is enough to reject generic continuity as a
uniqueness claim.

The [capture persistence prototype](capture-delivery-controls.md) remains separate and unintegrated.
Do not build another collector without a demonstrated source-availability need.
Distinct capability, adoption, and willingness to pay remain unestablished.
The reports below are evidence history, not simultaneous implementation commitments.

### Pi refresh and historical branch limits (October 27)

The current [Pi extension documentation](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/extensions.md)
exposes context transforms, persistent session entries, and active-branch reconstruction.
It cautions that abandoned branches represent alternative histories.
These are documented contracts, not runtime measurements in this project.
They rule out treating context hooks or durable session state alone as a new mechanism.
The old Pi `docs/session.md` URL returned 404 during this check; a forked copy is not evidence of current upstream behavior.

That comparison exposed a concrete retention gap here.
The Codex parser kept surrounding conversation but discarded `thread_rolled_back` events.
The [upstream protocol](https://github.com/openai/codex/blob/main/codex-rs/protocol/src/protocol.rs)
defines the legacy marker and its reported number of removed user turns.
Exports now retain the payload as a historical System message with source coordinates.
The marker can be required and audited through evidence-view handoffs.
No earlier messages are deleted or declared active, and coverage still reports unsupported replay.
Cleaned dialogue excludes System messages, so use evidence view when this marker matters.
Three authored controls test ordering, repeated events, and required handoff retention.
This fixes missing context for investigation; it does not establish branch replay, exclusive capability, reader benefit, or demand.

### Fresh recovery-demand check (October 27)

A read-only `git ls-remote` check of [codex-recover](https://github.com/agustif/codex-recover)
returned HEAD `7fe5e66fe7d07f427adf83a08ad6508704a1337e`, the revision already exercised here.
The local source still matches the documented probe fingerprint.
This refresh checks revision identity, not another runtime run or every upstream branch.
The recorded selector and cross-file controls remain reasons to defer that integration.

Two October 21 Cursor reports refine the problem rather than prove a general history-loss incident:

- In [the missing-history report](https://forum.cursor.com/t/agent-chat-history-missing-after-restart-titles-new-agent-history-shows-only-current-chat/175609), support describes workspace identity and existing cross-workspace search. The reporter's successful recovery is not established in the inspected thread.
- In [the Cloud Agent workspace report](https://forum.cursor.com/t/urgent-assistance-required-missing-cursor-cloud-agent-sessions-and-development-workspace/175669), the reporter later confirms finding the historical conversation. Workspace recovery remains the problem; support reports no accessible restorable machine snapshot.

These are public participant reports, not reproduced incidents or pricing feedback.
Conversation availability, exact source reconstruction, Git object recovery, and binary restoration are separate outcomes.
A transcript exporter cannot claim to restore an unavailable machine or absent binary bytes.
No private participant identifiers or project artifacts were copied into this repository.

The current [Cursor Cloud security documentation](https://prod.cursor.com/docs/cloud-agent/security) distinguishes
the recycled runtime workspace, VM snapshots retained for 30 days of inactivity, and conversation state containing
tool calls, diff context, and demo artifacts that is kept indefinitely by default. The [Cloud Agents API](https://prod.cursor.com/docs/cloud-agent/api/endpoints)
documents tool-call arguments/results and truncation flags. Its run stream is scoped to one run and does not replay
prior runs; after the stream retention window, clients are directed to read terminal run state instead.

However, Cursor's built-in [Cloud MCP](https://cursor.com/docs/cloud-agent/capabilities#cursor-cloud-mcp) can list
visible Cloud Agent runs and fetch transcripts, diff metadata, setup logs, and run events for prior run IDs.
Non-admins can fetch only their own runs; admins are limited to repositories and environments they can access.
The documented diff metadata reports whether code changed and how much; it is not a file diff. Transcripts include
tool calls only when available. This built-in workflow may remove the need for a separate capture service.

#### Enterprise OpenTelemetry trace lead

Cursor's [OpenTelemetry overview](https://prod.cursor.com/docs/enterprise/opentelemetry-export) describes a separate,
Enterprise-only export to a team-managed collector. Conversation content and Tool I/O require team opt-in and
destination toggles. The overview says `cursor.conversation.tool_io` includes arguments and results for every
finished Cloud Agent builtin and MCP tool call, joined by `cursor.tool_call.id` and conversation/turn IDs. It also
says records arrive after a turn and must be ordered by record timestamp. Each side is capped at 8 KiB, scrubbed,
and can be marked `cursor.conversation.content_truncated`; a valid JSON body can still be incomplete. Binary fields
are omitted, and secret/personal-data scrubbing is best-effort.

The linked [wire reference](https://prod.cursor.com/docs/enterprise/opentelemetry-export/wire) conflicts with that
scope: it says `tool_io` is Grok Bot only and describes MCP calls rather than Cloud Agent builtin file operations.
Both pages were inspected on October 27, 2026. Until Cursor resolves the conflict with a versioned contract or
official Cloud Agent example, the shape and availability of Cloud Agent file-operation records are not established.
The Enterprise setting was not enabled or tested here, and no Cursor account or API was accessed.

This is a better source lead than transcript browsing, but not yet a recovery capability. Even if the overview is
correct, truncation, scrubbing, missing records, and omitted binary data can prevent exact restoration. Do not claim
that a trace archive reconstructs a project until synthetic shape checks and an independent file/behavior check
show exactly which operations can be restored and which must be refused. If the source conflict remains unresolved,
stop this candidate rather than inventing a payload schema.

The selected [Cursor Chat Recovery](https://github.com/cpeoples/cursor-chat-recovery) project documents
workspace/chat-history remapping and local database backup, not reconstruction of project files from Cloud Agent
transcripts. That is one bounded comparison, not proof that no other repository can do it. No Cursor account or API
was accessed.

**Next bounded recovery question:** when the original Cloud VM snapshot is unavailable, do the transcripts returned
by Cloud MCP retain stable, complete file-change bytes that a deterministic tool can reconstruct and independently
verify? The public docs do not specify the transcript response schema or guarantee those bytes. Compare any exact
recovery workflow with Cursor's native MCP, Git/PR recovery, and existing provider-specific tools before building an
adapter. Preserve unknown execution and latest-state claims.
Keep recovery from historical text separate from regenerating a plausible replacement that passes newly written tests.
The public report motivates this task; unique capability and willingness to pay remain unproven.

The generic Cloud trace-recovery wedge is withdrawn. [Rewind](https://github.com/agentoptics/rewind) documents OTel import, forking/replay, regression baselines, and whole-workspace snapshots; [agent-replay](https://github.com/clay-good/agent-replay) documents OTLP ingest and time-travel replay. These are README/source claims, not runtime comparisons here. A future adapter would need a specific gap in these existing workflows and an actual user need.

Long-running goal persistence is also table stakes: [Cursor documents `/goal`](https://cursor.com/docs/agent/overview#goals-with-goal) and [Projects](https://cursor.com/docs/agent/projects), while [goal](https://github.com/secemp9/goal) and [Context Task Planning](https://github.com/excitedhaha/context-task-planning) document durable objectives or cross-session continuation. Do not claim generic goal persistence as the product distinction.

[The restored-project control](regression-tool-comparison.md#restored-project-behavior-october-27) now carries the selector mismatch into a runnable two-module checkout. Archive integrity passes with both files labelled exact, but prices are swapped. Ordinary replay with the existing editor yields the intended behavior. This is a behavioral recovery failure for the pinned tool, while the baseline still weakens the case for a new engine here.

[The existing-editor bridge](regression-tool-comparison.md#existing-editor-bridge-prototype-october-27) now repairs the observed selector behavior through a small compatibility adapter. The restored synthetic checkout behaves correctly and 38 upstream runtime tests pass. Missing-completion filtering and move-source uncertainty remain unresolved. This supports reusing an existing editor, while production recovery and commercial advantage remain unestablished.

## User problem

A useful handoff must retain critical constraints across sessions.
Literal search and summary budgets can omit a correction that does not repeat the current query.
A receiving agent can then lack evidence that limits its next action.

Public reports describe lost review-before-implementation constraints in [Claude Code](https://github.com/anthropics/claude-code/issues/23776).
Another report describes completed plans that return as active work in [Codex](https://github.com/openai/codex/issues/38931).
These reports motivate the problem. This repository did not independently reproduce those incidents.
The reports do not establish current bug status or willingness to pay.

The proposed workflow is:

1. Find a conversation passage across agents.
2. Pin a scope restriction, correction, or unresolved question.
3. Build a cited handoff with a requirements gate.
4. Audit retained evidence against current exports before use.

The first implementation runs locally with the Python standard library.
It uses no model, account, remote provider, or agent configuration change.

## Related tools reviewed

Review date: October 25, 2026. Public documentation can change.
Documented behavior does not establish runtime behavior.

| Tool | Documented capability | Design lesson |
|---|---|---|
| [Pi](https://github.com/earendil-works/pi/tree/main/packages/coding-agent) | Extensible agent harness with multiple integration modes | Keep the core small and expose explicit integration points |
| [CASS](https://github.com/Dicklesworthstone/coding_agent_session_search) | Unified local search across coding-agent histories | Search alone does not establish a distinct product |
| [Agent Session Search](https://github.com/benvenker/agent-session-search) | CLI and MCP retrieval with bounded evidence | Return inspectable source references and bounded text |
| [BeforeDone](https://github.com/rrrrrredy/beforedone) | File-bound verification receipts and completion gates | Evidence freshness and receipts already have implementations |
| [Qarinah](https://qarinah.io/docs/cross-agent-handoffs/) | Cited cross-agent context with stale and conflicting evidence | Cited handoffs and freshness alone do not establish uniqueness |

These tools overlap with this repository.
This review does not establish that they lack pinned evidence requirements.
No claim that this repository offers an exclusive capability is justified yet.
The later [lossless-compression comparison](review-scaling-results.md#existing-lossless-compression-mechanisms) also finds existing reference-based deduplication and recovery.
A pinned execution and a small JSON envelope recover the authored literal-marker controls, so that boundary does not establish a commercial distinction either.

### Public reliability reports checked on October 26

Public CASS issues supply concrete failure reports, but their latest activity changes the opportunity assessment:

| Report | Evidence boundary |
|---|---|
| [Health disagrees with search, #396](https://github.com/Dicklesworthstone/coding_agent_session_search/issues/396) | Closed; the maintainer reports fixing hard-open failures while distinguishing derived readiness from a real query |
| [Repeated semantic re-embedding, #394](https://github.com/Dicklesworthstone/coding_agent_session_search/issues/394) | Closed; comments report a no-change shortcut, and later activity links a delta-embedding change |
| [Large-archive startup hang, #395](https://github.com/Dicklesworthstone/coding_agent_session_search/issues/395) | Closed; later analysis corrects the initial attribution and reports bounded startup-query fixes |

These are reporter and maintainer statements, rather than independent reproductions in this project.
An issue title alone is not evidence of a current defect or an unmet product need.
The reports motivate measuring the complete local command path, including refresh and storage access.
They do not justify claiming a new health checker, incremental indexer, or session browser as an exclusive capability.

### Complete-command scale control

Before the fresh-index optimization, the dialogue-search CLI was measured with 1,000 synthetic sessions and 40,000 initial messages on October 26.
After appending one message, Markdown source files totalled 12,511,666 bytes.
Each measurement starts a new Python process and includes startup, source refresh, query execution, and JSON output.

| Command state | Elapsed seconds | Sources re-indexed |
|---|---:|---:|
| First index and query | 6.0207 | 1,000 |
| Unchanged query, first repeat | 0.1759 | 0 |
| Unchanged query, second repeat | 0.1777 | 0 |
| Unchanged query, third repeat | 0.1747 | 0 |
| Query after one source append | 0.1896 | 1 |

All queries returned the constructed target.
The final refresh indexed 40,001 passages and retained the other 999 source entries.
These are one local sequence's observations, rather than performance thresholds or a comparison with another tool.
The first command has no existing search index; operating-system caches were not controlled.
This measures dialogue search, not evidence-view search, model quality, memory use, or multi-gigabyte compatibility.

Reproduce with an isolated synthetic archive that is removed when the command finishes:

```sh
python3 -m examples.evaluate_retrieval --scale --sources 1000 --messages 40
```

The probe validates expected passage and refresh counts instead of accepting a fast but incomplete operation.
No performance rewrite is justified by this scale point alone.
[The subsequent mixed-size measurement](search-scale-results.md) exposed unnecessary deletion scans during fresh indexing and records the bounded optimization.

[Qarinah proof context](https://qarinah.io/docs/proof-carrying-context/) also documents budgeted packets and hash-based packet checks.
The comparison must therefore examine required-quote failure behavior, not the presence of citations or hashes alone.

[The synthetic tail-restriction probe](context-selection-probe.md) records one actual `compileContext` run against a pinned Qarinah revision.
The source restriction disappeared from that API output even with space remaining in the packet.
This repository retained it or rejected readiness under its explicit requirements workflow.
That is a measured mechanism difference, not an exclusive-capability or product-superiority claim.

The extended probe then recovered the entire source through Qarinah's public full-recall API using its compiler citation.
One call at 6,000 characters retained the restriction; two pages recovered it at a 3,000-character per-call limit.
The concatenated text exactly matched the source, with consistent source hashes.
Context recovery is therefore not an exclusive capability here.
The remaining hypothesis concerns the value of explicit required-evidence gates and review maintenance, not unique access to source text.
An actual continuation comparison must include full recall before drawing product conclusions.

## Historical evaluation: requirements-gated handoffs

This is a completed mechanism investigation, not the current product focus. The comparison below does not establish user advantage, adoption, or willingness to pay.

The candidate distinction is an inspectable handoff requirements workflow for existing local exports.
It detects an omitted required quote before the receiving agent consumes the handoff.
It also provides a repeatable way to study context loss without a model service.

Requirements now distinguish unrelated source updates from changes to complete selected evidence.
Explicit quoted challenges in another indexed session reopen review even when the pinned file remains unchanged.
Operator notes preserve both statements without inferring authority or correctness.

The synthetic demonstration must show:

- A relevant constraint that a query-only pack omits.
- A requirements gate that fails under an insufficient budget.
- A complete pack that retains every pinned anchor.
- An audit that detects a changed source or handoff.
- Reported results that remain unverified throughout.

These checks establish mechanism behavior only.
They do not establish reduced rework, adoption, or willingness to pay.

[The review trigger evaluation](review-burden-evaluation.md) exposes an important limit in 17 author-labeled synthetic cases.
Both modes detected only four of nine intended challenges.
Project scoping reduced unnecessary reviews from two to one across eight labeled nonchallenges.
A ready pack still missed paraphrased and multilingual challenges.
Explicit operator links now retain known challenges without recognized relationship wording.
Both passages remain mandatory evidence, and the operator interpretation requires review.
This handles known misses without improving automatic detection or proving that users find unknown challenges.
Visible scan limits and review effort take priority over additional search features.
The topic inspection queue now exposes in-scope sources with no current operator inspection note, including nonmatching conversations.
Reading or rebuilding does not clear it, and source changes make previous notes stale.
This provides a path to inspect unknown challenges without claiming semantic detection or guaranteed discovery.

[The inspection replay](inspection-volume-evaluation.md) measures displayed dialogue volume in one authored repeated-use scenario.
Following full-view recommendations displayed 99 sections, compared with 147 complete pending-source sections.
The initial queue still required all 192 in-scope sections.
These are text-volume measurements, not evidence of reading-time savings or successful challenge discovery.

`examples/evaluate_retrieval.py` measures eight labeled lexical queries across twelve synthetic sources.
The initial run placed the expected source first for all eight queries.
This small set does not establish performance on natural-language questions or private archives.

[The fresh-session exercise](continuation-evaluation.md) now includes all original sources as a stronger baseline.
In one preparation, those short sources used 838 characters while the original requirements pack used 4,551.
Removing duplicate claim summaries and empty groups reduced that pack to 2,307 characters on the same unchanged sources.
Direct reading can therefore be cheaper for small histories.
[One actual three-session AI exercise](fresh-session-results.md) now supports a narrower observation.
The requirements and full-source presentations each supported five answers after citation review.
Query-selected context supported two answers and produced three correct abstentions about omitted details.
This is no advantage over full-source reading on this tiny history and no evidence of human usability or demand.
An earlier proposed gate was [a human reader pilot](reader-pilot.md), including command friction and repeated-use feedback.
That study has not run. The current autonomous evaluation plan does not require manual participant studies.

[The bounded long-history exercise](long-history-results.md) uses a 62,875-character synthetic archive and a 5,000-character complete-prompt ceiling.
The manual reader supported five answers, while query-selected context supported two and produced three correct abstentions.
The requirements reader initially hit a provider usage limit, then a fresh retry supported all five answers on the unchanged prompt.
This matches the strong manual baseline without establishing better reader performance or lower effort.

[The maintenance replay](maintenance-evaluation.md) compares bounded audits with cited-source and whole-archive checkpoints.
The bounded audit detected three of four intended review needs and ignored two unrelated updates, but missed a paraphrased reversal.
The whole-archive checkpoint caught all four needs and flagged both unrelated updates.
The tool's inspection queue also remained pending on every update, so reduced total review burden is unproven.

[The automatic selection evaluation](automatic-selection-evaluation.md) tests nomination without manual pins.
Bounded rules proposed four of seven intended paragraphs and one irrelevant paragraph in the authored fixture.
One fresh assistant instead selected all seven intended sources with exact quotes, excluded all four distractors, and left permission conflicts unresolved.
That observation supports assistant-operated selection in this small exercise, not complete discovery or a built-in semantic selector.
[Validated saved-topic refresh](topic-review-refresh.md) now binds responses to the exact review input, creates paragraph anchors, and preserves explicit work.
One fresh synthetic response imported seven anchors; a later scripted explicit pin survived refresh without changing older handoff bytes.
These results establish workflow behavior, while actual effort savings and commercial value remain unproven.

## Evidence needed for a product decision

1. Compare the same task against manual handoffs and the closest existing tools.
2. Record lost constraints, repeated explanations, review time, and unsupported claims.
3. Run a fresh-session continuation with the same task and source evidence.
4. Ask target users to repeat the workflow on their own private archives.
5. Record actual repeated use and explicit pricing feedback.

Participation, external messages, and publication need separate user authorization.
Private evaluation inputs and reports remain outside this repository.
No telemetry or automatic publication belongs in this workflow.

If the requirements workflow adds friction without fewer missed constraints, revise or remove it.
Another generic search interface is not a sufficient product outcome.

[The scaling comparison](review-scaling-results.md) found no selection advantage and more input text than simple saved notes.
[Imported review maintenance](imported-review-maintenance.md) matched a project-scoped hash checkpoint after correcting an excluded-project false alert.
These results narrow the unproven claim to continuation and repair behavior rather than retrieval access, citations, or freshness detection.
Further checks must compare equivalent evidence and current authorization before attributing any improvement to this workflow.

[The regression-tool review](regression-tool-comparison.md) also found substantial overlap in evaluation, replay, visualization, and minimization.
FailMin's existing callback API reduced an actual synthetic failure in this repository without a new reduction engine.
The next investigation concerns archive-to-case preparation, with a comparison against existing importers before any adapter is built.
[The native importer comparison](native-importer-comparison.md) preserved the basic messages and paired tool data without a new conversion layer.
It found a chronology limitation in the captured payload and evidence losses in our Claude parser, which are now corrected.
[The chronology replay](chronology-replay-results.md) established that order changes a synthetic operation-check outcome.
An existing replay callback handled the original raw records without a production adapter, weakening that candidate distinction too.
The next product slice must start from an observed private archive problem rather than another invented mechanism demonstration.
[Source-origin hints](source-origin-hints.md) address an attribution problem found during that review: embedded templates can resemble user corrections.
Hints preserve the evidence and do not establish authorship, authority, or a model failure.
Private incident reconstruction must separate historical reports from independently established actions.
[The incident evidence protocol](incident-evidence-protocol.md) separates changed instructions and ambiguous targets from established constraint violations.
A captured correction and repair are not sufficient evidence that another memory or guard feature is needed.

## Withdrawn experiment: generated-command preflight

Investigate schema assumptions in generated operational snippets before adding a command-checking feature.
Use an isolated synthetic application and compare existing mechanisms first.
[Django's model metadata API](https://docs.djangoproject.com/en/5.2/ref/models/meta/) can inspect fields and raises an error for an unknown field name.
Field absence alone does not establish that every similarly named Python attribute is invalid; properties and dynamic behavior need separate treatment.
[django-stubs](https://github.com/typeddjango/django-stubs) provides framework types and a mypy plugin, with configuration and runtime-model-loading requirements.
[The isolated synthetic comparison](schema-preflight-results.md) now exercises these capabilities, including untyped and dynamic cases.
Existing checking covers the basic typed failure, while strict settings reject both unsafe and valid dynamic accesses with unknown return types.
This does not justify another checking engine.

Do not execute archived operational commands or infer production safety from a static check.
Compare detection, required setup, and false positives before choosing a product slice.
If an existing check handles the problem with little work, use that result rather than building another checker.
The follow-up investigation compared matching generated snippets to reported failures in archives with simple search.
[The fresh-reader comparison](investigation-reader-results.md) found equal supported conclusions, with more calls and displayed JSON for the evidence arm.
It establishes no investigation advantage or justification for a production failure matcher.

### Product-direction refresh — October 27, 2026

Recent public tools close several remaining generic angles. [Docket](https://github.com/Dillonsmart/docket) documents per-line agent edit attribution and associates checks with edits. [agent-witness](https://github.com/rioX432/agent-witness) compares a final completion claim with observed session events and reports configured-versus-used skills and MCP servers. [coding-agent-flight-recorder](https://github.com/spiatrenka/coding-agent-flight-recorder) documents local session forensics, while [agit](https://github.com/agitHQ/agit) documents replay, verified session forks, and merge workflows. These are documented project claims, not independently reproduced results. Together they mean this repository should not sell generic session replay, provenance, audit, or “did it really finish?” reports.

The skill ecosystem is also getting direct coverage. [KillerSkills](https://killerskills.ai/) documents cross-agent install checks, byte pinning, release drift alerts, real-session comparison, and organization-wide inventory. [NVIDIA SkillSpector](https://github.com/nvidia/skillspector) documents static and optional semantic security scans and Pi/OpenCode integrations. The [Skill Constellations paper](https://arxiv.org/abs/2610.11169) studies how copied skills lose source provenance and how fixes fail to reach downstream copies. Do not pivot this project into another generic skill scanner or inventory.

#### Withdrawn: generic session trees and cross-provider resume integrity

Current tools already document Codex parent trees, child-session reads, search, replay, and status. [Agent History](https://github.com/nihen/ah), [Agent Trail](https://github.com/camtrik/agent-trail), [LazyCodex's session finder](https://github.com/code-yeongyu/lazycodex), [AgentsView](https://github.com/kenn-io/agentsview), and [codex-threads](https://github.com/kcosr/codex-threads) overlap this space. The Codex parser correction remains valuable reliability work, but thread lineage alone is not a differentiator.

#### Diagnostic experiment only: read-only Codex lifecycle consistency

Codex stores thread-parent edges in `state_*.sqlite` and each thread's turn history in a rollout. Its source defines an `open` edge as a child that is live **or resumable**, so `task_complete` in the rollout does not prove that the edge is stale or that no worker is running. Public reports describe terminal child rollouts paired with open edges and children shown as Active after restoration. These are reports of specific builds and environments, not prevalence measurements or universal behavior: [Codex issue #33700](https://github.com/openai/codex/issues/33700), [Codex issue #35209](https://github.com/openai/codex/issues/35209), [Codex issue #50498](https://github.com/openai/codex/issues/50498), and [Codex issue #37876](https://github.com/openai/codex/issues/37876).

The candidate is a local read-only check that joins each persisted spawn edge with the child's latest rollout terminal marker and reports the evidence separately. It must say “last recorded turn is terminal; edge remains open/resumable,” never “agent is running” or “edge is stale.” Missing rollout data, contradictory events, unknown schemas, or incomplete chronology stay `unknown`. It must never edit Codex's SQLite database or close an edge.

Neighboring tools already cover parts: AgentsView documents lifecycle-derived status and subagent trees; Agent Trail documents local session status and replay; codex-threads queries live app-server status and parent links. Their public docs do not establish this offline cross-check between persisted SQLite edge status and rollout evidence. That documentation gap is not proof that no tool does it.

The synthetic, read-only prototype now exists in [codex-lifecycle-consistency](codex-lifecycle-consistency.md). It uses explicitly supplied paths, opens SQLite with `mode=ro`, and has no default archive discovery. It has not been exercised against a real Codex database or runtime. Adjacent tools now document local Codex history repair and cleanup, while Codex reports continue to document client-specific lifecycle inconsistencies. This supports keeping the checker as a diagnostic capability, not a standalone product bet. Do not inspect real archives, copy credentials, alter provider config, or automate repair. User value, a distinct advantage, and willingness to pay remain unestablished.

### Closed product lead: active-path retrieval and transcript handoff

This is no longer a defensible product lead. Pi's native session context and [pi-history-tools](https://github.com/amknight/pi-history-tools) use the active branch. [Switchboard](https://github.com/deadeye636/switchboard/blob/main/docs/backend-formats.md) documents a Pi parser that indexes the active branch and ignores abandoned branch text.

There are recent public reports of related but distinct resume failures: Codex reopens an older edited branch and hides later completed turns ([#42269](https://github.com/openai/codex/issues/42269)); an obsolete interrupted checkpoint can replace a completed continuation after restart ([#43885](https://github.com/openai/codex/issues/43885)); and a consumed permission reply reportedly resurfaced after compaction ([#27731](https://github.com/openai/codex/issues/27731)). These reports show consequential examples, not a shared root cause, prevalence, or proof this project can prevent the behavior.

More directly, the published [`sctxx` crate](https://docs.rs/crate/sctxx/latest) describes the same core job as this repository: extract Claude, Codex, and Pi transcripts into a compact verified handoff. Its [specification](https://github.com/handyutils/sctxx/blob/main/docs/SCTXX-SPEC.md) describes active-path resolution, event-range provenance, and checking claims against the current repository. The newer [`session-migrate`](https://github.com/xhluca/session-migrate) project documents native resumable-session migration across 18 harnesses, including Pi, Claude Code, Codex, and Cursor, with omissions declared in a content-free manifest. OpenAI also documents native import of Claude Code/Cursor setup and recent chats into Codex and ChatGPT. These are strong overlap signals; package/docs and self-reported test coverage do not independently establish runtime quality, adoption, or willingness to pay. [ctx](https://ctx.rs/) documents broad multi-agent history import and search. [brg](https://github.com/brghq/brg) documents context branches and Claude/Codex handoff. [Palimem](https://palimem.com/) documents cross-harness governed memory with supersession and audit. The feature categories we had considered are therefore already represented across active products; missing implementation details in their public docs are not a product gap by themselves.

The current exporter records Git branch names and some parent links. It preserves Codex `thread_rolled_back` markers as historical evidence but explicitly does not reconstruct the active conversation context; Cursor's documented export records lack branch metadata. These limits mean a universal active-branch filter is not currently supportable.

Close this lead as a product bet. Reopen it only if a target-user failure is observed on current versions of these tools and an evaluation demonstrates a substantial improvement in stale-answer rate or task completion. Do not implement another generic archive searcher, active-branch filter, or handoff generator based on capability absence alone.

Preventing stale decisions may still matter to users, but this repository has not shown an unmet failure, an advantage over these tools, a buyer, or willingness to pay. No exclusive-capability or commercial claim is justified. The next step is to find a specific recurring workflow failure before changing product scope again.

### October 27 secondary category checks

The next plausible categories are also crowded. [AgentHealth](https://github.com/opensearch-project/agent-health/blob/main/docs/CODING_AGENT_ANALYTICS.md), [AgentAbacus](https://github.com/tripleaceme/agentabacus), and [Claude Stats](https://marketplace.visualstudio.com/items?itemName=de-otio.claude-stats-vscode) document local usage analytics, cost or completion metrics, and in Claude Stats' case cost per successful task and ticket attribution. This makes a generic dashboard or model router a weak bet.

Retention has a concrete provider-specific failure mode: Claude documents a 30-day default for local session cleanup in [managed settings](https://support.claude.com/en/articles/14128775-claude-code-on-console-to-enterprise-migration). But [SessionKeeper](https://marketplace.visualstudio.com/items?itemName=argalla.sessionkeeper), [Rewound](https://www.reddit.com/r/ClaudeCode/comments/1uyyxxm/claude_code_deletes_your_session_transcripts/), and [agent-session-pack](https://github.com/YosefHayim/agent-session-pack) already document preservation or restore workflows. The gap is not generic archival; any narrower case needs an independently reproducible restore failure.

Independent trace integrity is a consequential security problem described in [recent research](https://arxiv.org/abs/2609.30266). [Tracekit](https://github.com/Cygnux-Labs/Tracekit), [ATB](https://github.com/pcguest/atb), [Agent Action Capsule](https://agentactioncapsule.org/), and [Obsign](https://github.com/obsign/obsign) document overlapping signed or tamper-evident capture and verification. A new generic audit layer would duplicate an active category. The current repository's post-run transcript readers cannot establish complete capture against a hostile agent.

These comparisons are documentation-level evidence only. They do not prove implementation quality, customer adoption, or demand. They eliminate generic feature bets; they do not produce a new validated product idea.

Work reporting is also represented: [weekly-report](https://github.com/tang-t21/weekly-report) combines Claude/Codex sessions with PR evidence; [weekly-report-skill](https://github.com/RayPengzhihui/weekly-report-skill) reads Claude and Cursor histories plus Git; [Agent Dump](https://agent-dump.xingkaixin.me/guides/weekly-report-from-ai-sessions/) produces source-scoped reports; and [Tracework](https://github.com/KKenny0/Tracework) describes evidence-based daily, weekly, monthly reports and roadmaps. [DX](https://docs.getdx.com/reports/agent-sessions/) offers commercial session-to-delivery analytics. This closes generic recap and proof-of-work generation as product wedges. Whether this repository can provide a materially safer, source-verifiable sharing flow remains untested; descriptions alone do not establish that it can.

### Closed: generic private agent bug packets

The problem reports remain individual evidence, not prevalence or current-version proof. A [Claude Code feature request](https://github.com/anthropics/claude-code/issues/57772) reports that sensitive paths, company names, personal information, and document contents prevent the reporter from sharing session transcripts for debugging. A [separate issue](https://github.com/anthropics/claude-code/issues/74814) reports a version-specific consent interaction that uploaded a full transcript containing plaintext secrets. Both issues are closed as not planned.

The hypothesis is a local workflow that turns a private agent session into a small bug report with enough evidence to reproduce the failure, while withholding the rest of the transcript. A short summary or a redacted transcript is not automatically sufficient: the output must preserve diagnostic signal and state when it cannot safely or faithfully do so.

This space already has substantial overlap. Pi's [`/bug` workflow](https://pi-agent-docs.pages.dev/sessions) can omit the transcript or ask the active model for a summary. The Pi [`pi-share-hf` workflow](https://huggingface.co/docs/hub/agent-traces) documents known-secret redaction, TruffleHog, and LLM review before upload. Oh My Pi documents a typed pre-share redaction pass and drops opaque payloads it cannot inspect in its [share implementation](https://github.com/can1357/oh-my-pi/blob/main/packages/coding-agent/src/export/share.ts). [`redact-transcripts`](https://github.com/crossvault/redact-transcripts) provides structure-aware local scrubbing and explicitly lists gaps including secrets in prose and sensitive meaning such as customer data or confidential code. [Praison AI](https://praison.ai/docs/cli/session/) documents sanitized session export and strict-by-default sharing. [Argenix](https://argenix.ai/privacy) documents shortening tool results and locally redacting paths, email addresses, and token-shaped values before a user-submitted bug transcript leaves the device. [Continuum](https://continuumcode.ai/product/share/) documents server-side allowlisted shares, a redaction preview, expiry, and revocation for sessions opened by its clients. [ReproWise](https://reprowise.ai/) and [Tapt](https://www.tapt.dev/) document reproducible bug reports with action traces, technical logs, sensitive-data masking, or visual privacy controls; their main focus is application bug capture, not coding-agent transcripts. [ContextClean](https://www.contextclean.dev/) locally reduces noisy logs and redacts common credentials but explicitly does not diagnose or reproduce failures. These published product pages and source comments are competitive evidence, not independent runtime validation; they make generic safe sharing and bug-report export poor candidates.

| Tool | Publicly documented workflow | Product implication |
|---|---|---|
| Pi `/bug` | Omit the transcript or ask the current model to summarize it | Bug-report workflow already exists in a coding agent |
| `pi-share-hf` | Collect Pi sessions, redact known secrets, run TruffleHog and LLM review, then upload passing sessions | Pi already has a multi-check guarded publishing path |
| Oh My Pi | Type-aware secret redaction before session-share encryption; drops opaque fields it cannot inspect | Share-time secret handling and explicit unsupported fields already exist |
| `redact-transcripts` | Structure-aware local scrubbing while preserving JSONL shape; publishes known misses | Generic local redaction is available, but the author says it cannot classify sensitive meaning |
| Praison AI | Sanitized export and strict-by-default share that removes paths and embedded file content | Local scrub-and-share is not unique to one harness |
| Argenix | User-submitted bug reports attach shortened transcripts with local path, email, and token redaction | A product already combines a support report with a minimized redacted session |
| Continuum | Preview a server-redacted session, set expiry, and revoke a share | Redacted session sharing has productized controls and a public-facing flow |
| VS Code / Copilot | `/troubleshoot` reads captured session events; the official support guide warns debug exports can contain prompts, source, paths, and tool data, which users must review and remove before sharing | Official troubleshooting still leaves privacy review to the user |
| VCode | Produces a short issue report without sending the conversation or files, then asks whether personal data, secrets, paths, or code may be present | Transcript-free bug reports are another existing privacy posture; the documentation does not establish reproducibility quality |
| Cursor support and shared transcripts | Official bug-report guidance says Privacy Mode hides conversation/context and even which tools failed; behavior issues require a fresh reproduction with Share Data. Shared transcripts include full history and use best-effort secret-pattern redaction, with no guarantee | Confirms the privacy/debugging trade-off in one vendor's documented flow; it does not show that an independent local packet would be accepted or improve diagnosis |
| [`agent-replay`](https://github.com/sangloo/agent-replay) | Exports an offline replay with scrubbed prompts, narration, and command output | The project explicitly leaves file contents unscrubbed; another replay export is not a complete privacy-preserving support packet |

This is a documentation comparison only. It does not establish feature quality, customer adoption, or equal safety. Cursor's [official bug-report guidance](https://prod.cursor.com/help/troubleshooting/reporting-bugs) explicitly confirms that Privacy Mode limits support's view of an agent-behavior failure, while [shared-transcript guidance](https://prod.cursor.com/help/ai-features/shared-transcripts) says shared links include the full conversation and secret redaction is best-effort. The documentation review found generic transcript redaction, sharing, bug-report export, event troubleshooting, and transcript-free reports already represented. No controlled comparison showed that a minimal packet preserves reproducibility better while exposing less, and no product gap or paid demand is established. Close generic safe sharing and bug-report export. Reopen only for a reproducible agent-specific failure that current workflows cannot preserve and a controlled comparison demonstrating less exposure at equal or better reproduction success. See the [roadmap](../roadmap.md).

### Closed detour: agent-workspace rollback

Do not turn transcript recovery into a generic undo/backup product. Public Codex reports include same-worktree edits silently disappearing from ordinary recovery paths ([#38541](https://github.com/openai/codex/issues/38541)) and primary-worktree deletion with some uncommitted loss ([#51672](https://github.com/openai/codex/issues/51672)). These establish consequential reports, not frequency or current prevalence. Direct alternatives now cover much of the workflow: [`claude-file-recovery`](https://github.com/hjtenklooster/claude-file-recovery) reconstructs Claude Code file states from tool operations; [Rollcage](https://rollcage.app/features/sessions), [bashback](https://github.com/trouties/bashback), and [doover](https://github.com/CaydenChik/doover) document session or shell-effect snapshots; [stepback](https://github.com/Archerkattri/stepback) documents cross-agent filesystem checkpoints; [VS Code](https://code.visualstudio.com/docs/agents/run/review-code-edits) ships automatic workspace checkpoints; and [SessionArk](https://github.com/julescules/sessionark) backs up provider session stores. [Agit](https://github.com/agitHQ/agit) adds cross-agent import, session file diffs, forking, and merging, with documented support for Pi and Codex; its own limitations say shell edits remain invisible and some runtimes carry no reconstructable file content. Additional direct tools include [Agent Change Guard](https://marketplace.visualstudio.com/items?itemName=PraveenMalagudi.agent-change-guard), [agent-undo](https://github.com/peaktwilight/agent-undo), [TimeAgent](https://github.com/timeagent-dev/timeagent), and [VibeRevert](https://github.com/madeinplutofabio/vibe-revert); [bashback](https://github.com/trouties/bashback) documents explicit gaps around failed shell commands and concurrent sessions. These are documented capabilities and claims, not runtime or adoption comparisons. The source-to-captured-patch restoration already in this repo is useful infrastructure; its edge cases do not support a new generic recovery product or a paid claim.

### Closed detour: agent history reindexing and repair

There is a real reported failure class: a [Claude Code issue](https://github.com/anthropics/claude-code/issues/18897) reports transcript JSONL files present while session-history index files are missing, and recent Codex reports describe either indexed history diverging from retained rollout JSONL ([#44434](https://github.com/openai/codex/issues/44434)) or a more severe case where the original transcript files could not be found after an update ([#27734](https://github.com/openai/codex/issues/27734)). These public issue reports indicate failures, not prevalence, current-version behavior, or verified causes.

The repair niche is already forming. [`codex-history-doctor`](https://github.com/2395115107-stack/codex-history-doctor) documents backup-first, previewable Codex history-index/database repair; [`Codex-session-recovery`](https://github.com/fengyazi/Codex-session-recovery) documents index rebuilding; [`cc_jsonl_fix`](https://github.com/ymonster/cc_jsonl_fix) repairs a Claude transcript parent-chain corruption case; and [`claude-code-session-recovery`](https://github.com/ibrews/claude-session-recovery) documents rebuilding a Claude Desktop index from retained transcripts. The source-to-export pipeline here cannot repair provider-owned databases or recreate missing transcript content. Do not pivot to a generic reindexer or claim this repo prevents history loss. Reopen only if a reproducible cross-provider failure remains after these tools and a non-destructive validation comparison shows a specific unmet outcome. No buyer or willingness-to-pay evidence is established.

### Closed as a standalone product: long-running work stops without a real blocker

Several public Codex issue reports describe active multi-step work ending after handoff or compaction and needing a “continue” nudge ([#33398](https://github.com/openai/codex/issues/33398), [#36596](https://github.com/openai/codex/issues/36596), [#36506](https://github.com/openai/codex/issues/36506)). They are user reports, not evidence of current-version prevalence. A separate Goal-management report describes a limited agent-facing lifecycle interface ([#40162](https://github.com/openai/codex/issues/40162)).

Current [Codex Goals documentation](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex) says active goals continue at safe idle boundaries, pause on interruptions, and suppress repeated continuation when no tool work occurs. The [App Server protocol](https://learn.chatgpt.com/docs/app-server) documents `thread/resume`, turn status/events, and goal get/set/clear on the same persisted goal state surfaced by the Codex TUI. The reported behavior therefore overlaps with a first-party feature contract and supported lifecycle API; the open issues do not establish a current unresolved defect. Adjacent tools also cover the generic solution: Anthropic’s [Ralph Loop](https://claude.com/plugins/ralph-loop), quota-aware [Codex Auto Resume](https://github.com/progressrdx/codex-auto-resume), [Temporal's durable-agent guidance](https://docs.temporal.io/ai), and the [nl-veil continuation proposal](https://github.com/openai/codex/issues/36596) in the Codex issue discussion. Verification and stop gates overlap too: [done-gate](https://github.com/kuroudo-ai/done-gate), [agent-done-or-not](https://github.com/mohamedzhioua/agent-done-or-not), and [Keepgate](https://github.com/darrien1998/Keepgate) document related controls. These sources are feature claims and proposals, not independently validated quality or demand. Close generic goal continuation and completion guarding as product wedges. Reopen only for a reproducible current-version failure that bypasses the documented API and remains valuable after those alternatives. No unique advantage or willingness to pay is established.

Next, continue public issue/changelog discovery across a different problem category. Do not build a continuation controller from these reports alone. Reopen this category only if a current reproducible defect and a remaining gap beyond the documented Codex lifecycle API and existing continuation/verification tools are demonstrated.

### Screened lead: evidence-complete blocker handoffs (October 28)

The preprint [Knowing When to Stop](https://arxiv.org/abs/2610.31895) introduces ImpasseBench and reports 19,371 trajectories across eight models. In its benchmark, adding an escalation tool reduced runs that exhausted the step budget from 34.0% to 6.7%; escalation tickets still omitted the agent's own progress in 35.7% of cases, and 25.9% of tickets were rated only partial. This is a controlled benchmark result, not a production prevalence estimate or proof that the same rates apply to local coding-agent histories.

The report-quality job already has direct overlap: [Aether's handoff export](https://github.com/AetherAI3/Aether-Agent/blob/main/COMMANDS.md) includes verification verdict, failing-test count, changed files, and verification command; [deja-vu](https://github.com/vshulcz/deja-vu) describes prior-session handoffs with conclusions, passed checks, and where work stopped; [dot-reflex](https://github.com/usedotai/dot-reflex) describes stop decisions that preserve evidence and report a blocker. The current repository can build source-linked retrospective handoffs from supported archives, but it cannot observe or stop a live run, and no comparison shows it produces more useful handoffs than those tools. Close a generic escalation controller or blocker-ticket generator. Reopen only if a same-task comparison shows an actionable cross-agent evidence gap that these tools miss and reduces recipient rediscovery or unsafe continuation. No unique value, adoption, or willingness to pay is established.

### Screened lead: cross-project context contamination (October 28)

Public reports identify specific, bounded risks: Codex issue [#17496](https://github.com/openai/codex/issues/17496) reported global memory-summary injection without working-directory filtering and was closed as completed, but current runtime behavior was not independently reproduced here; Codex issue [#16799](https://github.com/openai/codex/issues/16799) reports a project-specific approved command path appearing in another project's session, while the maintainer classified it as model behavior and the reporter published a separate controlled comparison; Multica issue [#6656](https://github.com/multica-ai/multica/issues/6656) describes stale issue memory in shared local-directory workspaces, with a maintainer correction that standard per-task workdirs were isolated and the risk applied to the shared-directory mode. These are concrete reports, not prevalence estimates or proof of a current broad provider defect.

The category already has direct tooling: [ContextGuard](https://bearinblue.github.io/contextguard/) audits agent instructions and workspace security; [ContextGuard by Jag](https://jagjourney.ai/context-guard/) markets local auditing and cleanup of persistent memory across coding agents; [OWASP Agent Memory Guard](https://owasp.org/projects/agent-memory-guard) screens memory operations for poisoning; and [ContextGuard's contamination detector](https://github.com/kriskimmerle/contextguard) documents cross-session contamination markers. These are published descriptions, not comparative runtime results. This repository can scope its own archive review by exact project metadata, but it cannot inspect every hidden prompt or prevent a provider from injecting out-of-scope memory. Do not build another generic memory cleaner or context firewall. A residual archive-based audit of observed foreign-project paths in tool calls is only a hypothesis; reopen only after a synthetic same-case comparison shows a useful result beyond these tools with acceptable false alerts. No unique value, adoption, or willingness to pay is established.

### October 28 screen: repeated rule violations and approval integrity

Public reports describe costly cases where agents acknowledge or have access to a saved process rule, then ignore it; examples include [repeated destructive deployment commands after saved-script instructions](https://github.com/anthropics/claude-code/issues/71671) and [repeatedly ignored project instructions](https://github.com/anthropics/claude-code/issues/27087). These are individual reports, not frequency estimates or independently reproduced current-version failures. The broad product idea is already crowded: [Microsoft's agent hooks](https://learn.microsoft.com/en-us/azure/sre-agent/agent-hooks) document policy gates at tool boundaries; [Shield](https://github.com/AperionAI/shield), [Kintsugi](https://github.com/arrowassassin/kintsugi), [destructive_command_guard](https://github.com/Dicklesworthstone/destructive_command_guard), and [world-model-mcp](https://github.com/SaravananJaichandar/world-model-mcp) document cross-agent enforcement, destructive-action controls, or repeated-violation memory. Do not build a generic instruction-adherence monitor or policy hook.

A narrower research lead is **whether an approval stays bound to the real effects of the exact action approved**, including argument changes, delegated calls, and downstream side effects. [Approval Laundering](https://arxiv.org/abs/2609.38983) reports controlled tests of six approval/execution mismatch classes; [Agent Approval Laundering](https://arxiv.org/abs/2609.28586) studies effects beyond the directly approved invocation. Existing product overlap is substantial: [Maqam](https://github.com/AjnasNB/maqam) documents exact one-use approvals, [Writ](https://github.com/infinri/Writ) documents tool-time workflow gates and approval records, and [Chio](https://www.chio.computer/docs/concepts/human-in-the-loop) documents parameter binding. Oh My Pi's [approval-mode documentation](https://github.com/can1357/oh-my-pi/blob/main/docs/approval-mode.md) says approval is resolved again after extension handlers revise arguments, while also warning that shell approval is not process or filesystem containment. Pi's [security documentation](https://pi.dev/docs/latest/security) says its default runtime does not ask before every tool call and relies on OS or virtualization boundaries to limit effects. These are source and product-documentation claims, not an independent runtime comparison. They establish neither a gap in those tools nor commercial demand. This is a test lead, not a selected product direction; a session exporter alone cannot prove what the approval UI showed or independently capture every side effect.

The approval-to-effect lead is now closed as a generic product direction. On October 28, a synthetic Claude Code 2.1.168 run with a fake loopback provider showed that a `PreToolUse` hook could allow `python3 ./task.py` while the script created both the requested `approved.txt` and an extra `extra_effect.txt`. The session parser retained the request, call, result, and final response, but did not produce an approval-to-effect finding. This was a single tool-layer probe: it did not test a human-facing approval card, a real model, or any competing runtime. AgentSight and Actime document the deeper effect-observation layer, so this is not a distinct capability claim. See the [synthetic approval-to-effects screen](approval-to-effects-screen.md).

Next gate: return to public issue and changelog discovery in a different outcome category. Do not build an approval monitor, effect tracer, or security gateway from this result. A new candidate needs a repeated user problem, a current baseline comparison, and evidence of meaningful user benefit before product work or a paid claim. Do not contact users or maintainers. Keep private history and personal data out of the public repository.

The candidate list still has no validated paid wedge. Continue mining public bug reports and changelogs for distinct repeated outcomes, deduplicate issue copies and follow-ups, and compare each cluster with current alternatives. Do not infer willingness to pay from issue counts, stars, or dramatic anecdotes. Keep the goal open until a candidate has a distinctive, measurable outcome and credible commercial evidence.

### October 28 screen: multi-agent semantic integration failures

Public reports and the STale benchmark describe cases where parallel or independently valid changes fail when combined. Direct tools such as Foremerge and Comity cover proactive coordination; TrajAudit, AgentRx, AgentDebugX, agenttrace, and onpath cover adjacent trajectory diagnosis, failure attribution, or local incident reports. Do not build a generic coordination or agent-failure diagnosis layer. One synthetic probe shows a specific cross-worktree type mismatch can pass locally, merge cleanly, and fail when combined, but this repository did not diagnose it and no comparison with the diagnosis tools has been run. That intersection is a research question, not a selected product direction or uniqueness claim. See the [multi-agent semantic integration screen](semantic-collision-screen.md).

The source audit found that existing claim extraction, quoted-relationship linking, source inspection, and captured-patch recovery are all bounded components; none produces this cross-session diagnosis today. The synthetic two-worktree probe showed both local checks passing, a clean merge, and a combined type failure. The parser preserved both source statements and edit calls, but current claim/relationship analysis did not diagnose the mismatch. Git did not report a conflict. Public tools TrajAudit, AgentRx, AgentDebugX, agenttrace, and onpath already cover adjacent trajectory diagnosis, attribution, or local failure reporting. Close generic multi-agent failure diagnosis; reopen the specific two-session case only after a measured comparison against these current diagnostic tools shows a material gap. Do not use private session data or contact users in this screen.

### October 28 screen: persisted session versus usable history

Recent Claude and Codex reports describe cases where persisted source records remained available while `/export`, history projection, or migration lost or omitted content. These are high-cost reported failures, not frequency estimates. The general solution space is crowded: the Unified Agent Session Specification defines broad conformance matrices; Session Preserve documents source coverage and integrity receipts; Agent Session Pack documents byte-exact archive/restore; ectype covers multi-agent conversion and redaction; SessionArk targets backup and recovery. Do not build a generic parser suite, archive, or repairer. The only open check is whether a current, reproducible provider gap exists that this repo can expose through read-only comparison without claiming UI completeness or changing provider state. See the [session-fidelity screen](session-fidelity-screen.md).

Next gate: check the current status of the three cited provider reports, then compare one synthetic source/export mismatch against existing preservation and repair receipts. Continue only if a material read-only recovery difference is demonstrated. Keep the actual fixture synthetic; no real archives or paths belong in this public repository.

### Screened category: worktree runtime setup

Public Codex reports describe selected setup scripts not running for remote worktrees and handoffs, leaving dependencies or generated environment files absent ([#23648](https://github.com/openai/codex/issues/23648), [#18981](https://github.com/openai/codex/issues/18981)). Claude Code reports also describe missing project configuration, hooks, or submodules in desktop worktrees ([#28041](https://github.com/anthropics/claude-code/issues/28041), [#83411](https://github.com/anthropics/claude-code/issues/83411)). These are specific reports, not proof of frequency or a shared current defect. Direct tools now cover provisioning and isolation: [workz](https://github.com/rohansx/workz) syncs local environment files and dependencies and can isolate ports/databases; [falq](https://github.com/sunduq-ai/falq) manages per-worktree runtime configuration; [Git Treeline](https://git-treeline.dev/features/agents/) provisions ports, databases, and cross-repository services; [Berth](https://outpostlabs.dev/berth/) provides isolated agent environments; and [AgentProto Worktree](https://www.npmjs.com/package/@agentproto/worktree) documents provision → run-gate → cleanup orchestration. Native Codex environments, Claude worktree hooks, and VS Code worktree configuration add further coverage. A generic environment-sync or worktree-bootstrap product would duplicate existing approaches. A follow-on check for wrong test targets was also closed after a synthetic Linux probe and direct review of Nexus Agents and AgentSlots; see [worktree test-target screen](worktree-runtime-integrity-screen.md). No remaining gap, runtime advantage, or paid demand is established.

### Closed detour: retrospective agent-security and incident response

Do not pivot to generic prompt-injection detection, session forensics, or compliance reporting. [AgentDFIR](https://github.com/efij/AgentDFIR) documents local collection and investigation across many coding agents, evidence confidence states, attack-chain timelines, and exportable incident cases. [toolmark](https://github.com/reloading01/toolmark) documents forensic timelines and detectors; [alibi-guard](https://pypi.org/project/alibi-guard/) documents post-session tracing from untrusted transcript content to dangerous calls. [SessionGuard](https://sessionguard.dev/) documents local transcript auditing. [BeyondTrust](https://docs.beyondtrust.com/bt-docs/docs/ai-coding-sessions-and-actions) and [Pinta](https://pinta.sh/) document runtime or endpoint security investigation, including prompt-injection and exfiltration controls. These products differ in scope, capture path, and assurance, and their public claims were not independently tested. They nevertheless make generic agent security/forensics a poor product bet here.

### October 28 screen: subagent output durability

Claude Code issue [#88621](https://github.com/anthropics/claude-code/issues/88621) reports that Desktop displayed “No output captured” for a completed subagent while the matching transcript remained on disk; it was closed as not planned after inactivity. Related reports cover background-output visibility ([#43829](https://github.com/anthropics/claude-code/issues/43829)) and raw subagent JSONL flooding the parent context ([#17591](https://github.com/anthropics/claude-code/issues/17591)); these are version-specific reports, not proof of a current widespread defect. `compact-plus` and `compact-handoff-plugin` cover compaction state; Tracehouse documents a local viewer where a user selects the child transcript; public schema tooling documents how to join a parent invocation to the child file. Generic memory, compaction, and session viewing are therefore poor product bets. Whether one-step recovery of a missing final result adds enough value beyond opening that child transcript remains unknown.

The current Claude parser finds nested JSONL files but skips `isSidechain` records. A seven-case synthetic prototype recovered one uniquely linked completed result and declined missing, failed, nonterminal, ambiguous, nested, and stale-final cases. This proves only code feasibility on an authored schema shape; it did not run a current provider session. Tracehouse already documents expanding available child traces and manually loading a child transcript. The proposed extractor may save file selection, but no measured time savings or distinct user benefit is established. Close this as a product candidate; retain the synthetic probe as parser research. Reopen only if current provider-generated evidence shows a gap existing viewers do not handle and a measured comparison shows meaningful user benefit. No current bug, adoption, or willingness to pay is established. Details: [subagent output durability screen](subagent-output-durability-screen.md) and [synthetic probe](../examples/evaluate_subagent_output_recovery.py).

### October 28 screen: repeated instruction violations and correction cost

OpenAI Codex issue [#43792](https://github.com/openai/codex/issues/43792) describes repeated violations of acknowledged instructions and the resulting correction turns and usage cost. The report is open and links several similar reports, but these are user reports, not independent reproductions or prevalence evidence. Its proposed remedy spans enforced constraints, usage attribution, compensation, and private diagnostics; that scope does not establish one product requirement.

The broad action-enforcement category is already crowded: agent-guard documents pre-execution shell rules across several harnesses; Ordo documents local allow/deny/ask rules and policy tests; Control Zero documents per-event enforcement coverage. These tools can gate supported tool actions, but their published descriptions do not claim to make conversational requirements reliably binding or measure correction-loop costs. Failproof AI separately describes session audits for repeated behavior patterns. These are product descriptions, not independent runtime comparisons. No distinct capability, repeated need outside the reports, user-benefit measurement, or buyer evidence is established. Do not build another general guardrail or session-audit tool. Reopen only for a specific unmet decision with a reproducible baseline comparison and a clear user outcome. Keep all private session material out of the public repository.

The [20,574-session misalignment study](https://arxiv.org/abs/2605.29442) adds stronger problem evidence: it reports seven recurring forms of developer-visible friction, with constraint violations, intent misreads, and inaccurate self-reports among the most common. The authors estimate that 90.5% of validated episodes imposed effort or trust costs, and 91.49% of visibly resolved episodes needed explicit developer correction. The corpus combines public SpecStory exports and opt-in Entire logs; it is observational, relies on visible pushback, and does not estimate all silent failures or product demand. Correction mining and cross-agent reusable guidance also overlap with [TRACE](https://arxiv.org/abs/2606.13174), [Tellonce](https://github.com/YujunZhou/tellonce), [Pathrule](https://www.pathrule.io/), and [agentmemory](https://www.agent-memory.dev/). This confirms that correction cost is a real design problem in the studied sessions, but does not make a generic session analyser, correction miner, or rule-learning product distinctive. No specific remaining outcome or willingness to pay is established.

### Rejected alternative: agent-session-derived freelancer billing

The commercial job would be to turn coding-agent activity into defensible billable time, client-ready work descriptions, and invoices. Direct products already target this exact workflow. [Hourweave](https://www.hourweave.com/) documents joining Claude Code, Codex, and Cursor sessions with Git and issue-tracker activity; it drafts evidence-linked timesheets for review, supports client approval and invoices, and lists a $2.99/month Pro plan. [AgentHours](https://marketplace.visualstudio.com/items?itemName=CavalryCollective.cavalry-agenthours) documents billable-time reconstruction across VS Code, Claude Code, and Codex CLI, plus CSV/JSON export; it is open source and explicitly warns users to check hours before billing. [Scribe](https://www.bopen.io/products/scribe) and [Time2Pay](https://time2pay.app/) also market developer-work evidence linked to invoices.

This is a clear money-linked user outcome, but not an uncovered one. The listed price proves only that a vendor offers a price, not that customers pay or retain the product. Time inferred from agent start/stop or session duration also needs idle handling, overlap removal, client attribution, and human approval before billing; Hourweave and AgentHours both document these safeguards. Do not add invoicing or billable-time features here. Reopen only if a reproducible client workflow needs evidence that these products cannot provide and a measured comparison shows an incremental billing or dispute-resolution benefit. No such gap or customer demand is established.

### Screened lead: unexplained coding-agent quota use (October 28)

Claude Code issue [#54750](https://github.com/anthropics/claude-code/issues/54750) is still open and links several similar usage-limit reports. It describes account limits reaching 100% while the reporter's local session usage appeared too low to explain it; later comments include separate reports across versions. One commenter attributes a narrower `--resume` pattern to prompt-cache rebuilding, but the issue thread contains multiple symptoms and does not establish one cause. This is user-reported evidence, not an independently reproduced provider-wide defect or a prevalence estimate. A recent preprint analyzes 1,200 Claude Code and Mini-SWE-Agent trajectories and reports cost-inefficient behaviors, but its controlled benchmark does not establish production demand ([paper](https://arxiv.org/abs/2609.30725)).

The broad product category is occupied. [ccusage](https://github.com/ryoppippi/ccusage) and [Trellis](https://trellis.dev/docs/pages/usage/) calculate local token totals and API-equivalent cost; [ccdeck](https://ccdeck.dev/) combines local session activity with Claude Code and Codex quota views; and [llm-usage-tracker](https://github.com/ninedter/llm-usage-tracker) documents provider quota monitoring alongside local session, tool, and file activity across machines. Their public descriptions are not independent quality or adoption evidence. The uncovered-sounding question—reconciling account-level quota consumption to every local and remote session or provider surface—requires trustworthy provider-side attribution that local archives do not contain. Whether any provider exposes sufficient data, and whether these existing tools already solve it, is not established.

Close generic usage dashboards, cost estimation, and quota meters as product leads. Reopen only if provider-authoritative per-request attribution is accessible and a same-case comparison demonstrates a reliable explanation unavailable in current quota-plus-session trackers, followed by evidence that users will pay. Do not inspect or publish private usage records. No unique outcome, adoption, or willingness to pay is established.

### Screened lead: MCP configuration context overhead (October 28)

The [MCP client best-practices guide](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/docs/2026-07-28/develop/clients/client-best-practices.mdx) says loading every tool definition into context can waste tokens and degrade performance, and recommends progressive discovery. GitHub's [agent-workflow optimization report](https://github.blog/ai-and-ml/github-copilot/improving-token-efficiency-in-github-agentic-workflows/) reports that removing unused MCP tools reduced context in its smoke tests. Anthropic's [MCP code-execution article](https://www.anthropic.com/engineering/code-execution-with-mcp) likewise describes tool-definition and result overhead. These establish a design concern and bounded measurements, not a universal coding-agent cost or buyer demand.

Direct approaches exist: Atlassian publishes the open-source [`mcp-compressor`](https://www.atlassian.com/blog/development/mcp-compression-preventing-tool-bloat-in-ai-agents); [`mcp-optimizer`](https://github.com/o8n/mcp-optimizer) documents configuration analysis, token estimates, and usage-based identification of unused tools; and MCP's own client guidance covers progressive discovery. These are documented capabilities, not independent quality or retention results. This repository's session archives do not reliably contain the exact tool schemas and configuration version used for each request, so transcript token totals alone cannot attribute overhead or show that removing a tool preserves task success.

Close generic MCP token estimators, compressors, unused-tool reports, and setup auditors as product leads. A possible research gap is a same-task, cross-agent evaluation that measures actual input-token savings while verifying that tool-selection accuracy and task outcomes do not regress. No distinct tool advantage, repeated buyer workflow, adoption, or willingness to pay is established; keep this repository focused on session evidence until such a result exists.

### Screened lead: authorization and uncertain effects during agent recovery (October 28)

The preprint [Permission to Retry](https://arxiv.org/abs/2610.31916) studies a consequential action whose remote effect may have occurred even though its acknowledgement was lost, while permission changes before recovery. Its finite campaign tests synthetic provider contracts on LangGraph and Temporal; it separates checked completions, denials, and unknown outcomes. It is evidence that a technically meaningful recovery boundary can be evaluated, not a production incident-rate study or proof of buyer demand. Its own validity section limits generalization to the authored synthetic histories and contracts.

Pi's [pi-durable-subagents](https://pi.dev/packages/pi-durable-subagents?name=pi-coding-agent) documents crash recovery, effect-safe retries where it can replay retained results, and explicitly says it cannot undo an external effect that happened before a crash. The Pi package page reports 7,421 monthly downloads for v1.4.3, an adoption signal for durable subagents but not proof of paid demand. Adjacent tools already target the external-action boundary: [Golem](https://golem.cloud/) documents durable agent execution and effect logs; [DigitalOcean Action Gateway](https://docs.digitalocean.com/products/managed-agents/action-gateway/concepts/reliable-execution/) documents bounded retries and idempotency contracts; [Cloudflare's Think Actions RFC](https://github.com/cloudflare/agents/blob/main/design/rfc-think-actions.md) specifies an action idempotency ledger; and [ActOnce](https://actonceapi.com/), [OnceOnly](https://www.onceonly.tech/), and [Dataoad](https://www.datoad.dev/) market action deduplication or recovery controls. These are public product or design claims, not independent reliability or customer evidence.

Close the generic agent retry-safety, idempotency gateway, and effect-ledger direction for this session-exporter repository. A narrower coding-agent integration that checks both current authority and unresolved provider effects at resume may still matter, but the cited tools already cover much of the mechanism and the paper's exact provider ledger depends on contracts an exporter cannot observe. Reopen only for a named agent/provider workflow with a reproduced failure that current runtime controls miss and a measured improvement in safe completion; no such gap, adoption, or willingness to pay is established.

### Research lead: cross-agent session data lifecycle and deletion evidence (October 28)

The handling rules are not uniform. [Claude Code's enterprise settings](https://support.claude.com/en/articles/14128775-claude-code-on-console-to-enterprise-migration) document a 30-day default local cleanup period and enterprise-managed settings; Anthropic's [Enterprise Compliance API](https://platform.claude.com/docs/en/manage-claude/compliance-sessions) separately retains captured local-session content for six years by default, with organization and HIPAA exceptions. GitHub documents that [disabling Copilot session sync](https://code.visualstudio.com/docs/agents/run/sessions/session-history) does not remove data already synced to a personal GitHub account, and organization policy does not give administrators access to those sessions. Cursor documents separate data layers for [Cloud Agent conversations and environment snapshots](https://prod.cursor.com/docs/cloud-agent/security-network): conversations are kept indefinitely by default, Enterprise retention currently offers Indefinite or 90 days, while snapshots follow a separate inactivity expiry. These are product-specific policies, not one cross-agent retention guarantee.

Generic local browsing, archival, and cleanup are covered by provider-native commands and tools such as [agentic-session-explorer](https://github.com/junxit/agentic-session-explorer), which claims guarded deletion across several local stores and associated artifacts. Cursor's [current release notes](https://prod.cursor.com/docs/release-notes) also describe cleanup of leftover message data after deleted chats. The public evidence does not establish that every local artifact can be enumerated, that cloud deletion can be independently verified, or that one dashboard improves on native controls. In particular, `off`, `archive`, `delete`, and expired are different states; an account-wide policy cannot be inferred from a local transcript scan.

#### Feasibility gate

A local-only inventory cannot prove the full data lifecycle. A local Copilot sync setting cannot reveal whether earlier sessions remain in the account; GitHub documents [separate controls for deleting synced copies](https://docs.github.com/en/copilot/concepts/security-governance-and-network-settings/session-data). Claude's [Compliance API](https://platform.claude.com/docs/en/manage-claude/compliance-sessions) exposes organization-level local-session records and retention, which a local filesystem scan cannot see. Cursor Cloud Agent conversations and snapshots also require [cloud-side controls](https://prod.cursor.com/docs/cloud-agent/security-network). GitLab already documents an [organization dashboard for external coding agents](https://docs.gitlab.com/user/ai-governance/externally-connected-agents/), but its CLI reads local transcripts and sends sessions and events to GitLab. [Stacktrace Fleet](https://stacktrace.ai/fleet/) documents an endpoint sidecar that analyzes session files locally and sends findings/inventory, not transcripts, to a fleet dashboard; it also documents one policy across agents. That directly covers the proposed content-free fleet view. Thus there is a real privacy tradeoff, not proof that a separate no-content report has buyer value.

#### Synthetic policy scenario (documentation-only)

Assume a team policy requires coding-agent session records to be removed 30 days after inactivity, and requires no synced copy to remain after local deletion. This is a hypothetical policy check against public product documentation, not a live account test.

| Provider surface | Documented control | What the check must still know |
|---|---|---|
| Claude Code Enterprise | Managed `cleanupPeriodDays` can control local cleanup; the Enterprise Compliance API has its own retention behavior tied to organization settings | Verify the effective managed setting and the organization retention period; a local-file scan cannot report Compliance API visibility |
| GitHub Copilot | Session sync can be governed separately from local storage; previously synced records need explicit deletion, and the CLI offers local-plus-cloud session deletion | Inspect both policy and account sync/deletion state; sync disabled alone does not meet the no-copy rule |
| Cursor Cloud Agents | Enterprise conversation retention currently offers Indefinite or 90 days; a per-agent delete API exists; environment snapshots have their own 30-day inactivity lifecycle | The 90-day setting alone does not meet a 30-day conversation policy; distinguish transcript deletion from snapshot expiry |

The scenario exposes a plausible automation gap: a stricter-than-native common retention policy may require different controls and account access on each provider. It does not prove that there is no existing automation, that these controls are available to the same organization, or that users will pay for a policy controller. The required account-level and endpoint integrations make this an enterprise product hypothesis, not a local archive feature.

The concrete product hypothesis is: an organization sets one maximum session-retention policy; endpoint clients and provider integrations apply it to local and cloud copies, then return a content-free evidence report showing which stores complied and which were unverifiable. Stacktrace Fleet documents the private endpoint/fleet architecture and its own agent policy, but its published ten rules do not currently document retention enforcement. That is a feature-scope gap in the public description, not proof of a product gap or market demand. The local multi-agent deletion tool addresses a separate endpoint-only slice.

#### First-pass enforcement matrix (public docs only)

| Surface | Native enforcement documented | Remaining cross-agent work |
|---|---|---|
| Claude Code Enterprise | Managed `cleanupPeriodDays` can be set on endpoints ([settings](https://support.claude.com/en/articles/14128775-claude-code-on-console-to-enterprise-migration)); enterprise conversation retention governs Compliance API capture, which is read-only for session data ([retention](https://platform.claude.com/docs/en/manage-claude/compliance-sessions)) | Confirm effective endpoint and organization settings across enrolled devices, and report the specific ZDR/HIPAA exceptions without collecting content |
| GitHub Copilot | Enterprise policy can disable session sync; local tools can delete local and synced session data, with controls that vary by Copilot surface ([session data controls](https://docs.github.com/en/copilot/concepts/security-governance-and-network-settings/session-data)) | Enforce one maximum-age policy across devices and account copies; sync-off alone does not remove old cloud copies, and no fleet-wide age-based delete control was found in the reviewed docs |
| Cursor Cloud Agents | Enterprise policy offers Indefinite or 90-day conversation retention; the API can delete an agent conversation; VM snapshots expire after 30 inactive days and cannot be deleted on demand ([retention and deletion](https://prod.cursor.com/docs/cloud-agent/security-network)) | Apply a stricter period through per-agent deletion where permitted; separately report snapshot expiry and avoid claiming immediate full deletion |
| Local session stores | Provider commands and [agentic-session-explorer](https://github.com/junxit/agentic-session-explorer) cover local session deletion for several tools | Connect local deletion to an organization policy and signed, content-free compliance evidence without breaking active sessions or other provider state |

This matrix suggests real integration work beyond a local scanner, but the controls remain fragmented and the operational policy may already be handled by MDM, vendor settings, or an organization's scripts. The hard question is not whether a dashboard can list stores; it is whether it can safely enforce an age rule across device and account scopes and prove the residual limits. No public source reviewed here establishes a commercial buyer for that work.

Do not prototype this as a complete local-only compliance auditor. New official documentation sharpens the governance mismatch: Microsoft says Purview retention policies do not apply to Copilot saved memories and provides no admin retention control for them; users must delete those memories. This is adjacent Copilot-memory evidence, not proof about GitHub Copilot coding-agent memories. Anthropic's Compliance API documents six-year default capture for local sessions and is read-only for session deletion; retention can be organization-configured, and HIPAA/ZDR cases differ. Cursor documents a delete API for Cloud Agent conversations, while snapshots have a separate lifecycle. Stacktrace Fleet's published cross-agent policy governs components (allow, block, or approval), not session age or deletion. These are distinct control boundaries, not a single universal gap.

The initial hypothesis was **automated retention-policy reconciliation for coding-agent data**: compare a company's maximum retention rule with the controls actually available for each enrolled agent and store, then show states such as policy configured, deletion requested, vendor-confirmed, user-action required, and unverifiable. The useful outcome would be identifying a policy violation or blind spot before an audit or employee departure, not another transcript dashboard. The [AI Developer Toolkit already publishes a manual AI service register](https://developertoolkit.ai/en/org/privacy-data-handling/) with per-service plan, route, retention, owner, and change triggers; the current synthetic spike does not beat that register. Any product difference would have to come from accurate automatic discovery, effective-setting verification, and drift alerts across stores. Keep this as an enterprise product-validation lead, not a selected product or a uniqueness claim. It must show a better result than MDM, Purview, vendor controls, Stacktrace/GitLab, manual registers, and scripts. No buyer, discovery feasibility, repeated incident, or willingness to pay is established. Do not promise complete erasure.

The synthetic policy and expected store states are recorded in the [retention-policy reconciliation prototype](retention-policy-reconciliation-prototype.md), with a runnable [offline demo](../examples/retention_reconciliation_demo.py). It processes only invented store states; this is not a provider integration or a completed comparison. The first scenario output is only a report over static inputs and does not outperform the manual AI service register. The API contract comparison is recorded in the subsection below; it found no advantage over an equally current manual register. Do not build production integrations from static inputs. No production integration or customer validation is authorized or implied by this research note.

**October 28 API refresh and comparison:** Anthropic's official Compliance API documents an endpoint for effective organization settings, including typed retention periods; the endpoint can verify enforced state for eligible linked organizations, not physical deletion or every account route. A [Cursor Enterprise user requested shorter retention](https://forum.cursor.com/t/retention-of-cloud-agent-sessions/161178) so the team could safely grant agents broader access. Cursor now documents 90-day/indefinite Enterprise controls plus per-agent transcript deletion. However, its published Cloud Agents API does not expose the retention-policy field, and snapshot expiry is separate. GitHub's agent-session activity API is limited to specific Enterprise Managed Users/data-residency setups. [Coder Agents](https://coder.com/beta-docs/ai-coder/agents/platform-controls/chat-retention/) exposes a retention API for its own conversations and separates archived conversations, debug data, and shared files. These are direct single-provider controls, not a cross-vendor control plane.

The contract-level synthetic comparison found no policy mismatch that an API-aware report caught when the manual register had equally fresh evidence. A stale register could miss Anthropic drift, but setting-change frequency and avoided review time are unknown; Cursor and GitHub still require manual or unknown states. **Decision:** do not prototype a product or build connectors from this evidence. Keep only the unanswered question of whether organizations with multiple providers experience retention drift often enough to make automated checks valuable. One forum request establishes an outcome one customer wanted, not prevalence or willingness to pay. Details: [comparison result](retention-policy-reconciliation-prototype.md#contract-level-comparison-result-october-28-2026).

### October 28 screen: deletion of session-derived agent memory

A source session can be deleted while its derived notes or index remain. The recent [AfterDeleteBench preprint](https://arxiv.org/abs/2610.31366) reports secret recovery after deletion in controlled fixed-weight agent-memory experiments and argues that deletion should be evaluated through fresh-session recall, not only storage state. This establishes a research problem in its tested setup; it does not measure prevalence or demand in coding-agent products.

The category already has direct overlap. [Antiburn's support documentation](https://github.com/antiburn/antiburn/blob/main/docs/support.md) says deleting a transcript does not immediately delete its derived data, but deleting its own session or index does. [agentic-session-explorer](https://github.com/junxit/agentic-session-explorer) exposes project memories with `originSessionId`, identifies memories whose source session was deleted, and supports memory deletion. A separate [Claude session deletion utility](https://github.com/genie360s/claude-session-deleta) documents cascading deletion across Claude session sidecars and memories linked by `originSessionId`. Newer direct coverage includes [Lethe Delete](https://lethe-delete.com/), which publishes a neutral benchmark over vector stores and signed deletion certificates; [MELT](https://github.com/shisa-ai/MELT), which evaluates memory lifecycle including provenance and revocation; and [MemoryStackBench](https://github.com/aetna000/MemoryStackBench), which benchmarks memory safety, evidence, deletion, and auditability. These are product descriptions and controlled evaluations, not independent effectiveness or market-demand evidence. They make a generic cross-store deletion verifier an occupied direction.

A possible residual is an automated, cross-tool check that asks whether a deleted synthetic fact can still be recalled from any configured memory store. Dedicated benchmarks and deletion-proof tooling now cover the broad workflow. Their public pages do not prove equal behavior on coding-agent-local stores, but that possible extension alone is not a product gap. Close this lead unless a concrete coding-agent store remains uncovered in a same-case comparison. Do not add deletion features or claim universal erasure.

### October 28 screen: tamper-evident agent traces

The [trace-tampering study](https://arxiv.org/abs/2609.30266) reports that tested local harnesses generally allowed agents to delete their own traces when instructed, and also studies external-triggered deletion. This is a controlled security finding; it does not establish attack frequency or buyer demand. The proposed generic product is already directly covered by [agent-pd](https://github.com/varmabudharaju/agent-pd), which documents hash-chained event logs and an optional off-host append-only sink; [nd7](https://nd7.dev/), which documents OS-level sandboxing and tamper-evident logs for Claude Code and Codex; and [Golem](https://docs.golem.team/guides/audit-trail), which documents signed, chained records across several coding agents. Pi offers a broad extension API, but it does not by itself create an independent trust boundary. Do not build another generic trace logger, hash chain, or viewer. No unserved outcome or paid demand is established.

### October 28 screen: repository-sensitive model routing

The user problem is plausible: a team may want sensitive repositories to use only approved models and provider routes. Direct coverage already exists. [PromptDLP](https://www.promptdlp.com/use-cases/source-code-protection.php) documents repository labels that trigger stricter handling and request interception before the model provider. [Routeur.ai](https://docs.routeur.ai/guides/dlp) documents DLP before forwarding to an upstream model; [MLflow AI Gateway](https://mlflow.org/docs/latest/genai/governance/ai-gateway/coding-agents/) supports Claude Code, Codex, and Gemini CLI routing plus guardrails; and [LiteLLM's harness-aware router](https://litellm.docs.miniasp.com/en/blog/auto-router-harness-aware-classification/) documents coding-harness-aware model selection. Cursor Enterprise adds model allowlists, BYOK controls, and admin model APIs ([docs](https://prod.cursor.com/docs/enterprise/model-and-integration-management)). These are product claims, not independently tested comparisons, but they cover the broad repo-sensitive routing and DLP workflow. The current session archive also cannot reliably establish account identity or actual route across all supported agents. Do not build another generic prompt DLP, model router, or repository allowlist. Reopen only for a named provider/task where a same-case comparison shows that current controls miss a consequential data-flow decision and a measured improvement. No product distinction, adoption, or willingness to pay is established.

### Screened lead: session-to-workspace binding before agent actions (October 28)

Three public Codex issue reports describe related but not proven-identical failures. In [#56631](https://github.com/openai/codex/issues/56631), a reporter saw existing chats acquire another project's saved working directory during session switching; the report says no command ran after the affected chat's observed cwd change. In [#24855](https://github.com/openai/codex/issues/24855), a Desktop reporter says a resumed chat loaded another workspace's cwd and instructions, and Git/repository actions were attempted before the mismatch was noticed. In [#42001](https://github.com/openai/codex/issues/42001), a Windows reporter says command execution intermittently used a stale directory even though task metadata and the command request contained the intended cwd. These are reports, not independent reproductions or frequency evidence, and may have different causes.

There is a concrete technical intervention to evaluate. Official [Codex hook documentation](https://learn.chatgpt.com/docs/hooks) exposes `session_id` and `cwd`, and supports pre-tool decisions for shell, `apply_patch`, MCP, and other local function tools, with documented exceptions. A global local registry could bind a session identifier to an expected repository/worktree identity and deny a mismatched action before it runs, without reading transcript text. This is a product hypothesis only: the current archive parser cannot enforce a live action, and Codex hook trust, bypass paths, and effective working-directory semantics need runtime verification. It may catch a resume whose pre-tool event reports another `cwd`; it does not automatically catch a runner that receives the intended `cwd` in metadata but starts the process elsewhere, as described in #42001.

The key competitive overlap is [Ordo Guard](https://ordo-engine.github.io/Ordo/docs/en/platform/guard). Its docs describe cross-agent pre-tool policies, `cwd` and `session_id` event fields, and a task context containing a root and optional session ID; a mismatch becomes explicit state. For the *visible wrong-cwd event* case, a correctly loaded Ordo context appears to express the needed rule already. Its published init flow is project-oriented, but public documentation alone does not prove whether the original project's hook remains active after a wrong-project resume. Coverage docs also differ: the official Codex contract describes interception of `apply_patch`, MCP, and most local functions, while Ordo says its Codex adapter currently sees Bash only. [Tuff](https://tuffcli.dev/primitives/policies/) documents policy parity across several agent runtimes and refuses installation when a runtime cannot enforce a rule. The adjacent security market includes [HOL Guard](https://hol.org/guard/docs/guard/get-started), which offers local-first runtime interception for many harnesses with paid cloud history/team tiers, plus [Agent Boundary Check](https://github.com/sylvesterkaczmarek/agent-boundary-check), [sandbox-probe](https://github.com/controlplaneio/sandbox-probe), and [BoundaryBench](https://github.com/boundary-bench/boundary-bench) for synthetic boundary tests or sandbox evaluations. Do not build a generic hook, guard, workspace-root boundary tool, or sandbox probe from this archive.

**Decision:** withdraw this as a product lead. Session/root guard logic and cross-agent sandbox probes are directly available, while a hook cannot prove the actual process directory from metadata alone. Preserve the reported Codex cases as possible regressions; do not add a guard or probe without a current-version reproduction that existing native and third-party controls fail to stop before a consequential action. No common defect, user prevalence, distinct value, or willingness to pay is established.

### October 28 screen: broad cross-agent continuity and evidence-backed memory

The broad continuity proposition is directly overlapped by [Motif](https://www.getmotif.dev/). Its public documentation describes a self-hosted, open-source tool for solo developers and teams that collects Claude Code, Codex, and Cursor sessions; exposes cited recall over MCP; links decisions to source reasoning; marks conflicts and possibly stale notes for human review; and writes native handoffs for supported agents. Motif also publishes a reproducible retrieval benchmark on its own corpus. Those are vendor-published capabilities and results, not an independent runtime comparison, adoption measure, or proof of demand.

[Crosshead](https://crosshead.sh/) separately describes hook-captured, source-backed checkpoints and signed handoffs across coding agents, with a local component and hosted operations. Its published description is also a product claim, not an independent verification. Other documented products include [Spooling](https://spooling.ai/) for cross-agent session indexing and team memory, and [Compaction.dev](https://www.compaction.dev/) for cross-agent handoff and compaction. This makes generic cross-agent search, memory, source-linked decisions, compaction continuity, and handoff a crowded direction for this repository.

**Decision:** do not build or market broad continuity, evidence-backed memory, or generic cross-agent handoff as a paid wedge. Keep the existing archive and handoff tooling as infrastructure. Continue only with a concrete user task where a same-case comparison against Motif and the closest available alternative shows a consequential outcome they miss, using synthetic data first. Then seek repeated-user and willingness-to-pay evidence before selecting a product direction. No such unmet outcome, independent performance advantage, adoption, or willingness to pay is established. Do not use personal transcripts or exports in public research artifacts.
