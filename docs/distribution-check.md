# Distribution check

The unreleased 0.2.0 worktree was built and installed locally on Python 3.13.
This does not establish a published release, other-platform support, or commercial value.

## Source archive correction

The first source archive included tests but omitted their JSON fixtures and imported example modules.
`MANIFEST.in` now includes documentation, examples, tests, JSON fixtures, and the generic continuation skill.
It names `examples/sample-session.jsonl` explicitly rather than including arbitrary transcript files.
Compiled bytecode and cache directories are excluded.

The rebuilt source archive contains the inputs required to run the documented synthetic demo and test suite.
All 348 tests passed from an extracted archive outside the checkout.
The synthetic demo and its exported-conversation search also passed there.

## Installed wheel observations

The check used a disposable source snapshot and temporary virtual environment.
Installation used a local wheel with `--no-index --no-deps`; no package was uploaded.
Commands ran outside the checkout with a temporary home and no `PYTHONPATH` override.

Verified behavior:

- The loaded module came from the virtual environment's `site-packages`.
- The installed CLI exposed compact review and complete-input budget options.
- Compact preparation retained source-bound evidence, and import selected a late repeated occurrence by its original coordinates.
- Over-budget preparation exited 1 without creating a packet or changing the earlier packet.
- The installed `skill` command emitted exactly the packaged generic skill.

A second wheel built from the source archive had the same runtime payload as the wheel built directly from the source snapshot.
The wheel contained the review codec and skill resource, with no example exports or compiled bytecode.
Both archives passed a bounded scan for known private markers.
That scan is not a general redaction guarantee.

## Repeat the checks

Use a disposable copy of the intended source files outside the working checkout.
With the declared setuptools build dependency installed, the backend can build both formats:

```sh
python -c 'from setuptools.build_meta import build_sdist, build_wheel; build_sdist("dist"); build_wheel("dist")'
```

Install the wheel into a fresh temporary virtual environment with `pip install --no-index --no-deps`.
Run the installed CLI from outside the source directory and compare its `skill` output with the packaged file.
Extract the source archive separately, then run:

```sh
python -m unittest discover -s tests -q
python examples/demo.py
agent-sessions search retry -d demo-output --json
```

Use synthetic data for fit, over-budget, and answer-import checks.
Keep real exports and review captures outside the source tree.
Package checks verify distribution behavior; scripted imports do not measure receiving-agent understanding.

## Captured-file command check (October 27)

A wheel built from the current checkout was installed into a new temporary virtual environment with
`pip install --no-index --no-deps`.
From outside the checkout, its `agent-sessions restore` command read the public synthetic wrapper fixture,
recovered `pkg/example.py`, and produced the expected bytes and conservative manifest labels.
The installed `agent_sessions.analysis.captured_files` module imported from the virtual environment.
No package was uploaded and no private transcript entered the wheel or fixture.

This checks wheel inclusion and one installed CLI path.
It does not repeat the earlier source-archive parity check, supported-Python matrix, or full extracted-package suite.
