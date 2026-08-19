"""Render and maintain SESSION_INDEX.md — one searchable line per session."""

from __future__ import annotations

from pathlib import Path

from agent_sessions.models import Session

HEADER = """\
# Session Index

Searchable one-line-per-session log. Newest first.

| ID | Agent | Date | Branch | Duration | Messages | Summary | File |
|---|---|---|---|---|---|---|---|
"""


class IndexRenderer:

    @classmethod
    def make_entry(cls, session: Session) -> str:
        summary = (session.summary or session.title)[:160].rstrip()
        parent = f" ← `{session.parent_id[:8]}…`" if session.parent_id else ""
        msg_count = f"{session.user_message_count}u/{session.assistant_message_count}a"

        return (
            f"| `{session.id[:8]}…` "
            f"| {session.agent.value} "
            f"| {session.date_str} "
            f"| `{session.branch}` "
            f"| {session.duration_human} "
            f"| {msg_count} "
            f"| {summary}{parent} "
            f"| [{session.id}.md]({session.id}.md) |"
        )

    @classmethod
    def update(cls, session: Session, index_path: Path) -> None:
        new_entry = cls.make_entry(session)
        short_id = session.id[:8]

        if index_path.exists():
            existing = index_path.read_text(encoding="utf-8")
            lines = [l for l in existing.splitlines() if short_id not in l]
            try:
                sep_idx = next(i for i, l in enumerate(lines) if l.startswith("|---"))
                lines.insert(sep_idx + 1, new_entry)
                index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            except StopIteration:
                index_path.write_text(HEADER + new_entry + "\n", encoding="utf-8")
        else:
            index_path.parent.mkdir(parents=True, exist_ok=True)
            index_path.write_text(HEADER + new_entry + "\n", encoding="utf-8")
