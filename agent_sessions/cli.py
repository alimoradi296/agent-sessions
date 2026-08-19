"""CLI entry point for agent-sessions.

Commands:
  export     Export a single session by ID (also used as hook target)
  bulk       Export all sessions for an agent
  search     Search across all exported sessions
  install    Install the Stop hook for an agent
  stats      Show aggregate stats across all sessions
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

from agent_sessions.models import Agent, Session
from agent_sessions.parsers import PARSERS
from agent_sessions.renderers.index import IndexRenderer
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.renderers.markdown import MarkdownRenderer


def resolve_output_dir(cwd: Optional[str]) -> Path:
    if cwd:
        p = Path(cwd)
        if (p / "docs" / "sessions").is_dir():
            return p / "docs" / "sessions"
        if (p / "docs").is_dir():
            out = p / "docs" / "sessions"
            out.mkdir(exist_ok=True)
            return out
    fallback = Path.home() / ".agent-sessions" / "exports"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def export_session(session: Session, out_dir: Path, dry_run: bool = False) -> None:
    if dry_run:
        print(f"[dry-run] Would write: {out_dir / f'{session.id}.md'}")
        print(f"  Agent:    {session.agent.value}")
        print(f"  Title:    {session.title}")
        print(f"  Branch:   {session.branch}")
        print(f"  Duration: {session.duration_human}")
        print(f"  Messages: {session.message_count}")
        if session.usage.total_tokens:
            print(f"  Tokens:   {session.usage.total_tokens:,}")
        return

    md_path = MarkdownRenderer.write(session, out_dir)
    IndexRenderer.update(session, out_dir / "SESSION_INDEX.md")
    JsonIndexRenderer.update(session, out_dir / "sessions.json")
    print(f"Exported → {md_path}")


# ── Hook entry point ────────────────────────────────────────────────────────
# Called by Claude Code Stop hook: reads JSON from stdin

def cmd_hook(args: argparse.Namespace) -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return

    agent_name = getattr(args, "agent", None) or "claude"
    session_id = payload.get("session_id") or payload.get("sessionId") or payload.get("id", "")
    cwd = payload.get("cwd") or payload.get("workspaceFolder", "")

    if not session_id:
        return

    parser_cls = PARSERS.get(agent_name)
    if not parser_cls:
        return

    path = parser_cls.find_session_file(session_id)
    if not path:
        return

    session = parser_cls.parse(path)
    if not session:
        return

    out_dir = resolve_output_dir(cwd)
    export_session(session, out_dir)


# ── Export command ──────────────────────────────────────────────────────────

def cmd_export(args: argparse.Namespace) -> None:
    parser_cls = PARSERS.get(args.agent)
    if not parser_cls:
        print(f"Unknown agent: {args.agent}", file=sys.stderr)
        sys.exit(1)

    path = parser_cls.find_session_file(args.session_id)
    if not path:
        print(f"Session not found: {args.session_id}", file=sys.stderr)
        sys.exit(1)

    session = parser_cls.parse(path)
    if not session:
        print("Session has no messages.", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.output) if args.output else resolve_output_dir(args.cwd)
    export_session(session, out_dir, dry_run=args.dry_run)


# ── Bulk command ────────────────────────────────────────────────────────────

def cmd_bulk(args: argparse.Namespace) -> None:
    agents = [args.agent] if args.agent else list(PARSERS.keys())
    out_dir = Path(args.output) if args.output else resolve_output_dir(args.cwd)

    total = 0
    for agent_name in agents:
        parser_cls = PARSERS[agent_name]
        if agent_name == "cursor":
            paths = parser_cls.list_sessions(project_slug=args.project)
        elif agent_name == "claude":
            paths = parser_cls.list_sessions(project_slug=args.project)
        else:
            paths = parser_cls.list_sessions()

        for path in paths:
            session = parser_cls.parse(path)
            if session:
                export_session(session, out_dir, dry_run=args.dry_run)
                total += 1

    print(f"\nExported {total} sessions to {out_dir}")


# ── Search command ──────────────────────────────────────────────────────────

def cmd_search(args: argparse.Namespace) -> None:
    search_dir = Path(args.directory) if args.directory else resolve_output_dir(None)
    pattern = re.compile(args.query, re.IGNORECASE)
    hits = 0

    # Search the JSON index first (fast path)
    json_idx = search_dir / "sessions.json"
    if json_idx.exists():
        try:
            data = json.loads(json_idx.read_text())
            sessions = data.get("sessions", []) if isinstance(data, dict) else data
            for entry in sessions:
                searchable = f"{entry.get('title','')} {entry.get('summary','')} {entry.get('branch','')}"
                if pattern.search(searchable):
                    agent = entry.get("agent", "?")
                    date = entry.get("date", "?")
                    title = entry.get("title", "?")[:80]
                    duration = entry.get("duration_human", "?")
                    print(f"  [{agent}] {date}  {duration:>8s}  {title}")
                    print(f"           → {entry.get('file', '?')}")
                    hits += 1
        except json.JSONDecodeError:
            pass

    if hits == 0:
        # Fallback: grep through markdown files
        for md in sorted(search_dir.glob("*.md"), reverse=True):
            if md.name == "SESSION_INDEX.md":
                continue
            content = md.read_text(encoding="utf-8", errors="replace")
            if pattern.search(content):
                first_line = content.split("\n")[0].lstrip("# ").strip()
                print(f"  {first_line[:80]}")
                print(f"           → {md.name}")
                hits += 1

    if hits == 0:
        print("No matches.")
    else:
        print(f"\n{hits} session(s) matched.")


# ── Stats command ───────────────────────────────────────────────────────────

def cmd_stats(args: argparse.Namespace) -> None:
    search_dir = Path(args.directory) if args.directory else resolve_output_dir(None)
    json_idx = search_dir / "sessions.json"

    if not json_idx.exists():
        print("No sessions.json found. Run 'bulk' first.", file=sys.stderr)
        sys.exit(1)

    data = json.loads(json_idx.read_text())
    sessions = data.get("sessions", []) if isinstance(data, dict) else data

    if not sessions:
        print("No sessions found.")
        return

    by_agent: dict[str, list] = {}
    total_tokens = 0
    total_duration = 0.0
    total_messages = 0

    for s in sessions:
        agent = s.get("agent", "unknown")
        by_agent.setdefault(agent, []).append(s)
        tokens = s.get("tokens", {})
        total_tokens += tokens.get("total", 0)
        dur = s.get("duration_seconds")
        if dur:
            total_duration += dur
        total_messages += s.get("message_count", 0)

    print(f"Total sessions: {len(sessions)}")
    print(f"Total messages: {total_messages:,}")
    print(f"Total tokens:   {total_tokens:,}")
    hours = total_duration / 3600
    print(f"Total duration: {hours:.1f}h")
    print()

    for agent, agent_sessions in sorted(by_agent.items()):
        agent_tokens = sum(s.get("tokens", {}).get("total", 0) for s in agent_sessions)
        agent_dur = sum(s.get("duration_seconds", 0) or 0 for s in agent_sessions)
        print(f"  {agent}: {len(agent_sessions)} sessions, {agent_tokens:,} tokens, {agent_dur/3600:.1f}h")


# ── Install command ─────────────────────────────────────────────────────────

CLAUDE_HOOK_SCRIPT = """\
#!/usr/bin/env bash
set -euo pipefail
cat | python3 -m agent_sessions hook
"""

def cmd_install(args: argparse.Namespace) -> None:
    agent = args.agent

    if agent == "claude":
        scripts_dir = Path.home() / ".claude" / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        hook_path = scripts_dir / "export-session.sh"
        hook_path.write_text(CLAUDE_HOOK_SCRIPT)
        hook_path.chmod(0o755)

        settings_path = Path.home() / ".claude" / "settings.json"
        hook_entry = {
            "type": "command",
            "command": f"bash {hook_path}",
            "timeout": 15,
            "statusMessage": "Exporting session transcript...",
        }

        if settings_path.exists():
            settings = json.loads(settings_path.read_text())
        else:
            settings = {}

        hooks = settings.setdefault("hooks", {})
        stop_hooks = hooks.setdefault("Stop", [])

        already = any(
            h.get("command", "").endswith("export-session.sh")
            for group in stop_hooks
            for h in group.get("hooks", [])
        )
        if not already:
            stop_hooks.append({"hooks": [hook_entry]})
            settings_path.write_text(json.dumps(settings, indent=2) + "\n")
            print(f"Hook installed: {hook_path}")
            print(f"Settings updated: {settings_path}")
        else:
            print("Hook already installed.")

    elif agent == "cursor":
        print("Cursor hook installation:")
        print("  Cursor uses hooks.json in .cursor/ — add this to your project's .cursor/hooks.json:")
        print()
        print(json.dumps({
            "hooks": {
                "agent-end": [{
                    "command": "python3 -m agent_sessions hook",
                    "timeout": 15,
                }]
            }
        }, indent=2))

    elif agent == "codex":
        print("Codex does not currently support Stop hooks.")
        print("Use 'agent-sessions bulk --agent codex' to export all sessions manually.")

    else:
        print(f"Unknown agent: {agent}", file=sys.stderr)
        sys.exit(1)


# ── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="agent-sessions",
        description="Universal AI agent session exporter",
    )
    sub = parser.add_subparsers(dest="command")

    # hook (stdin-driven, used by Stop hooks)
    p_hook = sub.add_parser("hook", help="Hook entry point (reads JSON from stdin)")
    p_hook.add_argument("--agent", choices=list(PARSERS.keys()), default="claude", help="Which agent (default: claude)")

    # export
    p_export = sub.add_parser("export", help="Export a single session")
    p_export.add_argument("agent", choices=list(PARSERS.keys()))
    p_export.add_argument("session_id")
    p_export.add_argument("-o", "--output", help="Output directory")
    p_export.add_argument("--cwd", help="Project working directory (for auto-detection)")
    p_export.add_argument("--dry-run", action="store_true", help="Show what would be exported")

    # bulk
    p_bulk = sub.add_parser("bulk", help="Export all sessions")
    p_bulk.add_argument("--agent", choices=list(PARSERS.keys()), help="Only this agent (default: all)")
    p_bulk.add_argument("--project", help="Project slug to filter by")
    p_bulk.add_argument("-o", "--output", help="Output directory")
    p_bulk.add_argument("--cwd", help="Project working directory")
    p_bulk.add_argument("--dry-run", action="store_true", help="Show what would be exported")

    # search
    p_search = sub.add_parser("search", help="Search exported sessions")
    p_search.add_argument("query", help="Search term (regex)")
    p_search.add_argument("-d", "--directory", help="Directory to search in")

    # stats
    p_stats = sub.add_parser("stats", help="Show aggregate session stats")
    p_stats.add_argument("-d", "--directory", help="Directory with sessions.json")

    # install
    p_install = sub.add_parser("install", help="Install the Stop hook for an agent")
    p_install.add_argument("agent", choices=["claude", "codex", "cursor"])

    args = parser.parse_args()

    if args.command == "hook":
        cmd_hook(args)
    elif args.command == "export":
        cmd_export(args)
    elif args.command == "bulk":
        cmd_bulk(args)
    elif args.command == "search":
        cmd_search(args)
    elif args.command == "stats":
        cmd_stats(args)
    elif args.command == "install":
        cmd_install(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
