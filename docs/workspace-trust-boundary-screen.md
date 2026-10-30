# Agent workspace trust and setup supply-chain screen

**Date:** 2026-10-28
**Status:** Generic scanner/package-manager lead closed; one session-level evidence question remains unvalidated.

## Signal

The paper [Scanning the Harness](https://arxiv.org/abs/2609.07360) reports that, within its manually validated 3,171-repository corpus, 16.0% of 2,660 multi-component setups had at least one defect in the paper's defined categories. The measured categories include unpinned MCP servers and overly broad execution permissions. This is a corpus-specific prevalence result, not a market-size estimate or proof of paid demand.

[Forever Security's October report](https://forever.security/blog/hijacking-ai-agents-via-downloads-folder) describes blocking an agent from acting on a hostile instruction file placed in a user's Downloads directory. The available reporting says the researchers reproduced behavior with Codex and Claude Code, but does not provide an independently audited trial matrix. Treat it as a credible reported incident and reproduction, not a frequency estimate.

## Direct coverage found

- [mcp-audit](https://mcp-audit.dev/) scans repository agent settings, instruction files, MCP configs, editor tasks, and related files; its site documents local read-only scanning, editor extension, pre-commit, and CI use.
- [AgentShield](https://github.com/affaan-m/agentshield) documents scanning user and project config, permission rules, instruction injection patterns, hooks, MCP definitions, and persistence surfaces.
- [aisecscan](https://github.com/jassics/aisecscan) documents scoped scanning of Claude settings, permissions, hooks, MCP servers, skills, commands, and instruction files.
- [Microsoft APM](https://microsoft.github.io/apm/) documents a cross-harness manifest and lockfile with exact versions, content hashes, and install policy. [AgentPack](https://github.com/OlegHQ/agentpack) documents a similar multi-harness dependency manager and lockfile.
- [OpenAI's Codex security plugin](https://github.com/openai/plugins/blob/main/plugins/codex-security/references/config-preflight.md) documents layered config and trust checks, including project trust and effective runtime overrides.
- [AER](https://aer.run/) documents signed execution records for Claude Code, Codex CLI, Antigravity, and OpenCode, including tools, programs, hosts, files, and models. Its default record is metadata-only and omits prompts and tool argument values.
- [Swif](https://help.swif.ai/en/articles/16814906-swif-ai-agent-activity-monitoring-policy) documents cross-agent endpoint session collection, review of prompts and tool activity, and optional controls for Claude Code, Codex, and Cursor. It explicitly warns that uploaded records can include sensitive prompts, paths, arguments, and results.
- [AgentSight](https://agentsight.us/) documents local session artifacts plus runtime links between model calls, commands, files, processes, and network activity across Claude Code, Codex, and other agents.

These are documentation claims; this screen did not install or run the tools. Their coverage is sufficient to reject a generic static scanner, generic `AGENTS.md` checker, agent package manager, or generic session evidence receipt as a novel wedge.

## Remaining question

Static repository scans answer what files contain; package managers answer what was pinned; a preflight can inspect configuration layers. Runtime visibility also exists: Claude Code's [`InstructionsLoaded` hook](https://code.claude.com/docs/en/hooks) reports an instruction file's path, scope, and load reason, while [VS Code agent diagnostics](https://code.visualstudio.com/docs/agent-customization/custom-instructions) expose discovered instructions and response references. Pi documents that its model context combines the active branch, system prompt, discovered context files, available tools, and loaded skill descriptions, although that page does not itself establish a complete persisted receipt of each input's exact bytes.

A narrower hypothesis is that a team may need a tamper-evident, cross-agent receipt of the exact inputs a specific session actually saw and could use: resolved working directory and trust decision, effective instruction sources and content hashes, enabled hooks/MCP tools, client version, and changes to those inputs during the session. The cited runtime facilities and provider session formats may already cover enough of this. That gap is not established.

That is not established as a gap. Current session exporters may omit the exact effective context, but products that capture runtime file and process events can plausibly reconstruct much of it. No customer decision that the receipt changes has been found. The receipt could also be operationally incomplete or leak paths and config details. Do not prototype unless a concrete gap survives direct runtime comparison and a buyer decision is established. Do not collect or publish real transcripts, paths, secrets, or personal configuration.

## Decision gate

Close the generic session-receipt lead. Existing runtime and endpoint evidence products cover too much of the proposed workflow to justify a synthetic prototype without a specific unmet buyer question. The reported incident and corpus study establish relevance, not product distinction or paid demand. Continue discovery in a different workflow category; do not build a scanner, lockfile manager, or observability dashboard from this screen.
