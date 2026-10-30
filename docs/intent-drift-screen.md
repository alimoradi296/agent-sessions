# Intent-to-diff review screen

Run date: October 28, 2026.

## Candidate

Use an agent's session to compare requested intent, assumptions, and validation with the final pull-request diff, then help a human review scope drift.

## Public evidence

- [Review Assist](https://github.com/uditk2/review-assist) describes turning Claude Code or Codex sessions into a guided, verifiable pull-request review. Its intent document records what was asked, assumed, tried, and verified; a validator checks coverage of the diff. The README says the session transcript stays local, while its GitHub app reads repository code and pull-request data per request.
- The [ARCTIC paper](https://arxiv.org/abs/2607.29516) describes intent prediction from conversation logs and metadata, drift detection by comparing developer intent with agent output, and ranking diff regions for review. Its reported evaluation and rollout results are the authors' claims; this screen did not reproduce them.
- [GitHub's review guidance](https://github.blog/ai-and-ml/generative-ai/agent-pull-requests-are-everywhere-heres-how-to-review-them/) recommends that authors check whether the pull request captured their intent and that reviewers inspect scope, plan, tests, and risky changes.

## Decision

Close generic intent-to-diff review as a product lead. The workflow is directly covered by a public open-source implementation and is also an active research/product direction. This is sufficient to reject a uniqueness claim for the broad idea; it does not establish that either implementation works well in practice, has adoption, or captures every workflow. Do not add another generic PR reviewer, intent document, or scope-drift detector here.

The session-export repository could still contribute a distinct capability if it demonstrates a concrete cross-agent or retrospective workflow these approaches cannot handle. No such residual is established by this screen. Parser coverage, privacy controls, or more adapters alone would not prove user value.

## What remains unknown

- Runtime quality and supported edge cases were not independently tested.
- No representative failure corpus, reviewer-time comparison, adoption evidence, or willingness-to-pay evidence was examined.
- No specific user workflow that remains unsolved by these products has been established.

Reopen only with a reproducible user-relevant case that current tools miss, a same-case baseline comparison, and evidence that the improvement changes a review decision or saves meaningful time. Keep real transcripts and repository data private; future public examples must remain synthetic.
