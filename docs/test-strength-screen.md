# Agent-edited test strength screen

Date: 2026-10-28

## Candidate

Detect when a code change passes because its tests or test configuration were weakened, and show the exact behavior that the tests no longer catch.

## Evidence

Mutation testing answers whether tests detect selected injected faults. Existing tools and agent-facing integrations already apply that technique:

- [Radforge](https://www.radforge.dev/) advertises changed-code mutation tests in a pre-merge workflow, with surviving mutants tied to behaviors the tests do not protect.
- [`agentic-verification`](https://github.com/timini/agentic-verification) documents a Claude Code plugin and GitHub check that mutates changed production code and fails when tests do not catch the mutants.
- [`testtruth`](https://socket.dev/npm/package/testtruth) describes comparing the same mutants before and after a pull request to detect weakened tests.
- [`Assist CLI`](https://github.com/emanuelepiodebernardis/Assist_CLI-V2) documents local hooks and a GitHub Action that use test and mutation evidence for a verdict.
- [The agent test-generation study](https://arxiv.org/abs/2602.07900) finds that agents often use tests as observational feedback rather than assertion-based checks. [Another study](https://arxiv.org/abs/2602.00409) reports agent commits change tests more often than non-agent commits in its sampled repositories. Neither establishes production incident rates or buyer demand.

These sources establish that the concern and several mechanisms are public. They do not prove the tools work reliably in arbitrary repositories or that every test weakening is undesirable.

## Decision

Close generic test-strength and mutation-testing checks as a product lead. Existing projects cover changed-code mutation checks, test-strength comparison, hooks, or CI gates. No uncovered decision, incremental outcome, prevalence, adoption, or willingness to pay is established for this repository.

Reopen only for a reproducible case where current mutation and test-strength tools fail to detect a consequential weakened behavior, with a controlled comparison and user evidence. Do not include private transcripts or user code in public artifacts.
