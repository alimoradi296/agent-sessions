# Parallel-agent duplicate-work screen

Date: 2026-10-28

## Candidate

Detect when concurrent coding agents are spending tokens and engineering time on the same task or implementation, then redirect work before duplicate patches reach review.

## Evidence

The research paper [Scaling Inference-Time Compute with Teams of Coding Agents](https://arxiv.org/abs/2610.17471) reports that multi-agent teams can create duplicate work and higher cost. In its ProgramBench experiments, delegating only planning and keeping implementation and verification with the lead matched a plan-implement-verify team at half the cost. The paper also reports that results vary by task: implementation workers helped more on Commit0, where the repository already supplied the plan. These are benchmark results, not production prevalence or buyer evidence.

Direct product descriptions already cover the proposed intervention:

- [Coordigent](https://coordigent.com/) says cross-agent visibility can reveal when another agent is building the same thing and stop duplication.
- [Co-Vibe](https://co-vibe.dev/) says it compares declared work with active and recent work, then warns or blocks before a pull request.
- The [Nerveplane scheduling paper](https://arxiv.org/abs/2610.07261) evaluates proactive scope partitioning and merge ordering against reactive coordination, including a benchmarked reduction in failed integrations. Its results are author-reported research, not independent validation of the product.
- GitHub Next's [Duplicate Code Detector](https://github.com/githubnext/agentics/blob/main/docs/duplicate-code-detector.md) looks for repeated code after changes and opens refactoring issues; this is adjacent post-change cleanup rather than duplicate-task prevention.

## Decision

Close generic duplicate-work detection as a product lead. The proposed before-work warning and coordination workflow are directly claimed by existing products; a session-exporter implementation has no demonstrated incremental outcome. Public product claims and benchmark results do not establish actual adoption, reliability, or willingness to pay.

Reopen only if a real, repeated duplicate-work case occurs despite the current coordination tools and a controlled comparison shows a material cost reduction. No such case or buyer evidence is established here.
