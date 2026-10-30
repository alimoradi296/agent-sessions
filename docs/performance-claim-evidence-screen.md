# Agent-authored performance claim evidence screen

Date: 2026-10-28

## Candidate

Help maintainers decide whether a performance-oriented pull request has reproducible, quantitative evidence for its intended improvement and relevant trade-offs, especially when an agent reports that it validated the change.

## Evidence

The preprint [How Do Coding Agents Optimize Software and Report Performance Validation?](https://arxiv.org/abs/2610.03969) analyzes 1,130 agentic and 1,130 human-authored performance pull requests. It reports that 82.3% of agentic PRs and 80.6% of human PRs reported some validation. Among PRs with validation evidence, only about half in either group reported a performance metric. This is a defined public dataset, not a measure of all repositories or proof that a specific product is needed.

Existing tools cover much of the proposed job:

- [CodSpeed](https://codspeed.io/) documents continuous benchmarks, pull-request checks and comments, regression detection, differential flamegraphs, and an Optimization Agent that benchmarks its proposed fixes and opens PRs.
- [Bencher](https://bencher.dev/) documents continuous benchmarking, bare-metal measurements, and performance-regression checks in CI.
- [PERFOPT-Bench](https://arxiv.org/abs/2607.07744) and [FormulaCode](https://formulacode.org/) evaluate agentic code optimization against performance benchmarks. These are evaluation resources, not evidence of a product buying market.

This screen did not run a competitor or benchmark. Public materials cannot establish implementation quality, adoption, or whether existing systems verify every claimed metric and trade-off.

## Decision

Close the generic performance-validation product lead. Continuous benchmark and optimization products directly cover measurement, regression reporting, and agent-proposed fixes. The residual idea—checking whether selected metrics adequately support the specific claim and workload—is not established as a distinct buyer workflow here. No unique advantage, prevalence beyond the cited corpus, user demand, or willingness to pay is established.

Reopen only with a concrete PR case where existing performance tooling gives reviewers an incomplete or misleading answer, and a controlled evaluation shows that a session-linked evidence check changes a consequential merge decision. Do not use private session data in public artifacts.
