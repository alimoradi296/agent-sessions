# Captured file restoration

Codex sessions can contain complete `Add File` bodies inside a direct patch call.
Some clients also wrap those calls as literal strings inside an orchestration `exec` record.
The ordinary session parser retains the wrapper text, but a recovery tool that recognizes only direct
`apply_patch` calls can miss the complete file bytes.

`agent-sessions restore` statically extracts both shapes.
It does not execute the wrapper, the patch, or any historical command.
It accepts only a complete JSON string literal passed directly to `tools.apply_patch(...)` in a wrapper.
Variables, template strings, expressions, and incomplete patches are ignored.
The command restores complete `Add File` bodies. It can also apply a captured `Update File` only when an earlier
captured addition supplies the complete base and every old hunk has one exact match. Missing or ambiguous bases
are counted and skipped; the command never reads a current checkout as an inferred historical base.
If a later update cannot be applied, the manifest labels the retained earlier bytes `captured_prefix` and the
update status `blocked`. A later complete addition can establish a new base.
Captured `Delete File` operations remove an earlier reconstructed file and create an explicit
`captured_deletion` tombstone with unknown execution. A later complete addition can re-establish the path.
Moves, shell writes, and binary data remain outside this command.

The output must be a new private directory outside every Git checkout:

```sh
agent-sessions restore /private/first.jsonl /private/resumed.jsonl \
  --source-root /historical/project/root \
  -o /private/recovered-copy \
  --json
```

To avoid locating segments manually, pass one directory instead. The command recursively inspects regular
`.jsonl` files, keeps only sources with captured patch targets under `--source-root`, and orders those sources by
captured timestamps. It reports the number scanned and selected. Unrelated sources, symlinks, missing timestamps,
and overlapping histories are not silently included.

One or more source files are accepted in the supplied chronological order. This allows an addition captured in
one session segment to provide the exact base for an update in a resumed segment. Duplicate sources are refused.
For multiple sources, every file must contain captured timestamps and their ranges must be ordered without overlap;
timestamp ties are refused because they do not establish order. ISO timestamps, numeric timestamps, and captured
payload timestamp fields are recognized. The command never trusts filenames, mtimes, or an unverified caller order.
The manifest records chronology verification, every source hash, and the source number for each recovered file state.

`--source-root` is an explicit logical path filter. It may name an existing directory or an absent historical
project root, so a deleted project can still be reconstructed. An existing file or symlink is refused.
Absolute captured paths outside it are counted and skipped.
A relative path that escapes the root is rejected.
Relative patch paths are resolved from the source's captured working directory, including subdirectory sessions.
Conflicting captured bodies for one relative path are rejected before output is created.
An existing output directory is never overwritten.
Output directories use owner-only permissions, and files use owner read/write permissions.

Every complete sequence has `status: captured_bytes`; blocked sequences use `captured_prefix`.
Each operation is correlated with a captured result by call ID. Explicit success can produce
`execution_status: confirmed_success`; explicit failure is counted and skipped; absent, conflicting, or
unrecognized results remain `unknown`. Recovered files include `result_evidence` (`linked`, `missing`, `ambiguous`,
or `nested_call`), the result status, and its line when a trusted direct link exists. `skipped_operations` records
failed operation lines and their failure result lines. Duplicate or conflicting results are ambiguous and do not
receive a trusted line reference. A requested patch alone never proves execution.
For a patch nested inside an orchestration `exec`, the outer executor result cannot certify the inner patch;
its execution therefore remains unknown until native nested-call evidence exists.
It also has a `current_status` of `missing`, `matching`, `different`, or `non_regular`, plus aggregate counts.
This comparison prioritizes recovery work; it does not change the captured bytes or claim which version is correct.
The top-level `execution_verified` is true only when every retained operation is confirmed successful.
`latest_state_verified` remains false.
It records whether the selected source root currently exists.
The source file hash, source line, outer call ID, and extraction shape make the result inspectable.
These fields can contain private paths and identifiers, so the manifest stays with the private recovery output.

Without `--json`, the command prints counts for current missing, changed, matching, and non-regular files, then
lists each recovered path with its current state, incomplete-prefix warning, and execution state. Captured
deletions appear as tombstones in that list. This gives the operator a review order without opening the manifest.

## Public controls

Synthetic regressions cover direct calls, nested literals, linked success/failure results, multiple files,
exact-base updates, deletion tombstones,
missing and ambiguous update bases, variables, conflicting bodies, absolute root filtering, relative traversal,
existing-output refusal, labels, permissions, and the CLI JSON path.
Public fixtures contain no developer archive data.
