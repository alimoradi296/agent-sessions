# Session-to-workspace binding screen

Date: 2026-10-28

## Candidate

Bind an agent session to the intended repository and worktree, then check that identity before tool actions. The proposed safety outcome is to stop a resumed session from reading or changing another project when a client restores the wrong working directory.

This is a research lead, not a selected product. The current archive can describe saved session metadata; it cannot block a live tool action. A live guard would be a scope change from archive inspection and must show an advantage over existing agent guardrails.

## Public problem reports

- [Codex issue #56631](https://github.com/openai/codex/issues/56631) describes two session-switching occurrences where saved working directories changed. The reporter says no command ran after the changed directory was observed in that occurrence.
- [Codex issue #24855](https://github.com/openai/codex/issues/24855) describes a Desktop continuation loading a different workspace and its instructions; the reporter says Git/repository operations were attempted before the mismatch was noticed. Its public report redacts local names and paths.
- [Codex issue #42001](https://github.com/openai/codex/issues/42001) describes a Windows command running in a stale directory even though task metadata and the command request had the intended `cwd`.

These are issue reports, not independently reproduced cases, prevalence estimates, or evidence of one shared root cause.

## Feasibility evidence

The [official Codex hook contract](https://learn.chatgpt.com/docs/hooks) exposes `session_id` and `cwd`, and documents `PreToolUse` decisions for shell calls, `apply_patch`, MCP, and other local function tools. It also documents that some specialized paths can bypass the default hook path. A local user-level hook could compare an event with a locally stored session-to-worktree binding without reading or transmitting transcript content.

This can potentially catch a resume where the event itself reports the wrong `cwd`. It does not prove that a guard sees the effective working directory of every tool, remains enabled through a misbound resume, or blocks every side effect. In particular, a command runner could receive the expected directory in metadata and still launch the command elsewhere; a pre-tool hook may see the request rather than the resulting process directory. The #42001 case therefore requires a separate executor-path check. Hook trust, timeout/error behavior, managed configuration, and platform coverage need runtime validation.

## Competitive baseline

[Ordo Guard](https://ordo-engine.github.io/Ordo/docs/en/platform/guard) documents cross-agent pre-tool policies for Claude Code, Codex, and Cursor. Its event fields include `cwd` and `session_id`; its task context contains a root and optional session ID and reports a mismatch when scope does not match. For the *visible wrong-cwd event* case, a correctly loaded Ordo context appears to express the needed rule already. Its published init flow is project-oriented, but public documentation alone does not prove whether the original project's hook remains active after a wrong-project resume.

The documented tool coverage is not fully aligned: the current [Codex hook reference](https://learn.chatgpt.com/docs/hooks) says pre-tool hooks cover `apply_patch`, MCP, and most local function tools, while Ordo's published guard page says its Codex adapter currently sees Bash only. This difference may reflect adapter/version scope. It makes a pinned, end-to-end runtime comparison necessary before claiming complete prevention.

[Tuff policies](https://tuffcli.dev/primitives/policies/) document cross-agent policy handling and refuse installation when a client cannot enforce a rule. VS Code also documents workspace-limited access for built-in agent tools. These controls make a generic action guard or path allowlist an occupied direction.

The adjacent sandbox-testing category is also occupied. [Agent Boundary Check](https://github.com/sylvesterkaczmarek/agent-boundary-check) says it tests what a coding agent can read, write, execute, and reach with synthetic canaries. [sandbox-probe](https://github.com/controlplaneio/sandbox-probe) documents sandbox inventory and regression probes across agent harnesses. [BoundaryBench](https://github.com/boundary-bench/boundary-bench) benchmarks task capability under hardened sandbox policies. These are public descriptions, not independently verified results, but they cover the proposed expansion into cross-agent boundary testing.

[HOL Guard](https://hol.org/guard/docs/guard/get-started) documents local-first interception across Codex, Cursor, Pi, Claude Code, and other harnesses, with paid Cloud plans for synchronized history and team controls ([pricing](https://hol.org/guard/pricing)). Its published advisory explicitly says its current controls do not establish a universal workspace-root boundary. This is evidence of a bounded product limit, not proof that this repository can close it; native sandboxes and dedicated probes already address adjacent parts. The listed Pro price is a posted offer, not evidence of sales or demand for this repo.

## Product decision

Withdraw this as a product lead. Ordo directly documents session/root matching; HOL Guard covers local runtime interception across agents; sandbox-probe and Agent Boundary Check exercise actual boundaries; and native clients provide sandbox controls. A reported client bug may deserve a runtime regression test or upstream fix, but the current archive cannot reliably prevent a runtime from ignoring its requested working directory. No distinctive outcome or willingness to pay for another guard is established.

## Synthetic control-flow comparison (documentation model, not runtime)

The cases below apply the published event fields and Ordo scope rules to invented values. This is not a run of Ordo or a coding-agent client.

| Case | No guard | Ordo root + session scope, if its hook runs | Global binding hook | Incremental value shown |
|---|---|---|---|---|
| Event reports session A in repo B; saved binding is A → repo A | Side effect is unguarded | Scope is `mismatch`; a policy can deny | Can deny on the same mismatch | None shown over an active Ordo hook |
| Event reports repo A, but the command process starts in repo B | No check | Request appears in scope; actual process cwd is not in the documented event contract | Same visibility limit | Neither pre-tool rule proves the executor's effective directory |
| Legitimate worktree moved or recreated | No check | Root check may mismatch | Path-bound rule may mismatch | Needs an explicit rebind/recovery flow; no measured advantage |
| Session has no binding | No check | Missing context is not automatically a deny; policy must require it | Could fail closed | Configuration/availability behavior remains untested |

The comparison rules out the easy differentiation claim: reimplementing `cwd` + `session_id` matching does not beat Ordo when Ordo is active. The only residuals are whether its project-local hook remains active after a wrong-root resume and how to attest the process's effective directory. The first is an untested deployment question; the second requires instrumentation beyond the documented pre-tool event. Neither currently supports a product build.

## Reopen only if

Keep the three public issue reports as candidate regression scenarios. Reopen product work only if a current-version, synthetic reproduction shows that native sandboxing and existing global guard controls both fail before a consequential action, and an independently installed session/worktree binding prevents that action without blocking legitimate moved worktrees. A report, synthetic mechanism check, or passing scenario alone would not establish prevalence, product distinction, adoption, or willingness to pay.
