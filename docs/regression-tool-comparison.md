# Existing regression tools and the next product decision

Review date: October 25, 2026. This is a bounded comparison, not a survey of every repository.
Documentation claims and local execution observations are separated below.

## Existing capabilities

| Tool or project | Supported by its primary source | Implication |
|---|---|---|
| [Promptfoo conversation evaluation](https://www.promptfoo.dev/docs/configuration/chat/) | Full conversation prompts and evolving conversation variables | Conversation regression testing is already available. |
| [Promptfoo Python providers](https://www.promptfoo.dev/docs/providers/python/) | Custom synchronous and asynchronous generation functions | Another generic replay runner needs a concrete advantage. |
| [LongMemEval](https://github.com/xiaowu0162/LongMemEval) | 500 questions covering extraction, multi-session reasoning, updates, temporal reasoning, and abstention | Memory evaluation is an existing field. |
| [CompactionBench](https://www.microsoft.com/en-us/research/publication/benchmarking-long-horizon-agent-context-compaction-with-compactionbench/) | Persistent multi-turn coding sessions with executable task evaluation | Coding continuation after compaction is already studied. |
| [agent-replay](https://github.com/clay-good/agent-replay) | Local trace replay, forks, exports, and structural golden-run checks | Trace capture and regression gates alone are insufficient distinctions. |
| [FailMin 0.2.0](https://pypi.org/project/failmin/0.2.0/) | Dependency-aware reduction, replay callbacks, failure predicates, and reports | General failure minimization already has an implementation. |
| [Hugging Face Agent Traces](https://huggingface.co/docs/hub/agent-traces) | Native rendering of several coding-agent trace formats | A cross-agent trace viewer alone would also overlap. |
| [codex-recover](https://github.com/agustif/codex-recover) | Documents reconstruction of patch edits, exact file writes/reads, unresolved mutations, and verified recovery archives from Codex rollouts | Do not propose another general file-recovery engine as an exclusive capability. |

These sources do not establish that the projects lack other capabilities.
Their existence does not establish adoption, customer satisfaction, or willingness to pay for our proposed workflow.
The codex-recover row was reviewed on October 26 from its primary documentation; its runtime was not installed or executed here.

## Local FailMin execution

Downloaded the public `failmin==0.2.0` wheel and checked its SHA-256 against PyPI metadata.
Installed it without dependencies in an isolated temporary environment.
No package was added to this repository's dependencies or the user's global environment.

Wheel SHA-256:

```text
f0a351758935fc414ba529a89ca50281bc948ddfcf6f474c165546915e1222aa
```

The package's deterministic demo reduced 16 events to three.
The separate [selection probe](../examples/failmin_selection_probe.py) then supplied our actual handoff builder as the replay callback.
Its authored trace contains 20 query-related naming messages and one restriction without the literal query.
The failure predicate requires the restriction and a query-bearing message to remain present while the handoff omits the restriction.
This prevents reducing the exercise into a different empty-query case.

| Observation | Result |
|---|---:|
| Original messages | 21 |
| Reduced messages | 2 |
| Reducer replay calls | 6 |
| Failure reproduced through the actual builder | Yes |
| Query-bearing message retained | Yes |
| Single-message deletions that still reproduce this failure | 0 |

The remaining messages expose literal-query selection omitting a nearby restriction.
This is a deterministic selection failure, not a newly observed model mistake or proof of semantic causality.
Single-deletion checks establish event-level one-minimality, not a globally smallest or semantically equivalent trace.

The wheel's generic CLI replays recorded outputs; executable agent behavior requires a supplied replay callback.
Our probe uses that callback boundary instead of treating a stored wrong answer as a fresh failure.
The existing package supplies the reduction algorithm.

## Reproduce the optional probe

Use a separate temporary environment and install the pinned package there.
Run from this repository with that environment's Python:

```sh
python -m examples.failmin_selection_probe
```

The probe creates only synthetic temporary exports and launches no model or external service.
Downloading or installing the optional dependency is separate from running the probe.

## Decision

Do not build another general regression runner, compaction benchmark, viewer, or minimizer without a demonstrated gap.
The next candidate is reducing preparation work between local coding-agent archives and existing evaluation tools.
Before implementing an adapter, inspect their native importers and try equivalent existing formats on synthetic traces.
Measure missing roles, tool boundaries, source identity, and required manual transformations.
If existing importers preserve those fields with little preparation, reject that candidate too.
Any private archive investigation stays local and separate from public fixtures.

No distinctive capability or commercial demand has been established by this review.

## Acceptance coverage check, October 26

Existing tools already address the proposed acceptance-audit workflow.
[OpenSpec verify](https://github.com/Fission-AI/OpenSpec/blob/main/docs/commands.md#opsxverify) documents checking requirements, scenarios, code evidence, and uncovered tests.
Its verification workflow reports issues rather than blocking archive.
[BeforeDone](https://github.com/rrrrrredy/beforedone#choose-credible-checks) explicitly distinguishes fresh check receipts from coverage of every acceptance criterion.
It asks the agent to map observable criteria to credible checks and report missing coverage.
These are documentation observations; neither tool was installed or executed for this check.

A small synthetic Python task tests ordered output, duplicate preservation, and unchanged input.
The original two checks cover ordinary ordering and an empty input.
Three implementations are executed in memory, with no model, dependency installation, or real repository changes.

| Implementation | Original checks | Expanded ordinary checks | Criterion matrix |
| --- | --- | --- | --- |
| `return sorted(set(values))` | 2/2 | Duplicate preservation fails | Same failure |
| `values.sort(); return values` | 2/2 | Input preservation fails | Same failure |
| `return sorted(values)` | 2/2 | 3/3 | Same passes |

The matrix records the same behavioral checks; it adds no separate correctness oracle.
Successful narrow checks do not prove all required behavior, including after a fix.
Expanding ordinary tests catches both authored failures without a new gate.
This exercise does not measure agents rereading documents, discovering missing requirements, or designing tests.
It cannot establish reduced user effort, better review accuracy, or a distinct capability.

To reproduce the behavioral observations with Python:

```python
implementations = [
    'def order(values): return sorted(set(values))',
    'def order(values): values.sort(); return values',
    'def order(values): return sorted(values)',
]
for source in implementations:
    namespace = {}
    exec(source, namespace)
    order = namespace['order']
    original = [order(['b', 'a']) == ['a', 'b'], order([]) == []]
    values = ['b', 'a']
    before = list(values)
    order(values)
    expanded = [
        order(['b', 'a']) == ['a', 'b'],
        order(['b', 'a', 'a']) == ['a', 'a', 'b'],
        values == before,
    ]
    print(original, expanded)
```

Defer another general acceptance gate.
The open opportunity is reducing actual preparation or review work around an existing tool, which requires a complete-task comparison.

## Pinned recovery implementation check, October 26

Reviewed codex-recover revision `7fe5e66fe7d07f427adf83a08ad6508704a1337e`.
Its [specification](https://github.com/agustif/codex-recover/blob/7fe5e66fe7d07f427adf83a08ad6508704a1337e/SPEC.md#recovery-evidence-classes) separates exact content, partial observations, patches without a base, deletion, and unresolved mutation intent.
The [reconstruction source](https://github.com/agustif/codex-recover/blob/7fe5e66fe7d07f427adf83a08ad6508704a1337e/src/recover.ts) checks completion evidence, preserves missing-base patches, and records truncated reads separately.
These are source observations; the Bun CLI, complete engine, and output archive were not executed here.

The standalone [patch module](https://github.com/agustif/codex-recover/blob/7fe5e66fe7d07f427adf83a08ad6508704a1337e/src/patch.ts) has no runtime dependency imports.
It was executed unchanged under Node v22.23.2 with TypeScript stripping enabled.
SHA-256: `c5b5dd70e8e7397607aafe71e04078cd7d8607e556448fa18cd3dc6548c59c52`.

| Authored operation | Observed module behavior | Expected boundary |
| --- | --- | --- |
| Ordinary matching context | Success, correct replacement | Match |
| Missing old context | Explicit replay failure | Match |
| Function context selector with repeated body text | Success, changes the first function | Mismatch: selector names the second function |
| End-of-file selector with repeated text | Success, changes the first occurrence | Mismatch: selected occurrence is at the end |

For the two selector cases, the available patch editor applied the same edit to disposable synthetic files and produced the expected target.
No project files or archived commands were executed or restored.
The pinned parser treats named `@@` markers as hunk boundaries without retaining their selector text, and ignores `*** End of File`.
Its subsequent first-match search explains these two observed differences.

The function-selector fixture contains two functions that each return `1`; only the second should change:

```text
*** Update File: example.py
@@ def second():
-    return 1
+    return 2
```

The public probe checks the source hash before importing that module:

```sh
node --experimental-strip-types examples/recovery_patch_probe.mjs /path/to/pinned/src/patch.ts
```

Normal Python tests need no downloaded source; an optional Node test verifies that unpinned code is rejected before import.
The probe reports observed mismatches rather than certifying the recovery tool.
The source reconstruction path promotes a successful module replay to exact content, but that downstream outcome remains untested at runtime here.
These controls do not establish failures in other revisions, complete real incidents, or an advantage implemented by agent-sessions.

Defer recovery integration until complete reconstruction preserves the actual editor semantics and reports uncertainty across failed or unknown mutations.
Prefer correcting or reusing existing replay implementations over building another partial patch interpreter.

## Complete recovery and archive controls

The follow-up ran the unchanged pinned project's actual `recover` and `verify` commands on Linux.
An isolated Bun 1.3.3 baseline runtime was downloaded from its [official release](https://github.com/oven-sh/bun/releases/tag/bun-v1.3.3).
The archive digest matched release metadata: `281e6cbad969eb2f5ef5724c6cba01da40cd5fead6f8292c50ed60bd4dba78ae`.
Production dependencies were installed only in the temporary comparison checkout, with a frozen lockfile and install scripts disabled.
The lockfile stayed unchanged; all 33 upstream runtime tests passed.
No global runtime, user configuration, or live user project was changed.

The histories are authored synthetic records with reported tool completion statuses.
They are not real incidents or independent attestations of tool success.
Commands received explicit rollout paths and absolute synthetic patch targets, with isolated home, cache, and Codex-home directories.
Live-base recovery was disabled.
Every simulated project retained its sentinel and had no recovered file written into it.

| Synthetic history | Archive file status | Warnings | Unresolved events | ZIP verification | Known intended target |
| --- | --- | ---:| ---:| --- | --- |
| Add, then ordinary update | exact | 0 | 0 | Pass | Matches |
| Add, then function selector | exact | 0 | 0 | Pass | Wrong repeated occurrence |
| Add, then end-of-file selector | exact | 0 | 0 | Pass | Wrong repeated occurrence |
| Update without a known base | patch_only | 0 | 1 | Pass | Not established |
| Reported-success update with mismatching replay context | exact, older bytes | 1 | 0 | Pass | Not established |
| Add, then opaque in-place edit | exact, older bytes | 1 | 1 | Pass | Not established |
| Add, then failed patch | exact, older bytes | 0 | 1 | Pass | Not established |
| Add, then patch without completion | exact, older bytes | 0 | 1 | Pass | Not established |
| Same missing-completion case, filtered to target path | exact, older bytes | 0 | 0 | Pass | Not established |

Both selector mismatches therefore reach the actual recovered archive, rather than remaining isolated module observations.
The verifier correctly checks the archive's structure and stored hashes; it does not compare reconstruction with the intended editor result.
A valid archive hash is not proof that replay preserved editor semantics.

Older exact snapshots can remain useful, but they must not be interpreted as proven latest file state.
In the filtered missing-completion case, the generic unresolved patch event is excluded while the older exact file remains.
The source's [path-filter function](https://github.com/agustif/codex-recover/blob/7fe5e66fe7d07f427adf83a08ad6508704a1337e/src/recover.ts) retains evidence by selected path; the unresolved event uses a generic patch path.
This is a scoped uncertainty-loss observation for the pinned revision, not a failure claim about every recovery tool.

The public reproducer verifies the source bundle before invoking the supplied runtime:

```sh
python3 -m examples.recovery_archive_probe \
  --source /path/to/pinned/codex-recover --bun /path/to/bun-1.3.3
```

It requires already-installed production dependencies and performs no download or installation.
Bundle SHA-256 is computed over sorted relative paths plus bytes for `package.json`, `bun.lock`, and `src/*.ts`, separated by NUL bytes:
`1e0c12264f46109855d63fd8ca22a1ee0709f02e59bd56317af9f63263dac329`.
Normal tests use no recovery dependency or downloaded history; a guard test rejects incomplete source before executing a runtime.

Do not integrate this pinned engine as a latest-state recovery authority.
Correct replay semantics and preserved uncertainty across filters need verification first.
Agent-sessions has no implemented recovery advantage from these results; another parser, gate, or misleading exactness label would not establish one.

## Installed editor reference comparison

The follow-up compares actual archive contents with an existing installed `apply_patch` helper, observed alongside Codex CLI 0.164.0.
Its executable fingerprint is `b93f6811d3f653f0fb83be4050d857fb9abbb111dfa2ce160563327daff7f306`.
This pins the local observation; it does not establish a stable public helper interface or universal patch compatibility.
The [official CLI reference](https://learn.chatgpt.com/docs/cli/reference) describes `codex apply` as applying a cloud-chat diff; that command was not used.
No agent, model, cloud task, credentials, or private history was involved.

The helper receives only the probe's authored patch strings, in a separate disposable directory for each case.
Known starting bytes are supplied directly from the synthetic fixture.
The recovered archive's bytes are compared with the helper's actual output file, rather than only comparing return codes or manifest hashes.

| Fixture | Helper exit | Expected editor result | Archive equals helper output |
| --- | ---:| --- | --- |
| Ordinary context | 0 | Correct replacement | Yes |
| Function selector | 0 | Correct second function | No |
| End-of-file selector | 0 | Correct final occurrence | No |
| Missing base | 1 | Refusal; no file created | No successful latest-state comparison |
| Mismatching context | 1 | Refusal; starting bytes preserved | No successful latest-state comparison |

Failed, missing-completion, and opaque-mutation histories are not submitted for reference replay.
Their exclusion follows the authored fixture classification; this is not a general mutation classifier.
Both the helper fingerprint and invocation name are checked before execution.
The invocation alias is preserved because resolving it to the underlying executable can select a different command mode.

To include this optional comparison, supply the pinned helper:

```sh
python3 -m examples.recovery_archive_probe \
  --source /path/to/pinned/codex-recover --bun /path/to/bun-1.3.3 \
  --editor /path/to/apply_patch
```

The guard rejects a different editor binary instead of assuming equivalent behavior.
No historical command is replayed and no live project receives recovered files.
The reference implementation handles the observed selector cases without a new patch-matching engine.
This weakens the case for building another interpreter here; it does not establish a complete recovery product or an exclusive advantage for agent-sessions.

## Scoped uncertainty prototype

A minimal local modification retains generic unresolved patch/shell events when filtering to a selected file.
Known uncertainty tied to a different file still stays outside the selected scope.
The prototype does not change recovered file content, fix selector replay, or certify latest state.

Three added synthetic runtime tests cover missing patch completion, a failed shell command, and known unrelated-file uncertainty.
Two fail on the original code; the unrelated-file control passes.
All 36 runtime tests pass after the modification, including the original 33.
The actual CLI comparison uses the same missing-completion rollout and target path:

| Observation | Original filtered archive | Prototype filtered archive |
| --- | --- | --- |
| Stored file class | exact, historical bytes | exact, same historical bytes |
| Stored content SHA-256 | `01d09d19c2139a46aebfb577780d123d7396e97201bc7ead210a2ebff8239dee` | Same |
| Unresolved events retained | 0 | 1 |
| ZIP integrity verification | Pass | Pass |
| Latest state established | No | No |

A separate controlled operation writes `new` to one temporary synthetic file, then exits 7.
Its observed failure is recorded in an authored rollout after an older `old` snapshot.
The original filtered archive retains the older bytes without the generic unresolved event.
The prototype retains those same older bytes with the unresolved event visible.
Neither reconstructs the newer bytes; the experiment shows why failed commands cannot simply be assumed to leave files unchanged.
The operation was newly authored and executed for this control, not replayed from user history.

The [reviewable patch and tests](../examples/patches/README.md) apply to a separate copy of the pinned upstream source.
Its runtime source fingerprint is `e6118994a815605908418b70893147b7ec2c5122bed03d901c8ba5ec698474a5`.
The archive probe accepts this exact variant, labels it `uncertainty-filter-prototype`, and reports the upstream parent revision separately.
It does not label modified code as an upstream release.

All nine archive controls run on the prototype as well; both selector mismatches remain.
Generic unresolved events are retained conservatively because they cannot be proven unrelated from their generic path alone.
This can retain irrelevant uncertainty; it is not semantic attribution or reduced review-effort evidence.
Keep historical snapshots, replay refusals, warnings, and unresolved events distinct before any latest-state claim.
This prototype is not a production recovery integration or a distinct commercial capability.
Cross-file effects such as copy/move operations require separate checks; a different recorded path does not alone establish that an operation is unrelated.


## Cross-file scope checks (October 27)

The archive probe now includes three authored, successful shell-operation histories.
Both files first have known synthetic snapshots; recovery is filtered to the selected file.
These are parsed command records, not executed shell commands or real incidents.
The original pinned source and the unchanged uncertainty-filter prototype produce the same results:

| Selected file | Recorded operation | Warnings | Unresolved events | Stored bytes | ZIP verification |
| --- | --- | --- | --- | --- | --- |
| Copy destination | `cp other.py example.py` | 1 | 1 | Older snapshot | Pass |
| Move destination | `mv other.py example.py` | 1 | 1 | Older snapshot | Pass |
| Move source | `mv example.py other.py` | 0 | 0 | Older snapshot | Pass |

The parser records the destination as the primary path for both copy and move.
The source is a related path in the intent, then free text in the recovery message.
Filtering to the moved source excludes the destination record and loses that uncertainty.
Thus the earlier hypothesis about missing destination uncertainty was incorrect for these controls.
The source-side omission is reproduced through actual recovery and archive verification.
A passing ZIP check still does not establish that the stored historical file exists in latest state.

All three archives retain the `old\n` snapshot with SHA-256
`01d09d19c2139a46aebfb577780d123d7396e97201bc7ead210a2ebff8239dee`.
All twelve archive controls ran on both source variants with Bun 1.3.3.
No simulated live project was modified.
Run the existing archive-probe command to reproduce the expanded controls.

**Decision:** defer recovery integration. The generic-event patch is insufficient for cross-file effects.
Do not extend it into another recovery engine without a demonstrated complete-task advantage.
The next product evaluation must measure a useful investigation outcome against ordinary source inspection;
more isolated recovery fixes cannot establish distinct capability or willingness to pay.

## Upstream revision refresh (October 27)

A read-only `git ls-remote https://github.com/agustif/codex-recover.git HEAD`
returned the same `7fe5e66fe7d07f427adf83a08ad6508704a1337e` revision used above.
The local source still passes the pinned-source fingerprint validator.
No new runtime result is claimed by this revision check.
See [the fresh recovery-demand review](product-direction.md#fresh-recovery-demand-check-october-27)
for the distinction between hidden chat history and lost workspace state.
A complete recovery task needs surviving exact evidence and a behavioral oracle;
a history report or passing archive integrity check supplies neither alone.

## Restored project behavior (October 27)

The two-module authored project uses a pricing module and a checkout entry point.
Successful patch records first create both files, then change only the express fee.
An independent expected output is held outside the recovery archive.
The probe restores the archive into a separate directory and executes the checkout.
A baseline replays the same authored patches with the pinned existing editor.
Neither arm writes the simulated original project.

| Observation | Existing editor replay | Pinned recovery archive |
|---|---|---|
| Standard fee | 5 | 12 |
| Express fee | 12 | 5 |
| Matches the authored behavior | Yes | No |
| Archive integrity | Not applicable | Pass |
| Recovery file labels | Not applicable | Both `exact`, no warnings |

The recovered checkout runs, but the repeated-function selector changed the wrong fee.
This carries the earlier byte mismatch into a behavioral failure across two modules.
The checks are independent of archive self-consistency; successful Python execution alone would also miss it.
The ordinary existing editor baseline restores the intended behavior without a new interpreter.
No new production recovery feature or agent-sessions advantage is established.

Reproduce with the source and runtime pins already documented above:

```sh
python3 -m examples.recovery_project_probe --source /path/to/pinned-codex-recover --bun /path/to/bun-1.3.3 --editor /path/to/pinned/apply_patch
```

The source and editor fingerprint guards run before supplied programs execute.
This probe accepts only the original upstream source fingerprint.
Exit zero means the comparison controls ran, not that both restorations are correct.
All Python code and patch inputs are authored fixtures; arbitrary historical commands are never executed.

This is a small behavioral control, not a recovered customer project.
It assumes complete text bases and successful patch outcomes.
Unknown mutations, missing content, cloud transcript acquisition, binary assets, and latest-state recovery remain outside the exercised task.
A passing fixture cannot establish an exclusive capability, reduced recovery effort, or willingness to pay.
The concrete result supports keeping the current recovery engine unintegrated.

## Existing editor bridge prototype (October 27)

A separate local copy of the pinned recovery tool now delegates update application to the existing editor.
The recovery parser, archive format, and uncertainty tracking remain in the existing tool.
The adapter checks the helper hash and invocation name, binds a single update to a scratch file,
and returns the helper's resulting bytes or a refusal.
It does not implement selector matching or run historical shell commands.
Move destinations remain the recovery tool's responsibility.
The adapter rejects unexpected extra operation directives and preserves payload trailing spaces.

The [reviewable compatibility patch](../examples/patches/codex-recover-existing-editor.patch)
applies cleanly to a fresh original copy.
Its runtime source fingerprint is `f5b36e0475b5bc7c286b66315d9733d242287f9030576fb2e3d5af14e5cab21b`.
It requires the same explicitly supplied editor binary as the earlier reference comparison.
It is an alternative to the uncertainty-filter prototype, not a combined patch or upstream release.

The public project probe restores the expected standard fee of 5 and express fee of 12 in both arms.
Archive verification passes and the simulated original project stays untouched.
The broader archive controls also restore the intended ordinary, function-selector, and end-of-file results.
A context mismatch refuses replay and retains the older snapshot with a warning.
Missing bases remain patch-only evidence.

The adapter does not repair the missing-completion path filter or move-source uncertainty gap.
Older snapshots can still have an `exact` label without proving latest state.
Do not treat this adapter as a reliable complete-project recovery authority.
It demonstrates compatible reuse of the actual editor for the observed replay problem.

All 38 upstream runtime tests pass on the prototype, including five added regressions.
Four added regressions fail on the original source; the payload-whitespace control already passes there.
The repository's 380 Python tests also pass after the probe updates.
A static TypeScript check could not run because the temporary installation lacks its compiler dependency.

Reproduce either public probe using the patched source, Bun 1.3.3, and the pinned `--editor` helper.
Both probes label the prototype explicitly and refuse unknown source fingerprints.
The archive probe requires the editor for this variant before executing the supplied runtime.
The project probe accepts only upstream or this exact bridge, retaining the original revision as parent metadata.

This is a local compatibility result on synthetic projects and histories.
No real lost project, cloud input, user-effort improvement, or commercial demand was measured.
It supplies no independent reason to add a second recovery engine to agent-sessions.

## Scoped editor bridge prototype (October 27)

A separate combined prototype keeps the existing-editor replay adapter and addresses
the two demonstrated uncertainty-filter failures.
Its [reviewable patch](../examples/patches/codex-recover-scoped-editor.patch)
targets the original upstream revision directly; do not layer it on another prototype.

Shell-move evidence now carries structured `affectedPaths` for its destination and source.
Both paths receive warnings when present as historical snapshots.
A copy records its destination as affected; its unchanged source does not acquire a mutation warning.
Filtering retains records affecting a selected path and generic unresolved patch/shell evidence.
Multiple-source copy/move commands also retain an explicit unknown-scope record because
that parser does not establish every affected path.
These changes preserve existing parser information rather than interpreting shell commands anew.

All twelve archive controls run through the public CLI probe with this exact variant:

| Control | Previous editor bridge | Scoped editor bridge |
|---|---|---|
| Ordinary, function-selector, EOF bytes | Intended bytes | Intended bytes |
| Filtered missing completion | No unresolved event | One unresolved event |
| Filtered move source | No warning or unresolved event | Warning and one unresolved event |
| Missing base | Patch-only | Patch-only |
| Context mismatch | Older snapshot with warning | Older snapshot with warning |

The two-module restored checkout still produces the expected prices in both arms.
The simulated original project remains untouched.
All archive integrity checks pass; this still establishes stored-byte consistency alone.
No unknown mutation's final bytes are reconstructed by these controls.

The runtime source fingerprint is `e87987f95a6e6fd63441125166b9b9eb8931db6c14eaa836d87878b59f926bef`.
A clean application of the public patch reproduces that fingerprint and both regression-test files.
All 43 upstream runtime tests pass.
Of five new scope tests, three fail and two pass on the earlier editor bridge.
They cover move sources, copy-source exclusion, missing completions, unrelated destinations,
and incomplete multiple-source move scope.
The three repository probe-guard tests also pass after adding this variant.
The earlier full repository run passed 380 tests; no new full run is claimed for this doc update.
Static TypeScript checking remains unavailable in the temporary dependency installation.

Both public probes accept this exact fingerprint and require the same explicit pinned editor.
They label the variant `scoped-existing-editor-bridge` and do not run arbitrary archived shell commands.
No original source code or customer transcript enters public fixtures.

This repairs the demonstrated controls, not arbitrary shell analysis or latest-workspace recovery.
Snapshots can retain an `exact` content label alongside unresolved later effects.
Unknown commands, incomplete records, omitted bytes, and unavailable cloud or binary data remain limits.
Real-project restoration correctness, user effort, distinct value, and demand remain unestablished.
