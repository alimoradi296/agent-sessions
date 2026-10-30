# Session family digest

Build a cited lineage overview from an existing export archive.
The command walks `parent_id` links already recorded in `sessions.json`.
It quotes the first cleaned user turn and the last cleaned assistant turn from each related Markdown export.
It also extracts continuation-signal candidates (scope boundaries, blockers, open questions, next actions) from cleaned dialogue.

This is local infrastructure for fork and spawn families.
It does not prove that a statement remains in force, that a child is live, or that users will pay for the feature.

## Prerequisites

- Python 3.10 or later
- An editable install of this package: `python -m pip install -e .`
- An export archive that already contains `sessions.json` and `{session_id}.md` files

## Synthetic end-to-end example

The demo uses invented Claude and Codex sessions only.
It does not read `~/.claude`, `~/.codex`, or `~/.cursor`.

```bash
python examples/family_digest_demo.py
```

Expected JSON fields include `synthetic_only: true`, the Claude family member IDs, a Codex `spawned_from` edge, `handoff_ready: true`, and `audit_exit_code: 0`.
Verification stays `not_checked`.

To keep files for CLI follow-up:

```bash
python examples/family_digest_demo.py --output-dir /tmp/agent-sessions-family-mvp
agent-sessions family synthetic-family-child -d /tmp/agent-sessions-family-mvp/exports
agent-sessions family synthetic-family-child -d /tmp/agent-sessions-family-mvp/exports --json
agent-sessions family synthetic-family-child -d /tmp/agent-sessions-family-mvp/exports --max-signals 5
agent-sessions family synthetic-family-child -d /tmp/agent-sessions-family-mvp/exports --max-pin-suggestions 6
agent-sessions family synthetic-family-child -d /tmp/agent-sessions-family-mvp/exports \
  --signal-kind scope_boundary --signal-kind open_question \
  --pin-signal-kind open_question --focus-priority-bonus 20
agent-sessions family synthetic-family-child -d /tmp/agent-sessions-family-mvp/exports \
  --profile questions
agent-sessions family synthetic-family-child -d /tmp/agent-sessions-family-mvp/exports \
  --min-signal-priority 90
agent-sessions family synthetic-family-child -d /tmp/agent-sessions-family-mvp/exports \
  --requirements-out /tmp/agent-sessions-family-mvp/private/requirements.auto.json
agent-sessions family synthetic-family-child -d /tmp/agent-sessions-family-mvp/exports \
  --bundle-out /tmp/agent-sessions-family-mvp/private/bundle.auto --audit-family-bundle
agent-sessions family synthetic-family-child -d /tmp/agent-sessions-family-mvp/exports \
  --profile strict --require-signal-kind scope_boundary \
  --bundle-out /tmp/agent-sessions-family-mvp/private/bundle.gated --audit-family-bundle
```

The Markdown digest lists ancestors, the focus session, and descendants with quoted turns.
The JSON form is the same structure for tooling.

## Pin a retained constraint from the family

After the synthetic archive exists, search and pin as usual:

```bash
agent-sessions search "Discovery only" -d /tmp/agent-sessions-family-mvp/exports --json
agent-sessions handoff pin --id discovery-only \
  --session synthetic-family-parent --section 2 --unit paragraph \
  --quote "Discovery only. Do not implement or publish." \
  -d /tmp/agent-sessions-family-mvp/exports \
  -o /tmp/agent-sessions-family-mvp/private/requirements.json
agent-sessions handoff build "family cache" \
  --requirements /tmp/agent-sessions-family-mvp/private/requirements.json \
  -d /tmp/agent-sessions-family-mvp/exports \
  -o /tmp/agent-sessions-family-mvp/private/bundle --json
agent-sessions handoff audit /tmp/agent-sessions-family-mvp/private/bundle \
  -d /tmp/agent-sessions-family-mvp/exports --json
```

The demo script already runs this path in a temporary directory and asserts readiness plus a passing audit.

## What the digest includes

| Field | Meaning |
|---|---|
| `relation` | `ancestor`, `focus`, or `descendant` relative to the requested session |
| `edge` | `forked_from` for Claude/Cursor children; `spawned_from` for Codex children |
| `depth` | Negative for ancestors, `0` for focus, positive for descendants |
| `quotes` | First user and last assistant cleaned sections, optionally truncated |
| `signals` | Per-member continuation-signal candidates from cleaned dialogue |
| `family_summary` | Aggregated signal counts, carry-over constraints, blockers, open questions, next actions |
| `pin_suggestions` | Prioritized candidate anchors that can be converted to `handoff pin` commands |
| `generated_requirements` | Optional write receipt when `--requirements-out` is used |
| `family_bundle` | Optional one-command handoff bundle receipt when `--bundle-out` is used |
| `required_signals` | Optional required-signal gate result when `--require-signal-kind` is used |
| `transcript` | `available`, `missing`, `unreadable`, or `missing_index` |
| `missing_parents` | Parent IDs referenced by the index but absent from it |
| `verification` | Always `not_checked` |

## Limits

- Only exported `parent_id` values participate. Native Pi trees, deleted parents, and unreexported sessions are out of scope.
- Cycles stop the ancestor walk without repair.
- Quotes come from cleaned dialogue, not tool-result evidence.
- Signals are heuristic labels and candidate cues. They do not prove correctness, acceptance, or completion.
- Truncation uses `--max-quote-chars` (minimum 40; default 400).
- `--max-signals` controls per-member signal volume (default 8; `0` disables signal extraction).
- `--max-pin-suggestions` controls global suggested anchors (default 12; `0` disables).
- `--signal-kind` filters extracted signals to selected kinds (repeatable).
- `--pin-signal-kind` filters pin suggestions to selected kinds (repeatable).
- `--focus-priority-bonus` raises priority for focus-session suggestions (default 15).
- `--min-signal-priority` drops weaker signals by score (for lower-noise output).
- `--profile` applies policy presets (`balanced`, `questions`, `blockers`, `strict`) and can still be overridden by explicit flags.
- `--require-signal-kind` fails when a required kind is absent and refuses `--requirements-out` / `--bundle-out` generation.
- Each pin suggestion includes a `pin_command_template` with placeholders for archive and requirements paths.
- `--requirements-out` writes a full dialogue requirements contract directly from suggested pins.
- `--bundle-out` compiles a handoff bundle from generated suggestions in one command.
- `--audit-family-bundle` runs immediate audit on the generated bundle and returns findings.
- The digest does not install hooks, contact providers, or modify agent stores.
- No uniqueness, adoption, or willingness-to-pay claim is made.

## Tests

```bash
python -m unittest tests.test_family -v
```
