# Agent skill evaluation and security screen

Status: closed as a generic product direction after a current competitive search. No local runtime comparison or willingness-to-pay evidence was collected.

## Hypothesis screened

Agent skills package instructions, files, and optional scripts that change how coding agents act. A potential product could evaluate whether a skill improves task results, detect harmful behavior, or govern which versions teams install across Claude Code, Codex, Cursor, Pi, and other hosts.

## Direct and adjacent coverage

- [NVIDIA SkillEvaluator](https://github.com/NVIDIA/SkillEvaluator) documents static checks, semantic overlap checks, synthetic evaluation-set generation, and live agent evaluation with and without a skill. NVIDIA also describes publishing integrations for Claude Code, Codex, and Cursor in its [product write-up](https://developer.nvidia.com/blog/evaluating-ai-agent-skill-performance-with-nvidia-skillevaluator/).
- [agent-skill-eval](https://github.com/tardigrde/agent-skill-eval) evaluates skills through real harnesses, including Claude Code, Codex, and OpenCode, with suite manifests and CI-oriented thresholds.
- Security scanners include [NVIDIA SkillSpector](https://github.com/NVIDIA/skillspector), [SkillWard](https://github.com/Fangcun-AI/SkillWard), and [Skill Sentinel](https://github.com/enkryptai/skill-sentinel). Their public descriptions cover prompt injection, malicious scripts, data exfiltration, supply-chain risks, and multi-stage or sandbox analysis.
- Runtime-focused research includes [Runtime Skill Audit](https://arxiv.org/abs/2606.11671), [MalSkillBench](https://arxiv.org/abs/2606.07131), [AgentTrap](https://arxiv.org/abs/2605.13940), and [Cloak and Detonate / SkillDetonate](https://arxiv.org/abs/2607.02357). These works evaluate behavior under agent execution, not only static text inspection.
- Enterprise discussions and products already frame skills as versioned, approved, auditable supply-chain assets. Security review, live quality evaluation, and governance are active categories.

## Decision

Do not build another generic skill benchmark, skill scanner, or skill registry. Published research reports meaningful coverage limits for individual scanners, but those results do not establish a distinct commercial workflow for this repository. A limited search cannot prove that no unlisted competitor exists.

Reopen only around a specific costly behavior missed by both the available static and runtime tools, reproduced in an isolated synthetic environment and tied to a buyer's decision. Any positive synthetic result would still need deployment and pricing evidence before this becomes a commercial direction.

## Privacy and evidence limits

This screen used public project descriptions and papers only. No skill package was downloaded, executed, or installed. No private session history or personal data was read for this comparison.
