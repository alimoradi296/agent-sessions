# Privacy contract

`agent-sessions` is local-first. The public repository must never contain your real transcripts, exports, or machine paths.

## What stays on your machine

- Native Claude Code, Codex, and Cursor session stores
- Hook configuration, generated launchers, and backups under your home directory
- Default exports under `~/.agent-sessions/exports/`
- Private workspaces, topics, requirements packs, handoff bundles, and doctor reports
- Any file that quotes real conversation text, code, credentials, or absolute home paths

The CLI uses the Python standard library only. Export, search, family, resume, restore, and doctor commands do not upload transcript data.

## What may be public

- Source code and synthetic fixtures under `examples/` and `tests/`
- Documentation that uses invented session IDs and placeholder paths
- Generated marketing assets that contain no private text

## Hard rules for this repository

1. Do not commit real JSONL transcripts, Markdown exports, `sessions.json`, distilled graphs, or handoff bundles.
2. Do not paste private quotes into issues, PRs, screenshots, or README demos.
3. Prefer `/path/to/private-exports/` or temporary directories in docs.
4. Run demos from `examples/` only. Those demos invent sessions.
5. Treat `.gitignore` as a guard, not a redactor. Review `git status` before every push.

## Before you push

```bash
git status
git diff --stat
# Refuse any path under your home exports, real session IDs from private work, or quoted private dialogue.
python3 scripts/check_public_surface.py
```

## Sharing safely

If you need help in a public issue:

- Describe the agent and command
- Use a minimal synthetic reproduction from `examples/`
- Redact absolute paths, usernames, company names, and conversation text

Generated exports can contain prompts, secrets, tool output, and source paths. Keep them outside public repositories.
