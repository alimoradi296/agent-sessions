# Approval provenance screen

**Date:** 2026-10-28
**Status:** Closed as a standalone product lead; no competitor runtime or buyer validation performed.

## Signal

An approval recorded under a human GitHub account may not establish that the person made the decision. A useful control would need to separate account identity, human sponsorship, agent activity, review authority, and the exact revision that passed the merge gate.

## Evidence and existing coverage

- The [single-organization study](https://arxiv.org/abs/2610.28683) reports that 71 of 263 non-bot merges in one fintech's gated period rested only on an approval submitted by an agent through a technical lead's account. Its authors say the records cannot establish who decided. The study also reports disabled enforcement and other gate failures. This is a serious case report, not a prevalence estimate or independent market validation.
- [GitHub's human review guidance](https://github.github.com/gh-aw/reference/compliance-patterns/) explicitly separates a publishing identity from evidence of human sponsorship or review. It recommends recording the trigger, workflow revision, human assignment, proposed diff, checks, review approvals, and merge record.
- [GitHub branch protection](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches) supports required reviews, code-owner reviews, stale-approval dismissal, approval of the latest push, status checks, and restrictions on bypass. These controls can address parts of the gate when configured and protected appropriately.
- [Gilded Code](https://gildedcode.com/) publicly describes a GitHub-native evidence product for AI-assisted pull requests, including human and agent attribution, permissions, review gates, checks, artifact hashes, and durable evidence packs. Its site says it is building the product and seeking design partners; this screen did not verify a running product, adoption, or efficacy.

## Decision

Close a generic approval-provenance or merge-evidence product for this repository. GitHub provides configurable review controls, and Gilded Code states a direct evidence-product overlap. The study gives one compelling organizational case, but it does not establish a distinct opportunity for this session-exporter repository. Do not build a GitHub app, approval monitor, governance dashboard, or audit-pack generator from this signal.

Reopen only if a concrete workflow shows a costly gap that remains after appropriate GitHub controls and is not covered by an available evidence product. That would require a reproducible synthetic case, a measured comparison, and buyer evidence. No private session data is needed for this screen and none was used.
