# Third-party compatibility prototypes

## Recovery filter

This experimental patch modifies codex-recover revision `7fe5e66fe7d07f427adf83a08ad6508704a1337e`.
It retains unresolved events with generic patch/shell paths when a recovery result is filtered to particular files.
It does not fix replay selectors, reconstruct unknown mutations, or establish the latest file state.
It is not an upstream release or a production agent-sessions integration.

Apply it only to a separate temporary copy of that pinned source:

```sh
git apply --check /path/to/codex-recover-unscoped-uncertainty.patch
git apply /path/to/codex-recover-unscoped-uncertainty.patch
bun test
```

The patch adds three synthetic tests. Two expose missing uncertainty on the original code; the third checks that known unrelated-file uncertainty stays excluded.
All 36 runtime tests pass after applying it in the measured environment.
The [archive probe](../recovery_archive_probe.py) accepts the pinned original and this exact prototype as separately labeled source variants.
Neither variant runs historical shell commands or restores files into live projects.

The modified source fingerprint is `e6118994a815605908418b70893147b7ec2c5122bed03d901c8ba5ec698474a5`.
See [the comparison report](../../docs/regression-tool-comparison.md) for limits and archive observations.

The patch contains context from [agustif/codex-recover](https://github.com/agustif/codex-recover), Copyright (c) 2026 agustif, licensed under the [MIT license](https://github.com/agustif/codex-recover/blob/7fe5e66fe7d07f427adf83a08ad6508704a1337e/LICENSE).
The same MIT permission and warranty terms are included in this distribution's [LICENSE](../../LICENSE).


## Local capture persistence

`otel-local-file-persistence.patch` targets OpenTelemetry Hooks revision `2b922aeddab9e83bea5e932e3d2558f0bd397e3b`.
It records local exporter outcomes and keeps file-only trace delivery failures visible to the existing batch-flush check.
Doctor reports a recent local-only failure as degraded.
A configured remote trace exporter retains authority when the local file is an optional mirror.
No collector or correlation engine is added.

Apply only to a separate temporary copy of that pinned public source:

```sh
git apply --check /path/to/otel-local-file-persistence.patch
git apply /path/to/otel-local-file-persistence.patch
python -m pytest -q tests/test_file_persistence.py
```

Three added tests fail on the original runtime and pass with this patch.
The combined selected run passes 26 tests, with 75 deselected; it is not the full upstream suite.
The [delivery probe](../otel_capture_delivery_probe.py) compares the original and exact patched runtime.
The patched source fingerprint is `9423b43b649ff59e08fe7d2e2887351b0720d04c097f1165ad550ee9e40e7640`.
The published patch applies cleanly and produces that fingerprint.

See [the failure and recovery controls](../../docs/capture-delivery-controls.md) for observations and limits.
This is a local experimental patch, not an upstream release or enabled agent-sessions capture integration.
The source package declares MIT licensing in its [package metadata](https://github.com/o11y-dev/opentelemetry-hooks/blob/2b922aeddab9e83bea5e932e3d2558f0bd397e3b/pyproject.toml).

## Existing editor recovery bridge

`codex-recover-existing-editor.patch` is a separate alternative prototype for
codex-recover revision `7fe5e66fe7d07f427adf83a08ad6508704a1337e`.
It delegates update replay to the existing pinned `apply_patch` helper instead of adding another patch interpreter.
It is not combined with the recovery-filter prototype above.

Apply it to a separate temporary copy of the original pinned source:

```sh
git apply --check /path/to/codex-recover-existing-editor.patch
git apply /path/to/codex-recover-existing-editor.patch
AGENT_SESSIONS_PATCH_EDITOR=/path/to/pinned/apply_patch bun test
```

The helper must have the tested executable hash and the `apply_patch` invocation name.
The prototype does not install or download it.
It rebinds each update to one regular scratch file and removes that scratch directory afterward.
A missing helper, failed replay, or unexpected extra operation refuses the update.
It does not execute historical shell commands.

The modified runtime source fingerprint is `f5b36e0475b5bc7c286b66315d9733d242287f9030576fb2e3d5af14e5cab21b`.
The public patch applies cleanly and reproduces that fingerprint and the regression test bytes.
All 38 runtime tests pass, including five added tests; four added tests fail on original code.
A TypeScript check was attempted but could not run because the temporary dependency installation lacks TypeScript.
No passing static check is claimed.

Both public [archive](../recovery_archive_probe.py) and [project](../recovery_project_probe.py)
probes accept this exact source variant with `--editor` and label it separately from upstream.
The restored checkout now has the intended prices, and both selector controls match the editor.
Path-filtered missing-completion and move-source uncertainty gaps remain.
This is neither latest-state certification nor a production agent-sessions recovery feature.
See [the detailed results](../../docs/regression-tool-comparison.md#existing-editor-bridge-prototype-october-27).

The patch includes context from the same MIT-licensed codex-recover source attributed above.

## Scoped existing-editor bridge

`codex-recover-scoped-editor.patch` is the latest combined experimental variant.
Apply it directly to original revision `7fe5e66fe7d07f427adf83a08ad6508704a1337e`,
not on top of another patch in this directory.
It combines existing-editor replay with retained generic uncertainty and structured move-source effects.
Copy sources remain outside destination-only mutation warnings.
Multiple-source copy/move commands retain an explicit unknown-scope warning.

Use the same explicit pinned editor and Bun 1.3.3 as the editor bridge above.
All 43 runtime tests pass; three of the five added scope controls fail on the earlier editor bridge.
The source fingerprint is `e87987f95a6e6fd63441125166b9b9eb8931db6c14eaa836d87878b59f926bef`.
The public patch applies cleanly and reproduces the tested source and test files.
Both public probes recognize and separately label this exact variant.
Static TypeScript checking remains unavailable.

See [the scoped results](../../docs/regression-tool-comparison.md#scoped-editor-bridge-prototype-october-27).
This is not a production recovery feature, a latest-state certificate, or an upstream release.
The patch includes context from the same MIT-licensed source attributed above.
