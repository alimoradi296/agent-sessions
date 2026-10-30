# Worktree runtime integrity screen

Date: 2026-10-28

## Candidate

When multiple coding agents use separate Git worktrees, a test can still talk to a server or database owned by another checkout. The test may pass while validating the wrong code or shared state. The candidate is a local gate that verifies the server and mutable data target belong to the worktree under review before accepting a browser or integration-test result.

This is narrower than provisioning worktrees or copying environment files. The proposed outcome is a trustworthy answer to: “Did this check exercise the code and state for this agent's worktree?” Whether teams will pay for that answer is unknown.

## Evidence of the failure

The [VS Code issue on worktree dev-server ports](https://github.com/microsoft/vscode/issues/313472) describes an agent worktree auto-selecting a new port while the developer and Playwright continue using the main checkout's hard-coded `localhost:3000`. The maintainer suggested choosing an open port and said VS Code had no platform solution at the time; the issue closed as not planned. This is one reported workflow, not a prevalence estimate.

Other public reports describe shared database, queue, and service state across otherwise isolated worktrees. They are useful problem signals, not independent confirmation of frequency. The [AgentSlots repository](https://github.com/hishamalward/agent-slots) describes a queue job handled by stale code in a shared runtime as its motivating incident; this is the project's own account.

## Existing coverage

| Tool or platform | Documented capability | What it does not establish for this candidate |
|---|---|---|
| [Supabase local projects](https://supabase.com/features/parallel-local-projects) | Per-worktree Postgres/Auth/Storage services and stable separate ports | General verification that arbitrary browser or test traffic reached the intended Git revision |
| [fed](https://www.service-federation.com/docs/isolation/) | Worktree-directory-scoped containers, volumes, state, and declared port parameters | Protection for hard-coded ports or proof that tests used the isolated target; its docs warn literal ports are not remapped |
| [AgentSlots](https://github.com/hishamalward/agent-slots) | Per-worktree ports, PostgreSQL, queue schema, and service lifecycle | Universal project support or independent proof that an arbitrary test targeted the correct runtime |
| [Neroli](https://neroli.dev/coding-agent-workspaces/) | Worktree, terminals, services, provider context, and verification attached to each task | Public docs do not specify a check that rejects a green test against a different worktree's running server |
| [VS Code Agents](https://code.visualstudio.com/docs/agents/concepts/sessions) | Conversation forks and worktrees, depending on the harness | A fork may share the source worktree; conversation branching alone does not isolate runtime state |

These public descriptions show that resource allocation and workspace orchestration are already active categories. The possible gap is runtime-target attestation, not generic worktree creation, port allocation, or database provisioning. The source review does not prove that the listed tools lack such a check internally.

## Evaluation evidence

### Synthetic two-worktree HTTP check (2026-10-28)

A disposable Git fixture created separate main and agent worktrees and ran local HTTP servers. A normal test request returned green against the main checkout while the agent worktree was under review. The identity gate accepted the expected agent server and rejected the main checkout, a stale server from the same worktree after a new commit, and a server reporting the shared `db-main` namespace. The fixture used an app endpoint that reported its startup Git revision, source digest, and test namespace.

This proves the comparison can reject these four authored cases in one cooperative standard-library app. It does not test a browser runner, a real database, multiple application stacks, arbitrary apps, or independent attestation. A loopback attempt was initially blocked by the default sandbox; the local-only synthetic rerun succeeded with the required permission. No external service or personal data was used. The app endpoint remains a material setup burden, and no product advantage is established.

### Linux process-ownership probe (2026-10-28)

A second disposable fixture mapped each local listening port to its process PID using Linux process/socket inspection. The verifier read the process working directory, a wrapper-provided launch SHA, and a configured database path. It distinguished the main checkout from the agent worktree, detected a server whose worktree advanced after launch, and detected a shared database path. This is a synthetic Linux mechanism check, not portable runtime coverage. A process started without the wrapper has no trusted launch SHA; an environment database path describes configuration, not the connection actually used by the app.

### Direct overlap and decision

The [Nexus Agents worktree guide](https://nexus-substrate.github.io/nexus-agents/docs/guides/parallel_agent_worktrees/) documents this exact false-green case: Playwright's `reuseExistingServer` can test the first worktree's bundle. Its stated fix is a unique port per worktree. [AgentSlots](https://github.com/hishamalward/agent-slots) attaches per-worktree ports and databases, derives state from Git and listening ports, and records process identity for safe lifecycle operations. These public docs do not prove either tool catches every wrong-target case, but they cover the central failure and its practical remedy.

Close test-target integrity as a product lead. Keep the probes as research only; do not build another worktree manager or local process dashboard. This screen establishes neither market prevalence nor willingness to pay. Reopen only if a reproducible wrong-target failure persists after per-worktree port/resource assignment and available tools cannot identify it.

## Decision

Close test-target integrity as a product lead. One synthetic dual-worktree HTTP app and a Linux process-ownership fixture detected authored wrong-worktree, stale-server, and shared-namespace cases. They required either cooperative app identity or a launch wrapper, and did not validate a browser or live database connection. Nexus Agents documents the same wrong-bundle failure and unique-port remedy; AgentSlots covers per-worktree resources and process lifecycle identity. No distinct product outcome, prevalence, or paid demand is established. Keep the probes as research only and reopen only for a reproducible gap these tools do not address.
