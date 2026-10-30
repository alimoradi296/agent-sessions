"""CLI entry point for agent-sessions.

Commands:
  export       Export a single session by ID (also used as hook target)
  bulk         Export all sessions for an agent
  search       Search across all exported sessions
  index        Refresh the local passage search cache
  stats        Show aggregate stats across all sessions
  distill      Extract structured knowledge from sessions
  link         Find related sessions / build session graph
  to-obsidian  Export distilled sessions as Obsidian notes
  report       Generate weekly/aggregate report
  context      Build a local pack of cited transcript excerpts
  handoff      Pin critical evidence, build a handoff, and audit retained sources
  init         Create a private workspace outside Git checkouts
  topic        Save queries and evidence requirements for repeated use
  resume       Rebuild a saved topic's handoff and report readiness
  reconcile    Export missing or changed sessions from local sources
  restore      Recover captured file bytes into a new private directory
  family       Build a cited lineage digest from exported parent_id links
  doctor       Inspect sources, exports, indexes, and hooks without changes
  install      Install the Stop hook for an agent
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import sys
from datetime import date
from pathlib import Path
from typing import Optional

from agent_sessions.analysis.distiller import Distiller, DistilledSession
from agent_sessions.analysis.context import DEFAULT_MAX_CHARS, build_context
from agent_sessions.analysis.handoff import build_handoff
from agent_sessions.analysis.doctor import Doctor, render_doctor
from agent_sessions.analysis.linker import build_graph, load_distilled_sessions, query_graph
from agent_sessions.analysis.obsidian import ObsidianExporter
from agent_sessions.analysis.report import WeeklyReport, week_start
from agent_sessions.analysis.search import search_archive, render_search
from agent_sessions.analysis.continuity import (
    compile_handoff, write_bundle, audit_bundle, pin_requirement, review_requirement,
    link_challenge, load_requirements, note_source_inspection,
)
from agent_sessions.analysis.inspection import inspection_report, render_inspection
from agent_sessions.analysis.suggestions import suggest_requirements
from agent_sessions.analysis.selection_import import prepare_selection_review, import_selection_review
from agent_sessions.analysis.captured_files import recover_captured_adds
from agent_sessions.analysis.family import (
    ALLOWED_SIGNAL_KINDS,
    DEFAULT_MAX_PIN_SUGGESTIONS,
    DEFAULT_MAX_QUOTE_CHARS,
    build_family_digest,
    evaluate_required_signals,
    materialize_pin_suggestions,
    render_family_digest,
)
from agent_sessions.topic_review import prepare_topic_review, import_topic_review, mutate_topic_requirements
from agent_sessions.skill_bundle import continuation_skill
from agent_sessions.reconcile import reconcile
from agent_sessions.history import inspect_history, latest_changes, read_revision
from agent_sessions.workspace import (
    default_workspace, initialize_workspace, load_workspace, add_topic, set_topic, get_topic, resume_topic,
    topic_history_directory,
)
from agent_sessions.models import Session
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
            diagnostics = {}
            try:
                session = (CodexParser.parse_many(group, diagnostics=diagnostics) if agent_name == "codex"
                           else parser_cls.parse(group[0], diagnostics=diagnostics))
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
                "record_counts": diagnostics.get(str(path), {}),
            } for path in group)

    if getattr(args, "coverage", False) and not args.dry_run:
        coverage_text = json.dumps({
            "version": 2, "source_files": len(coverage),
            "exported_sessions": total, "sources": coverage,
        }, indent=2) + "\n"
        with directory_lock(out_dir, timeout=getattr(args, "lock_timeout", DEFAULT_LOCK_TIMEOUT)):
            atomic_write_text(out_dir / "coverage.json", coverage_text)

    print(f"\nExported {total} sessions to {out_dir}")
    affected = sum(bool(row.get("record_counts", {}).get("malformed", 0)
                        or row.get("record_counts", {}).get("unsupported", 0)) for row in coverage)
    if affected:
        print(f"Coverage warning: {affected} source file(s) contain malformed or unsupported records. "
              "Run doctor or enable --coverage for details.", file=sys.stderr)
    errors = sum(row["status"] == "error" for row in coverage)
    if errors:
        print(f"Could not read {errors} source file(s). Check coverage.json when enabled.", file=sys.stderr)
        sys.exit(1)


# ── Search command ──────────────────────────────────────────────────────────

def cmd_search(args: argparse.Namespace) -> None:
    directory = Path(args.directory).expanduser() if args.directory else Path.home() / ".agent-sessions" / "exports"
    report = search_archive(directory, args.query, match=args.match, limit=args.limit,
                            agent=args.agent, projects=getattr(args, 'projects', None), since=args.since,
                            until=args.until, role=args.role, view=args.view)
    print(json.dumps(report, indent=2, ensure_ascii=False) if args.json else render_search(report))


def cmd_index(args: argparse.Namespace) -> None:
    directory = Path(args.directory).expanduser() if args.directory else Path.home() / ".agent-sessions" / "exports"
    report = search_archive(directory, rebuild=args.rebuild, projects=args.projects, view=args.view)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        counts = report['index']
        print(f"Search index: {counts['sessions']} sessions / {counts['passages']} passages; "
              f"{counts['updated']} updated, {counts['unchanged']} unchanged, {counts['removed']} removed.")
        for warning in counts['warnings']:
            print(f"Warning: {warning['code']} / {warning['session_id']}")


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
        builder = build_handoff if args.format == "handoff" else build_context
        text = builder(directory, args.query, args.last, args.max_chars, projects=getattr(args, 'projects', None))
    except ValueError as error:
        raise StorageError(str(error)) from error
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(out, text)
        print(f"Context pack → {out}")
    else:
        print(text, end="")


def cmd_family(args: argparse.Namespace) -> None:
    directory = Path(args.directory) if args.directory else Path.home() / ".agent-sessions" / "exports"
    profile = args.profile or "balanced"
    profile_signal_kinds = None
    profile_pin_signal_kinds = None
    profile_focus_bonus = args.focus_priority_bonus
    if profile == "questions":
        profile_signal_kinds = ["open_question", "scope_boundary"]
        profile_pin_signal_kinds = ["open_question"]
        profile_focus_bonus = max(profile_focus_bonus, 20)
    elif profile == "blockers":
        profile_signal_kinds = ["reported_blocker", "next_action", "scope_boundary"]
        profile_pin_signal_kinds = ["reported_blocker", "next_action"]
        profile_focus_bonus = max(profile_focus_bonus, 25)
    elif profile == "strict":
        profile_signal_kinds = ["scope_boundary", "reported_blocker", "open_question", "next_action"]
        profile_pin_signal_kinds = ["scope_boundary", "reported_blocker", "open_question", "next_action"]
        profile_focus_bonus = max(profile_focus_bonus, 20)
    profile_min_priority = args.min_signal_priority
    if profile == "strict":
        profile_min_priority = max(profile_min_priority, 90)
    report = build_family_digest(
        directory,
        args.session_id,
        max_quote_chars=args.max_quote_chars,
        max_signals=args.max_signals,
        max_pin_suggestions=args.max_pin_suggestions,
        signal_kinds=args.signal_kinds or profile_signal_kinds,
        pin_signal_kinds=args.pin_signal_kinds or profile_pin_signal_kinds,
        focus_priority_bonus=profile_focus_bonus,
        min_signal_priority=profile_min_priority,
    )
    report["signal_profile"] = profile
    required_check = None
    if args.require_signal_kinds:
        required_check = evaluate_required_signals(report, args.require_signal_kinds)
        report["required_signals"] = required_check
    if required_check is not None and not required_check["passed"] and (
        args.requirements_out or args.bundle_out
    ):
        text = json.dumps(report, indent=2, ensure_ascii=False) + "\n" if args.json else render_family_digest(report)
        if args.output:
            out = Path(args.output)
            out.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(out, text)
            print(f"Family digest → {out}")
        else:
            print(text, end="")
        missing = ", ".join(required_check["missing"])
        print(
            f"agent-sessions: required signal kind(s) missing: {missing}. "
            "Refused requirements/bundle generation.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    if args.requirements_out:
        generated = materialize_pin_suggestions(
            directory,
            report,
            Path(args.requirements_out),
            overwrite=args.overwrite_requirements,
        )
        report["generated_requirements"] = generated
    requirements_path = Path(args.requirements_out).expanduser() if args.requirements_out else None
    if args.bundle_out:
        bundle = Path(args.bundle_out).expanduser()
        if requirements_path is None:
            requirements_path = bundle.parent / f"{args.session_id}.family-requirements.json"
            generated = materialize_pin_suggestions(directory, report, requirements_path, overwrite=True)
            report["generated_requirements"] = generated
        query = args.query if args.query else f"family:{args.session_id}"
        handoff, manifest = compile_handoff(
            directory,
            query,
            requirements_path,
            last=args.last,
            max_chars=args.max_chars,
            max_total_chars=args.max_total_chars,
        )
        write_bundle(bundle, handoff, manifest)
        report["family_bundle"] = dict(
            path=str(bundle),
            query=query,
            ready=manifest["ready"],
            verification=manifest.get("verification", "not_checked"),
        )
        if args.audit_family_bundle:
            audit = audit_bundle(bundle, directory)
            report["family_bundle"]["audit"] = audit
    text = json.dumps(report, indent=2, ensure_ascii=False) + "\n" if args.json else render_family_digest(report)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(out, text)
        print(f"Family digest → {out}")
        if args.requirements_out:
            print(f"Family requirements → {args.requirements_out}")
        if args.bundle_out:
            print(f"Family handoff bundle → {args.bundle_out}")
    else:
        print(text, end="")
        if args.requirements_out and not args.json:
            print(f"\nGenerated requirements: {args.requirements_out}")
        if args.bundle_out and not args.json:
            print(f"Family handoff bundle: {args.bundle_out}")
    if required_check is not None and not required_check["passed"] and not (
        args.requirements_out or args.bundle_out
    ):
        raise SystemExit(1)


def _workspace_directory(args):
    return Path(args.workspace).expanduser() if args.workspace else default_workspace()


def cmd_init(args: argparse.Namespace) -> None:
    root = _workspace_directory(args)
    config = initialize_workspace(root, Path(args.archive))
    print(json.dumps(config, indent=2) if args.json else f"Private workspace → {root}\nArchive → {config['archive']}")


def cmd_topic(args: argparse.Namespace) -> None:
    workspace = _workspace_directory(args)
    if args.topic_command in ('pin', 'link', 'review', 'acknowledge'):
        def operation(archive, requirements, topic):
            projects = topic.get('projects')
            if args.topic_command == 'pin':
                return pin_requirement(archive, requirements, args.id, args.session, args.section,
                                       args.quote, unit=args.unit, projects=projects)
            if args.topic_command == 'link':
                return link_challenge(archive, requirements, args.id, args.target, args.session, args.section,
                                      args.quote, args.note, unit=args.unit, projects=projects)
            if args.topic_command == 'review':
                return review_requirement(archive, requirements, args.id, args.candidate, args.note, projects=projects)
            return note_source_inspection(archive, requirements, args.session, args.snapshot, args.note, projects=projects)
        result = mutate_topic_requirements(workspace, args.name, operation)
        print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else
              f"{args.topic_command.capitalize()} recorded for {args.name}. Evidence remains not checked.")
        return
    if args.topic_command in ('prepare-review', 'import-review'):
        if args.topic_command == 'prepare-review':
            result = prepare_topic_review(workspace, args.name, max_prompt_chars=args.max_prompt_chars, batch_review=args.batch_review,
                                          compact_review=args.compact_review, max_total_prompt_chars=args.max_total_prompt_chars, view=args.view)
        else:
            result = import_topic_review(workspace, args.name, Path(args.packet).expanduser(), Path(args.answer).expanduser())
        print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else
              json.dumps(result, ensure_ascii=False))
        if result.get('status') == 'over_budget':
            raise SystemExit(1)
        return
    if args.topic_command == 'list':
        _, config = load_workspace(workspace)
        if args.json:
            print(json.dumps(config['topics'], indent=2, ensure_ascii=False))
        elif not config['topics']:
            print('No saved topics. Use topic add NAME --query TEXT.')
        else:
            for name, topic in sorted(config['topics'].items()):
                boundary = json.dumps(topic['projects'], ensure_ascii=False) if topic.get('projects') else 'all indexed sources'
                print(f"{name}: {topic['query']} / metadata scope: {boundary}")
    elif args.topic_command == 'add':
        topic = add_topic(workspace, args.name, args.query, requirements=args.requirements,
                          limits=dict(last=args.last, max_chars=args.max_chars, max_total_chars=args.max_total_chars),
                          projects=args.projects)
        print(json.dumps(topic, indent=2) if args.json else f"Saved topic {args.name}. Pin evidence with topic pin {args.name}.")
    elif args.topic_command == 'set':
        limits = {key: getattr(args, key) for key in ('last', 'max_chars', 'max_total_chars')
                  if getattr(args, key) is not None}
        topic = set_topic(workspace, args.name, query=args.query, limits=limits,
                          projects=[] if args.all_projects else args.projects)
        print(json.dumps(topic, indent=2) if args.json else f"Updated topic {args.name}. Evidence requirements remain linked.")
    else:
        _, archive, topic = get_topic(workspace, args.name)
        requirements = Path(topic['requirements'])
        if args.topic_command == 'search':
            report = search_archive(archive, args.query or topic['query'], match=args.match, limit=args.limit,
                                    projects=topic.get('projects'), view=args.view)
            print(json.dumps(report, indent=2, ensure_ascii=False) if args.json else render_search(report))
        elif args.topic_command == 'inspect':
            contract = load_requirements(requirements)
            report = inspection_report(archive, contract.get('source_inspections', []),
                                       projects=topic.get('projects'), session_id=args.session,
                                       changed_only=args.changed_only)
            print(json.dumps(report, indent=2, ensure_ascii=False) if args.json else render_inspection(report), end='\n' if args.json else '')
        elif args.topic_command == 'history':
            history = inspect_history(topic_history_directory(workspace, args.name))
            if args.json:
                print(json.dumps(history, indent=2))
            else:
                print('Historical captures. Recorded readiness does not establish current validity.')
                for item in history['revisions']:
                    status = 'ready at capture' if item['ready'] else 'draft at capture'
                    marker = ' / head' if item['id'] == history['head'] else ''
                    print(f"{item['id']} / {status}{marker}")
                if not history['revisions']:
                    print('No captures yet. Run resume NAME first.')
        elif args.topic_command == 'changes':
            report = latest_changes(topic_history_directory(workspace, args.name), include_diff=args.diff)
            if args.json:
                print(json.dumps(report, indent=2, ensure_ascii=False))
            else:
                print('Changes between captured handoffs. Historical evidence remains not checked.')
                for key, value in report['changes'].items():
                    if value or key in ('readiness_before', 'readiness_after'):
                        print(f"{key}: {json.dumps(value, ensure_ascii=False)}")
                if args.diff:
                    print(report['diff'], end='')
        elif args.topic_command == 'show':
            text, manifest = read_revision(topic_history_directory(workspace, args.name), args.revision)
            if args.json:
                print(json.dumps(dict(historical=True, verification='not_checked', revision=args.revision,
                                      handoff=text, manifest=manifest), indent=2, ensure_ascii=False))
            else:
                print('Historical capture. Audit against current exports before use.\n')
                print(text, end='')


def cmd_resume(args: argparse.Namespace) -> None:
    report, text = resume_topic(_workspace_directory(args), args.name)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    elif args.print_context and report['ready']:
        print(text, end='')
    else:
        stream = sys.stderr if args.print_context else sys.stdout
        status = 'Ready' if report['ready'] else 'Draft — review required'
        print(f"{status}: {report['handoff_path']}", file=stream)
        scope = report['manifest']['scope']
        inspection = report['manifest']['source_inspection']
        if inspection['pending']:
            print(f"  {inspection['pending']} source(s) have no current inspection note. "
                  f"Use topic inspect {args.name}. This queue is independent of readiness.", file=stream)
        if scope['projects']:
            print(f"  Project metadata scope: {scope['in_scope_sources']} matching sessions, "
                  f"{scope['excluded_sources']} excluded, {scope['missing_project_metadata']} without project metadata.", file=stream)
        history = report['history']
        if history['changed'] and history['previous_revision']:
            changes = history['changes']
            print(f"  Since previous capture: {len(changes['requirements_changed'])} requirement change(s), "
                  f"{len(changes['review_opened'])} new review candidate(s).", file=stream)
            if changes['scope_changed']:
                print('  The declared project metadata boundary changed.', file=stream)
        if not report['ready'] and report['last_ready_handoff_path']:
            print(f"  Previous ready capture retained for historical inspection: {report['last_ready_handoff_path']}", file=stream)
        for item in report['manifest']['requirements']:
            if item['status'] != 'covered':
                print(f"  {item['id']}: {item['status']}", file=stream)
            for candidate in item.get('unreviewed_candidates', []):
                print(f"  {item['id']}: review candidate {candidate['review_id']} ({candidate['kind']})", file=stream)
        if not report['manifest']['total_budget_passed']:
            print('  The complete handoff exceeds the saved total character limit.', file=stream)
        for warning in report['manifest']['relationship_scan_warnings']:
            print(f"  Archive scan incomplete: {warning['code']}", file=stream)
    if not report['ready']:
        raise SystemExit(1)


def cmd_handoff(args: argparse.Namespace) -> None:
    if args.handoff_command == 'import-review':
        report = import_selection_review(Path(args.packet).expanduser(), Path(args.answer).expanduser(),
                                         Path(args.output).expanduser())
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return
    directory = Path(args.directory).expanduser() if args.directory else Path.home() / ".agent-sessions" / "exports"
    if args.handoff_command == 'suggest':
        report = suggest_requirements(directory, args.query, projects=args.projects,
                                      limit=args.limit, max_paragraph_chars=args.max_paragraph_chars)
        print(json.dumps(report, indent=2, ensure_ascii=False))
    elif args.handoff_command == 'prepare-review':
        report = prepare_selection_review(directory, Path(args.output).expanduser(), args.query,
                                          projects=args.projects, max_prompt_chars=args.max_prompt_chars, batch_review=args.batch_review,
                                          compact_review=args.compact_review, max_total_prompt_chars=args.max_total_prompt_chars, view=args.view)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        if report.get('status') == 'over_budget':
            raise SystemExit(1)
    elif args.handoff_command == 'pin':
        anchor = pin_requirement(directory, Path(args.output).expanduser(), args.id,
                                 args.session, args.section, args.quote, unit=args.unit, projects=args.projects, view=args.view)
        print(json.dumps(anchor, indent=2, ensure_ascii=False) if args.json else
              f"Pinned {anchor['id']}: {anchor['session_id']} / section {anchor['section']}")
    elif args.handoff_command == 'link':
        anchor = link_challenge(directory, Path(args.requirements).expanduser(), args.id, args.target,
                                args.session, args.section, args.quote, args.note, unit=args.unit,
                                projects=args.projects)
        print(json.dumps(anchor, indent=2, ensure_ascii=False) if args.json else
              f"Linked {anchor['id']} as a challenge to {anchor['challenge_for']}. Review remains pending.")
    elif args.handoff_command == 'review':
        review = review_requirement(directory, Path(args.requirements).expanduser(), args.id, args.candidate, args.note, projects=args.projects)
        print(json.dumps(review, indent=2) if args.json else
              f"Review note recorded for {review['requirement_id']} / {review['candidate_id']}. Statements remain not checked.")
    elif args.handoff_command == 'build':
        text, manifest = compile_handoff(directory, args.query, Path(args.requirements),
                                         last=args.last, max_chars=args.max_chars, max_total_chars=args.max_total_chars,
                                         projects=args.projects)
        output = Path(args.output).expanduser()
        write_bundle(output, text, manifest)
        if args.json:
            print(json.dumps(manifest, indent=2, ensure_ascii=False))
        else:
            status = 'PASS' if manifest['ready'] else 'FAIL — draft only'
            print(f"Handoff readiness: {status}. Bundle → {output}")
            for item in manifest['requirements']:
                print(f"  {item['id']}: {item['status']}")
                for candidate in item.get('unreviewed_candidates', []):
                    print(f"    Review required: {candidate['kind']} / {candidate['witness']['session_id']}")
        if not manifest['ready']:
            raise SystemExit(1)
    elif args.handoff_command == 'audit':
        report = audit_bundle(Path(args.bundle).expanduser(), directory)
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print('Handoff evidence: ' + ('current' if report['coverage_passed'] else 'needs review'))
            for finding in report['findings']:
                print('  ' + json.dumps(finding))
        if report['exit_code']:
            raise SystemExit(report['exit_code'])
    else:
        raise ValueError('Use handoff pin, handoff build, or handoff audit.')


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


def cmd_restore(args: argparse.Namespace) -> None:
    report = recover_captured_adds(args.source, args.source_root, args.output)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        files = report["files"]
        current = report["current_comparison"]
        print(f"Recovered {len(files)} file(s) to {report['output']}.")
        print("Current project comparison: " + ", ".join(
            f"{count} {status}" for status, count in current.items()))
        print(f"Captured updates applied exactly: {report['exact_updates_applied']}; "
              f"blocked paths: {report['blocked_update_paths']}; "
              f"failed operations skipped: {report['failed_operations_skipped']}.")
        print(f"Execution verified: {'yes' if report['execution_verified'] else 'no'}; "
              f"latest state verified: {'yes' if report['latest_state_verified'] else 'no'}.")
        for item in files:
            status = item["current_status"].upper()
            if item["status"] == "captured_prefix":
                status += ", CAPTURED PREFIX"
            if item["execution_status"] != "confirmed_success":
                status += f", EXECUTION {item['execution_status'].upper()}"
            print(f"[{status}] {item['path']}")
        for item in report["deleted_files"]:
            print(f"[CAPTURED DELETION, EXECUTION {item['execution_status'].upper()}] {item['path']}")


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


def non_negative_int(value: str) -> int:
    try:
        result = int(value)
        if result < 0:
            raise ValueError
        return result
    except ValueError:
        raise argparse.ArgumentTypeError("Use a non-negative integer")


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

    p_init = sub.add_parser("init", help="Create private workspace state outside Git checkouts")
    p_init.add_argument("--archive", required=True, help="Explicit local export archive")
    p_init.add_argument("--workspace", help="Private workspace directory (default: ~/.agent-sessions/workspace)")
    p_init.add_argument("--json", action="store_true")

    p_topic = sub.add_parser("topic", help="Save queries and evidence requirements for repeated use")
    topic_commands = p_topic.add_subparsers(dest="topic_command", required=True)
    p_topics = topic_commands.add_parser("list", help="List saved topics without changing files")
    p_topics.add_argument("--workspace")
    p_topics.add_argument("--json", action="store_true")
    p_add_topic = topic_commands.add_parser("add", help="Save a topic query and handoff limits")
    p_add_topic.add_argument("name")
    p_add_topic.add_argument("--query", required=True)
    p_add_topic.add_argument("--requirements", help="Reuse an explicit existing requirements file")
    p_add_topic.add_argument("--last", type=positive_int, default=5)
    p_add_topic.add_argument("--max-chars", type=positive_int, default=DEFAULT_MAX_CHARS)
    p_add_topic.add_argument("--max-total-chars", type=positive_int, default=64_000)
    p_add_topic.add_argument("--workspace")
    p_add_topic.add_argument("--json", action="store_true")
    p_add_topic.add_argument("--project", dest="projects", action="append", help="Exact cwd or project slug. Repeat for explicit aliases.")
    p_set_topic = topic_commands.add_parser("set", help="Change a saved query or limit without replacing its evidence requirements")
    p_set_topic.add_argument("name")
    p_set_topic.add_argument("--query")
    p_set_topic.add_argument("--last", type=positive_int)
    p_set_topic.add_argument("--max-chars", type=positive_int)
    p_set_topic.add_argument("--max-total-chars", type=positive_int)
    p_set_topic.add_argument("--workspace")
    p_set_topic.add_argument("--json", action="store_true")
    project_scope = p_set_topic.add_mutually_exclusive_group()
    project_scope.add_argument("--project", dest="projects", action="append", help="Replace the project selectors. Repeat for explicit aliases.")
    project_scope.add_argument("--all-projects", action="store_true", help="Explicitly clear the project metadata boundary")
    for action in ('history', 'changes', 'show'):
        command = topic_commands.add_parser(action, help=f"{action.capitalize()} private captured handoffs")
        command.add_argument("name")
        command.add_argument("--workspace")
        command.add_argument("--json", action="store_true")
        if action == 'changes':
            command.add_argument("--diff", action="store_true", help="Include a unified diff of historical handoff text")
        elif action == 'show':
            command.add_argument("--revision", required=True, help="Complete revision hash from topic history")
    for action in ('prepare-review', 'import-review'):
        command = topic_commands.add_parser(action, help=f"{action.capitalize()} source-bound assistant evidence for a saved topic")
        command.add_argument("name")
        command.add_argument("--workspace")
        command.add_argument("--json", action="store_true")
        if action == 'prepare-review':
            command.add_argument("--view", choices=("dialogue", "evidence"), default=None)
            command.add_argument("--max-prompt-chars", type=positive_int, default=32000)
            command.add_argument("--batch-review", action="store_true", help="Split evidence into at most 32 bounded review prompts")
            command.add_argument("--compact-review", action="store_true", help="Use exact text references only when the complete plan is smaller without extra omissions")
            command.add_argument("--max-total-prompt-chars", type=positive_int, help="Do not publish a packet when routing plus all prompts exceed this explicit input budget")
        else:
            command.add_argument("packet")
            command.add_argument("--answer", required=True)
    for action in ('search', 'pin', 'link', 'review', 'inspect', 'acknowledge'):
        command = topic_commands.add_parser(action, help=f"{action.capitalize()} a saved topic's evidence")
        command.add_argument("name")
        command.add_argument("--workspace")
        command.add_argument("--json", action="store_true")
        if action == 'search':
            command.add_argument("--view", choices=("dialogue", "evidence"), default="dialogue")
            command.add_argument("query", nargs="?", help="Words to find (default: the saved topic query)")
            command.add_argument("--match", choices=("all", "any", "phrase"), default="all")
            command.add_argument("--limit", type=positive_int, default=10)
        elif action == 'inspect':
            command.add_argument("--session", help="Show current cleaned dialogue and its inspection snapshot id")
            command.add_argument("--changed-only", action="store_true", help="Omit complete sections unchanged since the last inspection note")
        elif action == 'acknowledge':
            command.add_argument("--session", required=True)
            command.add_argument("--snapshot", required=True, help="Exact inspection snapshot id from topic inspect")
            command.add_argument("--note", required=True, help="Operator inspection note. Does not resolve challenges or prove understanding.")
        else:
            command.add_argument("--id", required=True)
            if action in ('pin', 'link'):
                command.add_argument("--session", required=True)
                command.add_argument("--section", type=positive_int, required=True)
                command.add_argument("--quote", required=action == 'link')
                command.add_argument("--unit", choices=("section", "paragraph"), default="section")
                if action == 'link':
                    command.add_argument("--target", required=True, help="Existing requirement challenged by this passage")
                    command.add_argument("--note", required=True, help="Why this passage challenges the target. Not acceptance.")
            else:
                command.add_argument("--candidate", required=True)
                command.add_argument("--note", required=True)

    p_resume = sub.add_parser("resume", help="Rebuild a saved topic's handoff and report readiness")
    p_resume.add_argument("name")
    p_resume.add_argument("--workspace")
    resume_format = p_resume.add_mutually_exclusive_group()
    resume_format.add_argument("--json", action="store_true")
    resume_format.add_argument("--print", dest="print_context", action="store_true", help="Print handoff text only when all readiness gates pass")

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
    p_search.add_argument("query", help="Words to find in conversation passages (no regex or query operators)")
    p_search.add_argument("-d", "--directory", help="Directory to search in")
    p_search.add_argument("--match", choices=("all", "any", "phrase"), default="all")
    p_search.add_argument("--limit", type=positive_int, default=10, help="Maximum passages (1–100)")
    p_search.add_argument("--agent", choices=list(PARSERS))
    p_search.add_argument("--project", dest="projects", action="append", help="Exact project slug or working directory. Repeat for explicit aliases.")
    p_search.add_argument("--since", type=iso_date)
    p_search.add_argument("--until", type=iso_date, help="Exclusive end date")
    p_search.add_argument("--role", choices=("user", "assistant", "tool", "system"))
    p_search.add_argument("--view", choices=("dialogue", "evidence"), default="dialogue",
                          help="Evidence includes code, tool output, and phase-tagged messages with raw-source locators")
    p_search.add_argument("--json", action="store_true", help="Structured hits with source hashes and quote offsets")

    p_index = sub.add_parser("index", help="Refresh the local passage search cache")
    p_index.add_argument("-d", "--directory", help="Export archive directory")
    p_index.add_argument("--rebuild", action="store_true", help="Replace only the derived search cache")
    p_index.add_argument("--view", choices=("dialogue", "evidence"), default="dialogue")
    p_index.add_argument("--json", action="store_true")
    p_index.add_argument("--project", dest="projects", action="append", help="Exact project metadata selector. Repeat for aliases.")

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
    p_context.add_argument("--format", choices=("excerpts", "handoff"), default="excerpts", help="Output format (default: excerpts)")
    p_context.add_argument("-o", "--output", help="Write the pack to a local file")
    p_context.add_argument("--project", dest="projects", action="append", help="Exact cwd or project slug. Repeat for explicit aliases.")
    p_family = sub.add_parser(
        "family",
        help="Build a cited lineage digest from exported parent_id links",
    )
    p_family.add_argument("session_id", help="Focus session ID already present in the archive index")
    p_family.add_argument("-d", "--directory", help="Exported sessions directory")
    p_family.add_argument(
        "--max-quote-chars",
        type=positive_int,
        default=DEFAULT_MAX_QUOTE_CHARS,
        help=f"Maximum characters per quoted turn (default: {DEFAULT_MAX_QUOTE_CHARS})",
    )
    p_family.add_argument(
        "--max-signals",
        type=non_negative_int,
        default=8,
        help="Maximum continuation signals per family member (default: 8; 0 disables)",
    )
    p_family.add_argument(
        "--max-pin-suggestions",
        type=non_negative_int,
        default=DEFAULT_MAX_PIN_SUGGESTIONS,
        help=f"Maximum suggested handoff pins in output (default: {DEFAULT_MAX_PIN_SUGGESTIONS}; 0 disables)",
    )
    p_family.add_argument(
        "--signal-kind",
        dest="signal_kinds",
        action="append",
        choices=ALLOWED_SIGNAL_KINDS,
        help="Restrict extracted continuation signals to this kind; repeatable",
    )
    p_family.add_argument(
        "--pin-signal-kind",
        dest="pin_signal_kinds",
        action="append",
        choices=ALLOWED_SIGNAL_KINDS,
        help="Restrict suggested pins to this signal kind; repeatable",
    )
    p_family.add_argument(
        "--focus-priority-bonus",
        type=non_negative_int,
        default=15,
        help="Additional priority score for focus-session suggestions (default: 15)",
    )
    p_family.add_argument(
        "--min-signal-priority",
        type=non_negative_int,
        default=0,
        help="Drop extracted signals below this priority score (default: 0)",
    )
    p_family.add_argument(
        "--profile",
        choices=("balanced", "questions", "blockers", "strict"),
        default="balanced",
        help="Preset signal and pin policy (default: balanced)",
    )
    p_family.add_argument(
        "--require-signal-kind",
        dest="require_signal_kinds",
        action="append",
        choices=ALLOWED_SIGNAL_KINDS,
        help="Fail when this signal kind is absent from the family; repeatable",
    )
    p_family.add_argument(
        "--requirements-out",
        help="Write a dialogue requirements contract from suggested pins",
    )
    p_family.add_argument(
        "--overwrite-requirements",
        action="store_true",
        help="Replace an existing requirements file when used with --requirements-out",
    )
    p_family.add_argument(
        "--bundle-out",
        help="Write a handoff bundle generated from family suggested pins",
    )
    p_family.add_argument(
        "--query",
        help="Query label used when compiling --bundle-out (default: family:<session_id>)",
    )
    p_family.add_argument(
        "--last",
        type=positive_int,
        default=5,
        help="Maximum sources when compiling --bundle-out (default: 5)",
    )
    p_family.add_argument(
        "--max-chars",
        type=positive_int,
        default=DEFAULT_MAX_CHARS,
        help=f"Source excerpt character budget for --bundle-out (default: {DEFAULT_MAX_CHARS})",
    )
    p_family.add_argument(
        "--max-total-chars",
        type=positive_int,
        default=120_000,
        help="Total handoff character budget for --bundle-out (default: 120000)",
    )
    p_family.add_argument(
        "--audit-family-bundle",
        action="store_true",
        help="Run handoff audit immediately after writing --bundle-out",
    )
    p_family.add_argument("--json", action="store_true", help="Emit machine-readable JSON instead of Markdown")
    p_family.add_argument("-o", "--output", help="Write the digest to a local file")
    sub.add_parser("skill", help="Print the packaged assistant continuation skill without installing or changing configuration")

    p_handoff = sub.add_parser("handoff", help="Build and audit handoffs against required source evidence")
    handoff_commands = p_handoff.add_subparsers(dest="handoff_command", required=True)
    p_suggest = handoff_commands.add_parser("suggest", help="Read-only evidence proposals for assistant review; never accepts requirements")
    p_suggest.add_argument("query")
    p_suggest.add_argument("-d", "--directory", help="Existing private export archive")
    p_suggest.add_argument("--project", dest="projects", action="append", help="Exact cwd or project slug. Enables same-scope candidate expansion.")
    p_suggest.add_argument("--limit", type=positive_int, default=10)
    p_suggest.add_argument("--max-paragraph-chars", type=positive_int, default=2000)
    p_prepare_review = handoff_commands.add_parser("prepare-review", help="Create a private, version-bound source packet for assistant selection")
    p_prepare_review.add_argument("query")
    p_prepare_review.add_argument("--view", choices=("dialogue", "evidence"), default="dialogue")
    p_prepare_review.add_argument("-d", "--directory")
    p_prepare_review.add_argument("-o", "--output", required=True)
    p_prepare_review.add_argument("--project", dest="projects", action="append")
    p_prepare_review.add_argument("--max-prompt-chars", type=positive_int, default=32000)
    p_prepare_review.add_argument("--compact-review", action="store_true", help="Use exact text references only when the complete plan is smaller without extra omissions")
    p_prepare_review.add_argument("--max-total-prompt-chars", type=positive_int, help="Do not publish a packet when routing plus all prompts exceed this explicit input budget")
    p_prepare_review.add_argument("--batch-review", action="store_true", help="Split evidence into at most 32 bounded review prompts")
    p_import_review = handoff_commands.add_parser("import-review", help="Validate assistant-selected quotes and create a new requirements contract")
    p_import_review.add_argument("packet")
    p_import_review.add_argument("--answer", required=True)
    p_import_review.add_argument("-o", "--output", required=True)
    p_pin = handoff_commands.add_parser("pin", help="Require an exact source quote in future handoffs")
    p_pin.add_argument("--id", required=True, help="Meaningful requirement name, such as discovery-only")
    p_pin.add_argument("--session", required=True)
    p_pin.add_argument("--section", required=True, type=positive_int)
    p_pin.add_argument("--view", choices=("dialogue", "evidence"), default="dialogue",
                       help="Coordinate system; evidence uses raw message numbers from evidence search")
    p_pin.add_argument("--quote", help="Exact quote (default: entire selected section/message)")
    p_pin.add_argument("--unit", choices=("section", "paragraph"), default="section", help="Required evidence unit (default: section)")
    p_pin.add_argument("-d", "--directory", help="Export archive directory")
    p_pin.add_argument("-o", "--output", required=True, help="Private requirements JSON to create or append")
    p_pin.add_argument("--json", action="store_true")
    p_pin.add_argument("--project", dest="projects", action="append", help="Exact cwd or project slug. Repeat for explicit aliases.")
    p_link = handoff_commands.add_parser("link", help="Pin an operator-selected challenge to an existing requirement")
    p_link.add_argument("--requirements", required=True)
    p_link.add_argument("--id", required=True, help="New challenge evidence requirement id")
    p_link.add_argument("--target", required=True, help="Existing requirement challenged by this passage")
    p_link.add_argument("--session", required=True)
    p_link.add_argument("--section", required=True, type=positive_int)
    p_link.add_argument("--quote", required=True)
    p_link.add_argument("--note", required=True, help="Why this passage challenges the target. Not acceptance.")
    p_link.add_argument("--unit", choices=("section", "paragraph"), default="section")
    p_link.add_argument("-d", "--directory", help="Export archive directory")
    p_link.add_argument("--json", action="store_true")
    p_link.add_argument("--project", dest="projects", action="append", help="Exact cwd or project slug. Repeat for explicit aliases.")
    p_review = handoff_commands.add_parser("review", help="Record a review note for a recognized or operator-linked challenge")
    p_review.add_argument("--requirements", required=True)
    p_review.add_argument("--id", required=True, help="Requirement id")
    p_review.add_argument("--candidate", required=True, help="Review id from a draft manifest")
    p_review.add_argument("--note", required=True, help="Operator explanation. Does not grant authorization.")
    p_review.add_argument("-d", "--directory", help="Export archive directory")
    p_review.add_argument("--json", action="store_true")
    p_review.add_argument("--project", dest="projects", action="append", help="Exact cwd or project slug. Repeat for explicit aliases.")
    p_build = handoff_commands.add_parser("build", help="Keep required evidence or fail the coverage gate")
    p_build.add_argument("query")
    p_build.add_argument("--requirements", required=True, help="Local evidence requirements JSON")
    p_build.add_argument("-o", "--output", required=True, help="Private output bundle directory")
    p_build.add_argument("-d", "--directory", help="Export archive directory")
    p_build.add_argument("--last", type=positive_int, default=5)
    p_build.add_argument("--max-chars", type=positive_int, default=DEFAULT_MAX_CHARS)
    p_build.add_argument("--max-total-chars", type=positive_int, default=64_000, help="Maximum complete handoff characters (default: 64000)")
    p_build.add_argument("--json", action="store_true")
    p_build.add_argument("--project", dest="projects", action="append", help="Exact cwd or project slug. Repeat for explicit aliases.")
    p_audit = handoff_commands.add_parser("audit", help="Read-only check of retained anchors and source freshness")
    p_audit.add_argument("bundle")
    p_audit.add_argument("-d", "--directory", help="Current export archive directory")
    p_audit.add_argument("--json", action="store_true")

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

    p_restore = sub.add_parser("restore", help="Recover captured additions and exact-base updates into a new private directory")
    p_restore.add_argument("source", nargs="+", help="Ordered Codex JSONL files, or one directory for automatic discovery")
    p_restore.add_argument("--source-root", required=True, help="Existing or absent historical path root to retain")
    p_restore.add_argument("-o", "--output", required=True, help="New private output directory outside Git")
    p_restore.add_argument("--json", action="store_true")

    args = parser.parse_args()
    if args.command == "bulk" and args.since and args.until and args.since >= args.until:
        parser.error("--until must be after --since")

    commands = {
        "init": cmd_init, "topic": cmd_topic, "resume": cmd_resume,
        "skill": lambda args: print(continuation_skill(), end=''),
        "hook": cmd_hook, "export": cmd_export, "bulk": cmd_bulk,
        "search": cmd_search, "index": cmd_index, "stats": cmd_stats, "distill": cmd_distill,
        "link": cmd_link, "to-obsidian": cmd_to_obsidian, "report": cmd_report,
        "reconcile": cmd_reconcile, "handoff": cmd_handoff, "context": cmd_context,
        "family": cmd_family, "doctor": cmd_doctor,
        "install": cmd_install, "restore": cmd_restore,
    }
    if args.command not in commands:
        parser.print_help()
        return
    try:
        commands[args.command](args)
    except (StorageError, ValueError, OSError) as error:
        parser.exit(1, f"agent-sessions: {error}\n")


if __name__ == "__main__":
    main()
