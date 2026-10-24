"""CLI entry point for agent-sessions.

Commands:
  export       Export a single session by ID (also used as hook target)
  bulk         Export all sessions for an agent
  search       Search across all exported sessions
  stats        Show aggregate stats across all sessions
  distill      Extract structured knowledge from sessions
  link         Find related sessions / build session graph
  to-obsidian  Export distilled sessions as Obsidian notes
  report       Generate weekly/aggregate report
  context      Build a local pack of cited transcript excerpts
  reconcile    Export missing or changed sessions from local sources
  doctor       Inspect sources, exports, indexes, and hooks without changes
  install      Install the Stop hook for an agent
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import re
import sys
from datetime import date
from pathlib import Path
from typing import Optional

from agent_sessions.analysis.distiller import Distiller, DistilledSession
from agent_sessions.analysis.context import DEFAULT_MAX_CHARS, build_context
from agent_sessions.analysis.doctor import Doctor, render_doctor
from agent_sessions.analysis.linker import build_graph, load_distilled_sessions, query_graph
from agent_sessions.analysis.obsidian import ObsidianExporter
from agent_sessions.analysis.report import WeeklyReport, week_start
from agent_sessions.reconcile import reconcile
from agent_sessions.models import Agent, Session
from agent_sessions.hook_setup import install_hooks
from agent_sessions.parsers import PARSERS
from agent_sessions.parsers.codex import CodexParser
from agent_sessions.renderers.index import IndexRenderer
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.renderers.markdown import MarkdownRenderer
from agent_sessions.storage import (
    DEFAULT_LOCK_TIMEOUT, StorageError, directory_lock, atomic_write_many,
    atomic_write_text, validate_session_id,
)


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


def export_session(session: Session, out_dir: Path, dry_run: bool = False,
                   lock_timeout: float = DEFAULT_LOCK_TIMEOUT) -> None:
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

    validate_session_id(session.id)
    md_path = out_dir / f"{session.id}.md"
    with directory_lock(out_dir, timeout=lock_timeout):
        # Validate both existing indexes and prepare every payload before
        # replacing any destination. JSON is the last commit marker.
        json_path = out_dir / "sessions.json"
        md_index_path = out_dir / "SESSION_INDEX.md"
        json_text = JsonIndexRenderer.render_update(session, json_path)
        index_text = IndexRenderer.render_update(session, md_index_path)
        atomic_write_many({md_path: MarkdownRenderer.render(session),
                           md_index_path: index_text, json_path: json_text})
    print(f"Exported → {md_path}")


def load_source_session(agent: str, session_id: str) -> Optional[Session]:
    parser_cls = PARSERS[agent]
    if agent == "codex":
        return CodexParser.parse_many(CodexParser.find_session_files(session_id))
    path = parser_cls.find_session_file(session_id)
    return parser_cls.parse(path) if path else None


# ── Hook entry point ────────────────────────────────────────────────────────
# Called by agent Stop hooks: reads JSON from stdin

def cmd_hook(args: argparse.Namespace) -> None:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, UnicodeError) as error:
        raise StorageError("Hook input must be a JSON object.") from error
    if not isinstance(payload, dict):
        raise StorageError("Hook input must be a JSON object.")
    agent = getattr(args, "agent", None) or "claude"
    keys = ("conversation_id", "session_id", "sessionId", "id") if agent == "cursor" else ("session_id", "sessionId", "id")
    sid = next((payload.get(key) for key in keys if payload.get(key)), None)
    validate_session_id(sid)
    hint = payload.get("transcript_path")
    if hint is not None and not isinstance(hint, str):
        raise StorageError("Hook transcript_path must be a string or null.")
    if hint:
        path = Path(hint).expanduser().resolve()
    else:
        path = None
    # Transcript paths are convenience hints. When an agent supplies text or
    # no current file, discover its supported JSONL by the stable session ID.
    if path is not None and path.suffix == ".jsonl" and path.is_file():
        if agent == "cursor":
            if path.stem != sid or path.parent.name != sid or path.parent.parent.name != "agent-transcripts":
                raise StorageError("Cursor transcript_path does not match the main conversation.")
            session = PARSERS[agent].parse(path)
        elif agent == "codex":
            if CodexParser.session_id(path) != sid:
                raise StorageError("Codex transcript_path does not match the session ID.")
            root = next((p for p in path.parents if p.name == "sessions" and p.parent.name == ".codex"), None)
            if root is None:
                raise StorageError("Codex transcript_path must be under a .codex/sessions directory.")
            paths = [p for p in root.rglob("*.jsonl") if CodexParser.session_id(p) == sid]
            session = CodexParser.parse_many(paths)
        else:
            session = load_source_session(agent, sid)
    else:
        session = load_source_session(agent, sid)
    if session is None:
        raise StorageError("No supported session transcript found. Run doctor to check source discovery.")
    # Automatic hooks use a private global destination, never project docs.
    output = getattr(args, "output", None)
    out_dir = Path(output).expanduser() if output else Path.home() / ".agent-sessions/exports"
    with contextlib.redirect_stdout(io.StringIO()):
        export_session(session, out_dir, lock_timeout=getattr(args, "lock_timeout", DEFAULT_LOCK_TIMEOUT))
    # Codex Stop requires JSON; Cursor stop accepts an empty response object.
    print("{}")


# ── Export command ──────────────────────────────────────────────────────────

def cmd_export(args: argparse.Namespace) -> None:
    parser_cls = PARSERS.get(args.agent)
    if not parser_cls:
        print(f"Unknown agent: {args.agent}", file=sys.stderr)
        sys.exit(1)

    session = load_source_session(args.agent, args.session_id)
    if not session:
        print("Session not found or has no messages.", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.output) if args.output else resolve_output_dir(args.cwd)
    export_session(session, out_dir, dry_run=args.dry_run,
                   lock_timeout=getattr(args, "lock_timeout", DEFAULT_LOCK_TIMEOUT))


# ── Bulk command ────────────────────────────────────────────────────────────

def cmd_bulk(args: argparse.Namespace) -> None:
    agents = [args.agent] if args.agent else list(PARSERS.keys())
    out_dir = Path(args.output) if args.output else resolve_output_dir(args.cwd)

    since = getattr(args, "since", None)
    until = getattr(args, "until", None)
    if since and until and since >= until:
        raise ValueError("--until must be after --since")
    coverage = []
    total = 0
    for agent_name in agents:
        parser_cls = PARSERS[agent_name]
        if agent_name == "cursor":
            paths = parser_cls.list_sessions(project_slug=args.project)
        elif agent_name == "claude":
            paths = parser_cls.list_sessions(project_slug=args.project)
        else:
            paths = parser_cls.list_sessions()

        groups: dict[str, list[Path]] = {}
        for path in paths:
            try:
                key = CodexParser.session_id(path) if agent_name == "codex" else str(path)
            except (OSError, UnicodeError) as error:
                coverage.append({"agent": agent_name, "source_path": str(path),
                                 "status": "error", "error_type": type(error).__name__})
                continue
            groups.setdefault(key, []).append(path)
        for group in groups.values():
            try:
                session = (CodexParser.parse_many(group) if agent_name == "codex"
                           else parser_cls.parse(group[0]))
            except (OSError, UnicodeError) as error:
                coverage.extend({"agent": agent_name, "source_path": str(path),
                                 "status": "error", "error_type": type(error).__name__}
                                for path in group)
                continue
            status = "empty"
            if session:
                status = "exported"
                if ((since and session.date_str < since)
                        or (until and session.date_str >= until)):
                    status = "outside_period"
                if status == "exported":
                    export_session(session, out_dir, dry_run=args.dry_run,
                                   lock_timeout=getattr(args, "lock_timeout", DEFAULT_LOCK_TIMEOUT))
                    total += 1
            coverage.extend({
                "agent": agent_name, "source_path": str(path), "status": status,
                "session_id": session.id if session else None,
                "date": session.date_str if session else None,
                "date_source": session.date_source if session else "unknown",
            } for path in group)

    if getattr(args, "coverage", False) and not args.dry_run:
        coverage_text = json.dumps({
            "version": 1, "source_files": len(coverage),
            "exported_sessions": total, "sources": coverage,
        }, indent=2) + "\n"
        with directory_lock(out_dir, timeout=getattr(args, "lock_timeout", DEFAULT_LOCK_TIMEOUT)):
            atomic_write_text(out_dir / "coverage.json", coverage_text)

    print(f"\nExported {total} sessions to {out_dir}")
    errors = sum(row["status"] == "error" for row in coverage)
    if errors:
        print(f"Could not read {errors} source file(s). Check coverage.json when enabled.", file=sys.stderr)
        sys.exit(1)


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


def load_sessions_index(directory: Path) -> dict[str, dict]:
    json_idx = directory / "sessions.json"
    if not json_idx.exists():
        return {}
    try:
        data = json.loads(json_idx.read_text(encoding="utf-8"))
        sessions = data.get("sessions", []) if isinstance(data, dict) else data
        return {s["id"]: s for s in sessions if "id" in s}
    except (json.JSONDecodeError, KeyError):
        return {}


def distilled_dir_for(directory: Path) -> Path:
    d = directory / "distilled"
    d.mkdir(exist_ok=True)
    return d


def cmd_distill(args: argparse.Namespace) -> None:
    directory = Path(args.directory) if args.directory else resolve_output_dir(None)
    out_dir = distilled_dir_for(directory)
    index = load_sessions_index(directory)
    count = 0

    if args.session_id:
        targets = [args.session_id]
    else:
        targets = [p.stem for p in directory.glob("*.md") if p.name != "SESSION_INDEX.md"]

    for sid in targets:
        meta = index.get(sid, {})
        md_path = directory / f"{sid}.md"

        distilled: Optional[DistilledSession] = None

        # Try re-parsing from source for richer tool data
        agent = meta.get("agent")
        if agent and agent in PARSERS:
            session = load_source_session(agent, sid)
            if session:
                distilled = Distiller.distill(session)

        if distilled is None and md_path.exists():
            distilled = Distiller.distill_from_markdown(md_path, meta)

        if distilled is None:
            continue

        if args.significant_only and not Distiller.is_significant(distilled, args.min_duration):
            continue

        if args.dry_run:
            print(f"[dry-run] {sid} score={distilled.significance} topic={distilled.topic[:60]}")
            count += 1
            continue

        path = distilled.save(out_dir)
        print(f"Distilled → {path}")
        count += 1

    print(f"\nDistilled {count} session(s) to {out_dir}")


def cmd_link(args: argparse.Namespace) -> None:
    directory = Path(args.directory) if args.directory else resolve_output_dir(None)
    d_dir = distilled_dir_for(directory)

    if args.build or not any([args.prd, args.branch, args.file, args.session_id]):
        distilled = load_distilled_sessions(d_dir)
        if not distilled:
            print("No distilled sessions. Run 'distill --all' first.", file=sys.stderr)
            sys.exit(1)
        graph = build_graph(distilled)
        graph_path = directory / "sessions_graph.json"
        graph.save(graph_path)
        print(f"Graph built → {graph_path}")
        print(f"  {len(graph.nodes)} nodes, {len(graph.edges)} edges")
        if not any([args.prd, args.branch, args.file, args.session_id]):
            return

    distilled = load_distilled_sessions(d_dir)
    graph_path = directory / "sessions_graph.json"
    graph = build_graph(distilled)
    if graph_path.exists():
        try:
            from agent_sessions.analysis.linker import SessionGraph
            graph = SessionGraph.load(graph_path)
        except (json.JSONDecodeError, TypeError, KeyError):
            pass

    results = query_graph(
        graph, distilled,
        prd=args.prd,
        branch=args.branch,
        file_path=args.file,
        session_id=args.session_id,
    )

    if not results:
        print("No linked sessions found.")
        return

    for d in sorted(results, key=lambda x: x.get("date", ""), reverse=True):
        prds = ", ".join(d.get("prds", [])[:2]) or "-"
        print(f"  [{d.get('agent')}] {d.get('date')} score={d.get('significance')}  {d.get('topic', '')[:60]}")
        print(f"           PRDs: {prds}  branch: {d.get('branch', '?')}")
    print(f"\n{len(results)} session(s) linked.")


def cmd_to_obsidian(args: argparse.Namespace) -> None:
    directory = Path(args.directory) if args.directory else resolve_output_dir(None)
    d_dir = distilled_dir_for(directory)
    vault = Path(args.vault).expanduser()

    if not vault.is_dir():
        print(f"Vault not found: {vault}", file=sys.stderr)
        sys.exit(1)

    since = args.since or ""
    count = 0

    for path in sorted(d_dir.glob("*.distilled.json")):
        try:
            distilled = DistilledSession.load(path)
        except (json.JSONDecodeError, TypeError, KeyError):
            continue

        if since and (distilled.date or "") < since:
            continue

        if args.significant_only and distilled.significance < args.min_significance:
            continue

        session_md = directory / f"{distilled.session_id}.md"
        md_ref = str(session_md) if session_md.exists() else None

        if args.dry_run:
            note = ObsidianExporter.note_path(vault, distilled, args.folder)
            print(f"[dry-run] Would write → {note}")
            count += 1
            continue

        out = ObsidianExporter.write(vault, distilled, args.folder, md_ref)
        print(f"Obsidian → {out}")
        count += 1

    print(f"\nExported {count} note(s) to {vault / (args.folder or ObsidianExporter.DEFAULT_FOLDER)}")


def cmd_report(args: argparse.Namespace) -> None:
    directory = Path(args.directory) if args.directory else resolve_output_dir(None)

    since = args.since
    if args.week:
        since = week_start(7)
        label = f"Week of {since}"
    elif since:
        label = f"Since {since}"
    else:
        label = "All time"

    report = WeeklyReport.from_directory(directory, since=since)
    text = report.render(label)

    if args.output:
        out = Path(args.output)
        report.save(out, label)
        print(f"Report → {out}")
    else:
        print(text)


def cmd_context(args: argparse.Namespace) -> None:
    directory = Path(args.directory) if args.directory else Path.home() / ".agent-sessions" / "exports"
    try:
        text = build_context(directory, args.query, args.last, args.max_chars)
    except ValueError as error:
        raise StorageError(str(error)) from error
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(out, text)
        print(f"Context pack → {out}")
    else:
        print(text, end="")


def cmd_reconcile(args: argparse.Namespace) -> None:
    directory = Path(args.output).expanduser() if args.output else Path.home() / ".agent-sessions" / "exports"
    report = reconcile(directory, [args.agent] if args.agent else None,
                       dry_run=args.dry_run, lock_timeout=args.lock_timeout)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        counts = report['counts']
        changed = counts['would_export'] if args.dry_run else counts['exported']
        action = 'Would export' if args.dry_run else 'Exported'
        print(f"{action} {changed} session(s); unchanged: {counts['unchanged']}; empty: {counts['empty']}; errors: {counts['error']}.")
        for row in report['discovery'] + report['sources']:
            if row['status'] == 'error':
                print(f"Source error: {row['agent']} {row.get('session_id', '')} {row.get('error_type', 'source directory absent')}", file=sys.stderr)
    if report['exit_code']:
        raise SystemExit(report['exit_code'])


def cmd_doctor(args: argparse.Namespace) -> None:
    # Do not call resolve_output_dir: diagnostics must not create a directory.
    directory = Path(args.directory).expanduser() if args.directory else Path.home() / ".agent-sessions" / "exports"
    agents = [args.agent] if args.agent else None
    project = Path(args.project_dir).expanduser() if args.project_dir else None
    report = Doctor(directory, agents=agents, project_dir=project).run()
    print(json.dumps(report, indent=2) if args.json else render_doctor(report))
    if report["exit_code"]:
        sys.exit(report["exit_code"])


# ── Install command ─────────────────────────────────────────────────────────

CLAUDE_HOOK_SCRIPT = """\
#!/usr/bin/env bash
set -euo pipefail
cat | python3 -m agent_sessions hook
"""

def cmd_install(args: argparse.Namespace) -> None:
    agent = args.agent

    if agent == "claude":
        if getattr(args, "dry_run", False) or getattr(args, "output", None):
            raise StorageError("These install options currently apply to Codex and Cursor only.")
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

    elif agent in ("cursor", "codex"):
        output = Path(args.output) if getattr(args, "output", None) else None
        result = install_hooks(agent, output=output, dry_run=getattr(args, "dry_run", False))
        action = ("Would update" if result["dry_run"] else "Updated") if result["changed"] else "Already current"
        print(f"{action}: {result['config_path']}")
        print(f"Launcher: {result['script_path']}")
        print(f"Private exports: {result['output']}")
        for backup in result["backups"]:
            print(f"Backup: {backup}")
        if agent == "codex":
            print("Review changed hooks with /hooks before relying on automatic execution.")

    else:
        print(f"Unknown agent: {agent}", file=sys.stderr)
        sys.exit(1)


# ── Main ────────────────────────────────────────────────────────────────────

def iso_date(value: str) -> str:
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError
        return value
    except ValueError:
        raise argparse.ArgumentTypeError("Use a date in YYYY-MM-DD format")


def positive_int(value: str) -> int:
    try:
        result = int(value)
        if result < 1:
            raise ValueError
        return result
    except ValueError:
        raise argparse.ArgumentTypeError("Use a positive integer")


def lock_timeout(value: str) -> float:
    try:
        result = float(value)
        if not math.isfinite(result) or result < 0:
            raise ValueError
        return result
    except ValueError:
        raise argparse.ArgumentTypeError("Use a finite, nonnegative number of seconds")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="agent-sessions",
        description="Universal AI agent session exporter",
    )
    sub = parser.add_subparsers(dest="command")

    # hook (stdin-driven, used by Stop hooks)
    p_hook = sub.add_parser("hook", help="Hook entry point (reads JSON from stdin)")
    p_hook.add_argument("-o", "--output", help="Private export directory (default: ~/.agent-sessions/exports)")
    p_hook.add_argument("--agent", choices=list(PARSERS.keys()), default="claude", help="Which agent (default: claude)")
    p_hook.add_argument("--lock-timeout", type=lock_timeout, default=DEFAULT_LOCK_TIMEOUT, help="Seconds to wait for the export lock (default: 10)")

    # export
    p_export = sub.add_parser("export", help="Export a single session")
    p_export.add_argument("agent", choices=list(PARSERS.keys()))
    p_export.add_argument("session_id")
    p_export.add_argument("-o", "--output", help="Output directory")
    p_export.add_argument("--cwd", help="Project working directory (for auto-detection)")
    p_export.add_argument("--dry-run", action="store_true", help="Show what would be exported")
    p_export.add_argument("--lock-timeout", type=lock_timeout, default=DEFAULT_LOCK_TIMEOUT, help="Seconds to wait for the export lock (default: 10)")

    # bulk
    p_bulk = sub.add_parser("bulk", help="Export all sessions")
    p_bulk.add_argument("--agent", choices=list(PARSERS.keys()), help="Only this agent (default: all)")
    p_bulk.add_argument("--project", help="Project slug to filter by")
    p_bulk.add_argument("-o", "--output", help="Output directory")
    p_bulk.add_argument("--cwd", help="Project working directory")
    p_bulk.add_argument("--dry-run", action="store_true", help="Show what would be exported")
    p_bulk.add_argument("--since", type=iso_date, help="Session date on/after YYYY-MM-DD")
    p_bulk.add_argument("--until", type=iso_date, help="Session date before YYYY-MM-DD (exclusive)")
    p_bulk.add_argument("--coverage", action="store_true", help="Write local coverage.json with source file statuses")
    p_bulk.add_argument("--lock-timeout", type=lock_timeout, default=DEFAULT_LOCK_TIMEOUT, help="Seconds to wait for each export lock (default: 10)")

    # search
    p_search = sub.add_parser("search", help="Search exported sessions")
    p_search.add_argument("query", help="Search term (regex)")
    p_search.add_argument("-d", "--directory", help="Directory to search in")

    # stats
    p_stats = sub.add_parser("stats", help="Show aggregate session stats")
    p_stats.add_argument("-d", "--directory", help="Directory with sessions.json")

    # distill
    p_distill = sub.add_parser("distill", help="Extract structured knowledge from sessions")
    p_distill.add_argument("session_id", nargs="?", help="Single session ID (omit for --all)")
    p_distill.add_argument("-d", "--directory", help="Exported sessions directory")
    p_distill.add_argument("--significant-only", action="store_true", help="Skip low-value sessions")
    p_distill.add_argument("--min-duration", type=int, default=30, help="Min minutes for significant filter")
    p_distill.add_argument("--dry-run", action="store_true")

    # link
    p_link = sub.add_parser("link", help="Find related sessions / build graph")
    p_link.add_argument("-d", "--directory", help="Exported sessions directory")
    p_link.add_argument("--build", action="store_true", help="Build/rebuild sessions_graph.json")
    p_link.add_argument("--prd", help="Find sessions for a PRD (e.g. PRD-021)")
    p_link.add_argument("--branch", help="Find sessions on a branch")
    p_link.add_argument("--file", help="Find sessions that touched a file")
    p_link.add_argument("--session-id", help="Find sessions linked to this session")

    # to-obsidian
    p_obs = sub.add_parser("to-obsidian", help="Export distilled sessions as Obsidian notes")
    p_obs.add_argument("--vault", required=True, help="Obsidian vault path")
    p_obs.add_argument("-d", "--directory", help="Exported sessions directory")
    p_obs.add_argument("--folder", default="", help="Subfolder in vault (default: Agent Sessions)")
    p_obs.add_argument("--since", help="Only sessions on/after this date (YYYY-MM-DD)")
    p_obs.add_argument("--significant-only", action="store_true")
    p_obs.add_argument("--min-significance", type=int, default=3)
    p_obs.add_argument("--dry-run", action="store_true")

    # report
    p_report = sub.add_parser("report", help="Generate session report")
    p_report.add_argument("-d", "--directory", help="Exported sessions directory")
    p_report.add_argument("--week", action="store_true", help="Last 7 days only")
    p_report.add_argument("--since", help="Sessions on/after date (YYYY-MM-DD)")
    p_report.add_argument("-o", "--output", help="Write report to file")

    p_context = sub.add_parser("context", help="Build a local pack of cited transcript excerpts")
    p_context.add_argument("query", help="Literal topic text to find in conversations")
    p_context.add_argument("-d", "--directory", help="Exported sessions directory")
    p_context.add_argument("--last", type=positive_int, default=5, help="Maximum sources, ranked by relevance (default: 5)")
    p_context.add_argument("--max-chars", type=positive_int, default=DEFAULT_MAX_CHARS, help="Excerpt character budget per source (default: 24000)")
    p_context.add_argument("-o", "--output", help="Write the pack to a local file")

    p_reconcile = sub.add_parser("reconcile", help="Export only missing or changed local sessions")
    p_reconcile.add_argument("--agent", choices=list(PARSERS), help="Only this agent (default: all installed)")
    p_reconcile.add_argument("-o", "--output", help="Private export directory (default: ~/.agent-sessions/exports)")
    p_reconcile.add_argument("--dry-run", action="store_true", help="Compare without creating or changing any files")
    p_reconcile.add_argument("--json", action="store_true", help="Print the local reconciliation report as JSON")
    p_reconcile.add_argument("--lock-timeout", type=lock_timeout, default=DEFAULT_LOCK_TIMEOUT)

    p_doctor = sub.add_parser("doctor", help="Inspect sources, exports, indexes, and hooks without changes")
    p_doctor.add_argument("-d", "--directory", help="Export directory (default: ~/.agent-sessions/exports)")
    p_doctor.add_argument("--agent", choices=list(PARSERS), help="Inspect source and hook configuration for this agent")
    p_doctor.add_argument("--project-dir", help="Also inspect this project's .cursor/hooks.json")
    p_doctor.add_argument("--json", action="store_true", help="Print a JSON diagnostic report")

    # install
    p_install = sub.add_parser("install", help="Install the Stop hook for an agent")
    p_install.add_argument("agent", choices=["claude", "codex", "cursor"])
    p_install.add_argument("-o", "--output", help="Private export directory for Codex/Cursor hooks")
    p_install.add_argument("--dry-run", action="store_true", help="Inspect Codex/Cursor setup without writes")

    args = parser.parse_args()
    if args.command == "bulk" and args.since and args.until and args.since >= args.until:
        parser.error("--until must be after --since")

    commands = {
        "hook": cmd_hook, "export": cmd_export, "bulk": cmd_bulk,
        "search": cmd_search, "stats": cmd_stats, "distill": cmd_distill,
        "link": cmd_link, "to-obsidian": cmd_to_obsidian, "report": cmd_report,
        "reconcile": cmd_reconcile, "context": cmd_context, "doctor": cmd_doctor, "install": cmd_install,
    }
    if args.command not in commands:
        parser.print_help()
        return
    try:
        commands[args.command](args)
    except StorageError as error:
        parser.exit(1, f"agent-sessions: {error}\n")


if __name__ == "__main__":
    main()
