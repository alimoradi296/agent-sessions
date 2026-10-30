# Native-session regression case screen

Date: 2026-10-28

## Hypothesis

When a coding agent makes a mistake that a developer later fixes, the saved native session may contain enough task, tool, and change evidence to create a small, private regression case. The proposed value is to keep the same mistake from recurring after an agent, model, instruction, or repository change, including across different coding tools.

The possible distinction is retrospective import from ordinary Claude Code, Codex, and Cursor session archives without having installed a recorder before the failure. This is a hypothesis about workflow fit, not a uniqueness claim. Public evidence does not establish demand, willingness to pay, or reliable automatic adjudication.

## Existing coverage

| Source | Documented overlap | Limit for this hypothesis |
|---|---|---|
| [Chronicle](https://arxiv.org/abs/2609.20625) | Records nondeterministic agent boundaries and uses cut-point replay to turn recorded incidents into regression tests. | Research prototype with six benchmark failures; the paper does not establish import from existing native Claude/Codex/Cursor archives. |
| [Promptfoo coding-agent evaluations](https://www.promptfoo.dev/docs/guides/evaluate-coding-agents/) | Runs coding agents such as Codex, Claude Agent SDK, and OpenCode against evaluation cases and checks outcomes. | The guide documents evaluation execution; it does not establish automatic creation of cases from ordinary local session archives. |
| [Converra trace-to-test guide](https://converra.ai/blog/build-ai-agent-regression-suite-from-production-traces) | Describes converting a production trace into a minimal, adjudicated regression case, with privacy, controls, and baseline review. | A methodology article, not evidence of a product's comparative results or buyer demand. |
| [Agentmine](https://agentmine.io/) and [AgentsView](https://www.agentsview.io/) | Provide searchable local coding-agent session archives and transcript-oriented analysis. | Public descriptions do not establish an end-to-end, adjudicated regression-case workflow. |
| [`evals-from-sessions`](https://github.com/ibragim-bad/evals-from-sessions) | An MIT-licensed Claude/Codex/Pi skill copies coding-agent sessions, extracts task episodes, builds verified Harbor evaluation tasks, checks the verifier, and prepares them for cross-agent/model comparison. It requires human review at candidate, spec, and finished-task checkpoints. | Direct overlap with mining ordinary session histories into private agent-evaluation tasks. Its README is a product description, not independent runtime, quality, adoption, or willingness-to-pay evidence. |
| [CodeProbe](https://www.sjarmak.ai/projects/codeprobe), [RepoBench](https://github.com/felipcsousa/repobench), and [Fullbeam](https://www.fullbeam.ai/product/private-qualification) | Mine repository PR/Git history into private, verifier-backed evaluations for comparing coding-agent configurations on local or private repository work. | Direct overlap with repository-personalized agent evaluation, using PR history rather than native-session task mining. Public descriptions do not establish comparative execution quality or buyer outcomes. |
| [Entire CLI and SWE-chat](https://github.com/entireio/cli) | Records sessions on checkpoint branches, links sessions to commits, and supports line-level authorship and code-survival analysis. The SWE-chat paper reconstructs sequential file edits against base and committed states. | It requires opt-in checkpoint instrumentation, so it does not establish retrospective import from ordinary native archives or reviewed regression-case generation. The paper includes only sessions whose commit-level lines can be unambiguously attributed in one relevant analysis (47.7% of its sessions). The related [SWE-chat dataset](https://huggingface.co/datasets/SALT-NLP/SWE-chat) is gated and requires agreeing to share contact information; its files were not accessed. |

## Fit with this repository

The repository already parses native Claude Code, Codex, and Cursor histories, preserves source coordinates, and can relate some recorded tool results to captured file changes. It does not decide that a historical outcome was wrong, infer the expected behavior, build a minimized executable case, or replay that case against another agent. Those are substantial missing capabilities.

The core risk is incorrect test generation. A transcript can record a failed command or a later correction without proving the user's intended behavior. A useful case needs a human-approved failure mechanism, expected result, clean control, minimal context, and privacy review. A raw transcript replay is neither a regression test nor safe fixture data.

## Synthetic feasibility probe (October 28)

[`examples/evaluate_native_session_regression.py`](../examples/evaluate_native_session_regression.py) creates temporary fictional Claude, Codex, and Cursor records. In each positive case, the existing parsers retained source-line references for a task request, a failed test result, a captured patch, and a later successful run of the same command. Applying the captured patch to a separately authored synthetic base reproduced the failing-to-passing test change for all three providers. The JSON report emitted no transcript text. Clean, unrelated-test, documentation-edit, and different-module controls were not selected.

The same-target-flaky control *was* selected: the same test command failed, a comment-only edit in the target source file followed, and the recorded run then passed. Replaying that captured edit against the authored synthetic base left the test failing, so the recorded pass was not reproduced. Four of eight cases were selected: three authored positives plus this false candidate. This is one authored false candidate, not an estimated false-positive rate.

The test base, oracle, and environment were authored for this probe; they were not reconstructed from any provider's native archive. The current synthetic sessions contain no `git rev-parse HEAD` or clean-worktree result. Source inspection found that Claude and Codex parsers retain a working directory and branch, while Cursor retains a project slug; none of those fields alone pins the exact pre-change tree. The report therefore marks all cases as not replayable from the archive, even though the three positive patches pass against the separately authored base.

A separate synthetic anchor control recorded `pwd`, `git rev-parse HEAD`, and `git status --porcelain`. All three parsers retained enough evidence to recognize a clean baseline, and the pinned commit object existed in the temporary repository during the check. A dirty worktree and a missing status capture were both rejected as ready baselines. This only proves the parser can interpret such recorded commands; it does not show that ordinary sessions contain them, that the Git object remains available later, or that the captured commands ran before any agent changes.

## Git transition reconstruction probe (October 28)

[`examples/evaluate_git_base_reconstruction.py`](../examples/evaluate_git_base_reconstruction.py) searched temporary Git histories for an exact one-file before/after transition without being given a commit ID. It found one unique full transition when the edit was committed alone, no reachable transition when it remained uncommitted, two candidates when the same edit appeared on two branches, and only a partial match when an unrelated file was included in the commit. The probe emitted no commit IDs or project content.

This shows that Git history can supply a candidate parent tree in a narrow, favorable case. It does not link that commit to a particular native session, establish a clean worktree at session start, recover untracked files or dependencies, or show that ordinary archives have enough evidence to run the matcher. A matching source transition is a candidate baseline, not a verified historical workspace or regression case.

This distinguishes patch replay mechanics from historical reproduction. The archive source does not currently establish the exact initial repository state needed for safe replay. The probe does not measure setup savings, review effort, or product advantage.

## Public benchmark lead (October 28)

The [GOAT Agentic Coding Sessions corpus](https://goat.ai/gatc/) documents a public 1% sample of 1,189 sessions under Apache-2.0, drawn from a 117,796-session corpus. Its published tables include ordered tool traces, code edits, and tool outcomes. The schema uses pseudonymous project IDs and provides only a Boolean `git_commit_made`; it does not expose a source repository or commit identifier. Thus the sample could estimate event-extraction frequency, but cannot test reconstructing a clean starting tree or the core retrospective replay promise. The source says records are pseudonymized, not anonymous, and project/code identifiers may remain. No sample rows were opened, downloaded, or copied. A separate GitHub Copilot trace release is metadata-only and excludes prompt, tool-output, code, and diff content, so it also cannot answer the replayability question.

## Decision and next gate

Close retrospective native-session-to-regression generation as a product lead. The new `evals-from-sessions` project directly documents mining ordinary local session history into private, verified evaluation tasks; CodeProbe, RepoBench, and Fullbeam cover the neighboring repository-history benchmark workflow. This materially weakens the proposed uniqueness claim. The existing synthetic work remains parser/recovery research: it shows event extraction and patch replay against authored fixtures, not that this repository improves task extraction, verifier quality, privacy, setup effort, or evaluation outcomes over those tools. No competitor was run and no buyer comparison was performed. Keep the useful parsers as infrastructure; do not implement or market this product without a specific measured advantage and buyer evidence.

Proceed only if the case is executable, a reviewer can verify its expected behavior, and archive import adds a measurable reduction in setup or review work over manually authored evals. Before any real-archive pilot, keep all source data private and obtain explicit approval for its use. Even a successful synthetic probe would establish feasibility only; repeated user value and paid demand would remain unproven.
