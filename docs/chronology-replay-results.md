# Correction ordering and replay

Run date: October 25, 2026. Every record and rule in this experiment is authored synthetic data.
The target is a deterministic operation check, not a model or production tool.

## Paired histories

Each format has two histories with the same messages, tool calls, and results.
Only the correction's position and timestamp differ.
In one history, the correction precedes a captured operation applying a 60-second TTL.
In the other, it follows that operation.
The authored rule changes the expected TTL from 60 to 30 when the user correction arrives.
It checks the expected value at each operation, without retroactively judging earlier operations.

[The native importer probe](../examples/compare_native_importers.mjs) uses pinned agent-replay revision `ccda6229a9451692fb6f1d6d323dd825c2be9dbb`.
Its two captured import payloads were exactly equal within each format.
No fields were removed to obtain this equality.
Only the storage function was replaced, as in [the earlier comparison](native-importer-comparison.md).
The later user correction appears as text without its position relative to tool steps.

| Source representation | Correction before operation | Correction after operation |
|---|---|---|
| Raw Codex records | Rule failure | Pass |
| Canonical Codex messages | Rule failure | Pass |
| Raw Claude records | Rule failure | Pass |
| Canonical Claude messages | Rule failure | Pass |
| Native captured payload alone | Order unknown | Order unknown |

Unknown is the appropriate result when the payload cannot establish order.
The comparison does not treat missing evidence as a false claim of success.
Original raw files preserve the distinction, so this does not establish a limitation in every workflow of the competing project.

## Existing replay API baseline

[The replay probe](../examples/chronology_replay_probe.py) passes original raw JSON records into FailMin 0.2.0's callback API.
A small fixture-specific function reads user text and captured tool arguments from those records.
No production adapter or new replay engine was needed.

| Format | Original records | Reduced records | Same rule failure reproduced |
|---|---:|---:|---|
| Codex | 8 | 2 | Yes |
| Claude | 7 | 2 | Yes |

The retained records are the correction and the later operation using the old value.
The replay runs an authored invariant over captured operations; it does not rerun an agent or infer an actual causal explanation.
The fixture-specific raw reader is not a complete vendor-format importer.
No setup time, real bug diagnosis, model cost, or willingness to pay was measured.

## Reproduce

Generate the synthetic histories with `examples/compare_native_importers.mjs` as described in the earlier comparison.
Use a separate environment with the pinned optional FailMin package:

```sh
python -m examples.chronology_replay_probe /path/to/generated-private-output
```

The probe reads only the generated fixture directory and launches no model or service.

## Product decision

Ordering can matter, and the canonical model now preserves the tested evidence.
However, the existing raw callback provides an equivalent result for this exercise with little code.
This result therefore does not justify the proposed chronology adapter as a distinct product.
Return to observed private archive problems before adding another feature or benchmark.
Require one grounded failure and a strong existing baseline before choosing the next implementation slice.
