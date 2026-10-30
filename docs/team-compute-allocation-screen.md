# Task-aware team compute allocation screen

Date: 2026-10-28

## Candidate

Choose how many coding agents to use and which phases to delegate, based on task properties and observed verified outcomes, so a user can reduce cost without increasing failed work or rework.

## Evidence

The study [Scaling Inference-Time Compute with Teams of Coding Agents](https://arxiv.org/abs/2610.17471) evaluates worker count, model choice, and delegation stage on ProgramBench and Commit0. It reports that teams cost 3–7 times a solo run on ProgramBench, and that planning-only delegation matched planning, implementation, and verification delegation at half the cost in one setting. The best allocation varied by benchmark. These are results from the paper's harness and tasks; they do not establish production savings, repeated user demand, or willingness to pay.

Public product documentation covers adjacent pieces:

- [GitHub Agentic Workflows model routing](https://github.github.io/gh-aw/reference/model-routing/) selects a model and reasoning effort for each workflow run, trading cost against estimated task success. Its documentation describes model routing, not selecting coding-agent team size and delegation stage from verified repository outcomes.
- [AgentOpt](https://agentoptimizer.github.io/agentopt/) searches model combinations across agent steps against an evaluation dataset, measuring accuracy, cost, and latency. Its documented optimization is model configuration; this screen found no documented team-size policy learned across repository outcomes.
- [VECTA](https://vecta.build/parallel-coding-agents/) documents concurrent agent tasks, agent teams, per-task reported cost/time/tokens, and budgets. Its product page documents coordination and visibility; it does not establish an outcome-learned allocation policy.
- The [Nerveplane scheduling paper](https://arxiv.org/abs/2610.07261) evaluates proactive task-scope partitioning and merge ordering. Its reported benchmark results concern coordination and integration, not willingness to pay for allocation analytics.

This is a bounded documentation screen. A missing feature in public documentation does not prove a product lacks it. No runtime comparison, buyer interview, deployment evidence, adoption measurement, or pricing validation was performed. No personal session data was used.

## Decision

Keep as a research question only; do not build or claim that no other repository can do this. Public evidence shows adjacent products and benchmark evidence that allocation choices can affect cost and outcomes, but does not establish a distinct product gap or commercial value.

Reopen only if a user workflow can supply lawful, privacy-safe task and outcome data, and a controlled evaluation demonstrates a better cost-versus-success decision than existing routing, orchestration, and fixed policies. Then validate that users will pay for the measured improvement before implementation.
