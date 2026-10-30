"""Cited session-family digests from exported parent_id links.

This reads only an existing export archive. It does not discover native agent
stores, infer liveness, or certify that a quoted statement remains in force.
"""

from __future__ import annotations

import re
import json
from pathlib import Path

from agent_sessions.analysis.claims import claims_from_sections
from agent_sessions.analysis.transcript import conversation_sections
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.storage import validate_session_id

METHOD = "export_parent_id_v1"
DEFAULT_MAX_QUOTE_CHARS = 400
DEFAULT_MAX_SIGNALS = 8
DEFAULT_MAX_PIN_SUGGESTIONS = 12

SCOPE_CUE = re.compile(
    r"(?:^scope\s*:|\bdiscovery[ -]only\b|\bresearch[ -]only\b|\breview[ -]only\b|\bdo not\b|\bout of scope\s*:)",
    re.IGNORECASE,
)
SIGNAL_PRIORITY = {
    "scope_boundary": 120,
    "reported_blocker": 100,
    "open_question": 95,
    "next_action": 90,
    "decision_candidate": 80,
    "deferred": 75,
    "proposal": 60,
    "request": 55,
}
ALLOWED_SIGNAL_KINDS = tuple(sorted(SIGNAL_PRIORITY))
DEFAULT_PIN_SIGNAL_KINDS = ("scope_boundary", "reported_blocker", "open_question", "next_action")


def _edge_for(agent: str) -> str:
    return "spawned_from" if agent == "codex" else "forked_from"


def _clip(text: str, limit: int) -> tuple[str, bool]:
    text = text.strip()
    if len(text) <= limit:
        return text, False
    return text[: max(0, limit - 1)].rstrip() + "…", True


def _member_quotes(path: Path, max_quote_chars: int) -> tuple[str, list[dict]]:
    if not path.is_file() or path.is_symlink():
        return "missing", []
    try:
        sections = conversation_sections(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError):
        return "unreadable", []
    quotes = []
    first_user = next(((i, body) for i, (role, body) in enumerate(sections, 1) if role == "User"), None)
    last_assistant = next(
        ((i, body) for i, (role, body) in reversed(list(enumerate(sections, 1))) if role == "Assistant"),
        None,
    )
    for role, item in (("User", first_user), ("Assistant", last_assistant)):
        if item is None:
            continue
        section, body = item
        text, truncated = _clip(body, max_quote_chars)
        quotes.append(dict(role=role, section=section, text=text, truncated=truncated))
    return "available", quotes


def _signals(
    path: Path,
    sections: list[tuple[str, str]],
    agent: str,
    relation: str,
    max_signals: int,
    signal_kinds: set[str],
    min_signal_priority: int,
) -> list[dict]:
    if max_signals <= 0:
        return []
    claims = claims_from_sections(
        path,
        [(i, role, body) for i, (role, body) in enumerate(sections, 1)],
        agent,
    )
    found: list[dict] = []
    for claim in claims:
        kind = claim["kind"]
        quote = claim["text"].strip()
        section = claim["evidence"].get("conversation_section")
        if kind in SIGNAL_PRIORITY and kind in signal_kinds and SIGNAL_PRIORITY[kind] >= min_signal_priority:
            found.append(
                dict(
                    kind=kind,
                    priority=SIGNAL_PRIORITY[kind],
                    role=claim["evidence"]["role"],
                    section=section,
                    quote=quote,
                    relation=relation,
                )
            )
    # Scope boundaries are high-value carry-over constraints and deserve explicit detection.
    for i, (role, body) in enumerate(sections, 1):
        for line in body.splitlines():
            text = line.strip()
            if (not text or not SCOPE_CUE.search(text) or "scope_boundary" not in signal_kinds
                    or SIGNAL_PRIORITY["scope_boundary"] < min_signal_priority):
                continue
            found.append(
                dict(
                    kind="scope_boundary",
                    priority=SIGNAL_PRIORITY["scope_boundary"],
                    role=role.lower(),
                    section=i,
                    quote=text,
                    relation=relation,
                )
            )
    found.sort(key=lambda item: (item["priority"], item["section"] or 0), reverse=True)
    selected = []
    seen = set()
    for signal in found:
        key = (signal["kind"], signal["quote"].casefold())
        if key in seen:
            continue
        seen.add(key)
        selected.append(signal)
        if len(selected) >= max_signals:
            break
    return selected


def _family_summary(members: list[dict]) -> dict:
    signals = [signal for member in members for signal in member.get("signals", [])]
    unresolved_questions = [signal for signal in signals if signal["kind"] == "open_question"]
    blockers = [signal for signal in signals if signal["kind"] == "reported_blocker"]
    constraints = [signal for signal in signals if signal["kind"] == "scope_boundary"]
    next_actions = [signal for signal in signals if signal["kind"] == "next_action"]
    return dict(
        signal_count=len(signals),
        unresolved_questions=unresolved_questions,
        blockers=blockers,
        carryover_constraints=constraints,
        next_actions=next_actions,
        limits=(
            "Signals are heuristic text labels from cleaned dialogue and explicit scope cues. "
            "They are candidates for review, not verified obligations or task completion proof."
        ),
    )


def _pin_id(signal: dict, number: int) -> str:
    base = signal["kind"].replace("_", "-")
    relation = signal["relation"]
    return f"{relation}-{base}-{number}"


def _pin_suggestions(
    members: list[dict],
    max_pin_suggestions: int,
    *,
    pin_signal_kinds: set[str],
    focus_priority_bonus: int,
) -> list[dict]:
    if max_pin_suggestions <= 0:
        return []
    candidates = []
    for member in members:
        for signal in member.get("signals", []):
            if signal["kind"] not in pin_signal_kinds:
                continue
            candidates.append(
                dict(
                    session_id=member["session_id"],
                    section=signal["section"],
                    quote=signal["quote"],
                    kind=signal["kind"],
                    relation=signal["relation"],
                    priority=signal["priority"],
                )
            )
    candidates.sort(
        key=lambda item: (item["priority"] + (focus_priority_bonus if item["relation"] == "focus" else 0), item["priority"]),
        reverse=True,
    )
    output = []
    seen = set()
    for item in candidates:
        key = (item["session_id"], item["section"], item["quote"].casefold())
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
        if len(output) >= max_pin_suggestions:
            break
    for i, item in enumerate(output, 1):
        item["id"] = _pin_id(item, i)
        item["pin_command_template"] = (
            "agent-sessions handoff pin "
            f"--id {item['id']} "
            f"--session {item['session_id']} "
            f"--section {item['section']} "
            "--unit paragraph "
            f"--quote {json.dumps(item['quote'], ensure_ascii=False)} "
            "-d <archive> "
            "-o <requirements.json>"
        )
    return output


def _normalize_signal_kinds(kinds, *, default: tuple[str, ...] | None = None) -> set[str]:
    if kinds is None:
        return set(default if default is not None else ALLOWED_SIGNAL_KINDS)
    if not isinstance(kinds, (list, tuple, set)):
        raise ValueError("Signal kinds must be a list, tuple, or set.")
    normalized = {str(kind) for kind in kinds}
    unknown = sorted(normalized - set(ALLOWED_SIGNAL_KINDS))
    if unknown:
        raise ValueError("Unknown signal kind(s): " + ", ".join(unknown))
    return normalized


def evaluate_required_signals(report: dict, required_kinds) -> dict:
    """Report whether required signal kinds appear anywhere in the family."""
    required = _normalize_signal_kinds(required_kinds, default=())
    present = {
        signal["kind"]
        for member in report.get("members", [])
        for signal in member.get("signals", [])
    }
    missing = sorted(required - present)
    return dict(
        required=sorted(required),
        present=sorted(present & required),
        missing=missing,
        passed=not missing,
        verification="not_checked",
        limits=(
            "Required-signal checks look only at extracted family signals. "
            "A pass does not prove completeness, correctness, or readiness."
        ),
    )


def materialize_pin_suggestions(
    directory: Path,
    report: dict,
    output: Path,
    *,
    overwrite: bool = False,
) -> dict:
    """Write a dialogue requirements contract from family pin suggestions."""
    suggestions = report.get("pin_suggestions") or []
    if not suggestions:
        raise ValueError("Family digest has no pin suggestions to materialize.")
    output = Path(output)
    if output.exists():
        if output.is_symlink() or not output.is_file():
            raise ValueError("Requirements destination must be a regular file path.")
        if not overwrite:
            raise ValueError("Requirements destination exists. Use overwrite to replace it.")
        output.unlink()
    from agent_sessions.analysis.continuity import pin_requirement, load_requirements

    for suggestion in suggestions:
        pin_requirement(
            directory,
            output,
            suggestion["id"],
            suggestion["session_id"],
            suggestion["section"],
            suggestion["quote"],
            unit="paragraph",
            view="dialogue",
        )
    contract = load_requirements(output)
    return dict(
        path=str(output),
        pins_written=len(contract["requirements"]),
        source_suggestions=len(suggestions),
        verification="not_checked",
        limits=(
            "Generated pins are exact historical anchors from family suggestions. "
            "They do not establish correctness, acceptance, or task completion."
        ),
    )


def _walk_ancestors(rows: dict[str, dict], session_id: str) -> list[tuple[str, int]]:
    chain = []
    seen = {session_id}
    current = rows[session_id].get("parent_id")
    depth = -1
    while isinstance(current, str) and current:
        if current in seen:
            break
        seen.add(current)
        chain.append((current, depth))
        if current not in rows:
            break
        current = rows[current].get("parent_id")
        depth -= 1
    return chain


def _walk_descendants(rows: dict[str, dict], session_id: str) -> list[tuple[str, int]]:
    children: dict[str, list[str]] = {}
    for sid, row in rows.items():
        parent = row.get("parent_id")
        if isinstance(parent, str) and parent:
            children.setdefault(parent, []).append(sid)
    found: list[tuple[str, int]] = []
    stack = [(child, 1) for child in sorted(children.get(session_id, []))]
    seen = {session_id}
    while stack:
        sid, depth = stack.pop(0)
        if sid in seen:
            continue
        seen.add(sid)
        found.append((sid, depth))
        for child in sorted(children.get(sid, [])):
            stack.append((child, depth + 1))
    return found


def build_family_digest(
    directory: Path,
    session_id: str,
    *,
    max_quote_chars: int = DEFAULT_MAX_QUOTE_CHARS,
    max_signals: int = DEFAULT_MAX_SIGNALS,
    max_pin_suggestions: int = DEFAULT_MAX_PIN_SUGGESTIONS,
    signal_kinds: list[str] | tuple[str, ...] | None = None,
    pin_signal_kinds: list[str] | tuple[str, ...] | None = None,
    focus_priority_bonus: int = 15,
    min_signal_priority: int = 0,
) -> dict:
    """Return a lineage digest with cited first-user and last-assistant quotes."""
    validate_session_id(session_id)
    if type(max_quote_chars) is not int or max_quote_chars < 40:
        raise ValueError("max_quote_chars must be an integer of at least 40.")
    if type(max_signals) is not int or max_signals < 0:
        raise ValueError("max_signals must be a nonnegative integer.")
    if type(max_pin_suggestions) is not int or max_pin_suggestions < 0:
        raise ValueError("max_pin_suggestions must be a nonnegative integer.")
    if type(focus_priority_bonus) is not int or focus_priority_bonus < 0:
        raise ValueError("focus_priority_bonus must be a nonnegative integer.")
    if type(min_signal_priority) is not int or min_signal_priority < 0:
        raise ValueError("min_signal_priority must be a nonnegative integer.")
    selected_signal_kinds = _normalize_signal_kinds(signal_kinds)
    selected_pin_signal_kinds = _normalize_signal_kinds(
        pin_signal_kinds,
        default=DEFAULT_PIN_SIGNAL_KINDS,
    )
    index_path = directory / "sessions.json"
    if not index_path.is_file():
        raise ValueError("Family digest needs an existing archive index.")
    rows = JsonIndexRenderer.read_entries(index_path)
    if session_id not in rows:
        raise ValueError(f"Session {session_id!r} is not in the archive index.")

    ordered: list[tuple[str, str, int]] = []
    for sid, depth in reversed(_walk_ancestors(rows, session_id)):
        ordered.append((sid, "ancestor", depth))
    ordered.append((session_id, "focus", 0))
    for sid, depth in _walk_descendants(rows, session_id):
        ordered.append((sid, "descendant", depth))

    members = []
    missing_parents = []
    for sid, relation, depth in ordered:
        row = rows.get(sid)
        if row is None:
            missing_parents.append(sid)
            members.append(dict(
                session_id=sid,
                agent=None,
                title=None,
                relation=relation,
                parent_id=None,
                edge=None,
                depth=depth,
                quotes=[],
                transcript="missing_index",
            ))
            continue
        parent_id = row.get("parent_id") if isinstance(row.get("parent_id"), str) else None
        if parent_id and parent_id not in rows and parent_id not in missing_parents:
            missing_parents.append(parent_id)
        source_path = directory / f"{sid}.md"
        status, quotes = _member_quotes(source_path, max_quote_chars)
        try:
            sections = conversation_sections(source_path.read_text(encoding="utf-8")) if status == "available" else []
        except (OSError, UnicodeError):
            sections = []
        agent = row.get("agent")
        members.append(dict(
            session_id=sid,
            agent=agent,
            title=row.get("title") or "",
            relation=relation,
            parent_id=parent_id,
            edge=_edge_for(agent) if parent_id else None,
            depth=depth,
            cwd=row.get("cwd") or "",
            branch=row.get("branch") or "",
            date=row.get("date") or row.get("started_at") or "",
            quotes=quotes,
            signals=_signals(
                source_path,
                sections,
                agent or "unknown",
                relation,
                max_signals,
                selected_signal_kinds,
                min_signal_priority,
            ),
            transcript=status,
        ))

    pin_suggestions = _pin_suggestions(
        members,
        max_pin_suggestions,
        pin_signal_kinds=selected_pin_signal_kinds,
        focus_priority_bonus=focus_priority_bonus,
    )
    return dict(
        method=METHOD,
        focus=session_id,
        member_count=len(members),
        members=members,
        missing_parents=missing_parents,
        family_summary=_family_summary(members),
        pin_suggestions=pin_suggestions,
        signal_policy=dict(
            signal_kinds=sorted(selected_signal_kinds),
            pin_signal_kinds=sorted(selected_pin_signal_kinds),
            focus_priority_bonus=focus_priority_bonus,
            min_signal_priority=min_signal_priority,
        ),
        verification="not_checked",
        limits=(
            "Digest uses exported sessions.json parent_id links and cleaned dialogue "
            "quotes only. Missing native stores, deleted parents, and unbroken cycles "
            "are reported without repair. Quotes are historical evidence, not current "
            "authorization or verified outcomes."
        ),
    )


def render_family_digest(report: dict) -> str:
    """Render a human-readable Markdown digest."""
    lines = [
        f"# Session family: {report['focus']}",
        "",
        f"Method: `{report['method']}` · Members: {report['member_count']} · "
        f"Verification: `{report['verification']}`",
        "",
    ]
    if report.get("missing_parents"):
        lines.append("Missing parent indexes: " + ", ".join(f"`{sid}`" for sid in report["missing_parents"]))
        lines.append("")
    for member in report["members"]:
        title = member.get("title") or "(untitled)"
        agent = member.get("agent") or "unknown"
        lines.append(f"## {member['relation']} · `{member['session_id']}` ({agent})")
        lines.append("")
        lines.append(f"- Title: {title}")
        lines.append(f"- Depth: {member['depth']}")
        if member.get("parent_id"):
            lines.append(f"- Parent: `{member['parent_id']}` ({member.get('edge') or 'parent_id'})")
        if member.get("cwd"):
            lines.append(f"- cwd: `{member['cwd']}`")
        if member.get("branch"):
            lines.append(f"- Branch: `{member['branch']}`")
        if member.get("date"):
            lines.append(f"- Date: {member['date']}")
        lines.append(f"- Transcript: `{member['transcript']}`")
        lines.append("")
        signals = member.get("signals", [])
        if signals:
            lines.append("### Continuation signals")
            lines.append("")
            for signal in signals:
                lines.append(
                    f"- `{signal['kind']}` ({signal['role']}, section {signal['section']}): {signal['quote']}"
                )
            lines.append("")
        if not member["quotes"]:
            lines.append("_No cleaned user/assistant quotes available._")
            lines.append("")
            continue
        for quote in member["quotes"]:
            marker = " (truncated)" if quote.get("truncated") else ""
            lines.append(f"### {quote['role']} · section {quote['section']}{marker}")
            lines.append("")
            lines.append("```text")
            lines.append(quote["text"])
            lines.append("```")
            lines.append("")
    summary = report.get("family_summary") or {}
    if summary:
        lines.append("## Family summary")
        lines.append("")
        lines.append(f"- Signal candidates: {summary.get('signal_count', 0)}")
        lines.append(f"- Open questions: {len(summary.get('unresolved_questions', []))}")
        lines.append(f"- Blockers: {len(summary.get('blockers', []))}")
        lines.append(f"- Carry-over constraints: {len(summary.get('carryover_constraints', []))}")
        lines.append(f"- Next actions: {len(summary.get('next_actions', []))}")
        lines.append("")
        if summary.get("carryover_constraints"):
            lines.append("### Carry-over constraints")
            lines.append("")
            for signal in summary["carryover_constraints"][:5]:
                lines.append(
                    f"- `{signal['relation']}` `{signal['kind']}` (section {signal['section']}): {signal['quote']}"
                )
            lines.append("")
        if summary.get("unresolved_questions"):
            lines.append("### Open questions")
            lines.append("")
            for signal in summary["unresolved_questions"][:5]:
                lines.append(
                    f"- `{signal['relation']}` (section {signal['section']}): {signal['quote']}"
                )
            lines.append("")
        lines.append(summary.get("limits", ""))
        lines.append("")
    lines.append("## Limits")
    lines.append("")
    lines.append(report.get("limits", ""))
    pin_suggestions = report.get("pin_suggestions") or []
    if pin_suggestions:
        lines.append("")
        lines.append("## Suggested pins")
        lines.append("")
        lines.append("Use these as starting anchors with `agent-sessions handoff pin`.")
        lines.append("")
        for item in pin_suggestions:
            lines.append(
                f"- `{item['id']}` · `{item['kind']}` · `{item['session_id']}` section {item['section']}: {item['quote']}"
            )
            lines.append(f"  - Template: `{item['pin_command_template']}`")
    lines.append("")
    return "\n".join(lines)
