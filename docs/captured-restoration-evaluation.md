# Captured restoration comparison

This public synthetic comparison measures one narrow recovery difference.
It contains one direct patch addition, two additions hidden as literal strings inside orchestration calls,
and one wrapped update with a complete captured base.

Run it from the repository root:

```sh
python examples/evaluate_captured_restoration.py
```

The transparent baseline reads only direct `apply_patch` calls. It recovers one file.
The wrapper-aware command recovers three files, including two the baseline cannot see, and applies the one
exact-base update. All expected bytes must match. No archived command is executed.

The comparison is deterministic and enforced by the test suite. It proves a source-shape mechanism and two
additional recovered files in this fixture. It does not prove that other tools lack equivalent behavior,
that historical patches executed, that the output is latest, or that users will pay for it.
