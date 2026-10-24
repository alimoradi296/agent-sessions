"""Render and maintain SESSION_INDEX.md — one searchable line per session."""

from __future__ import annotations

import re
from pathlib import Path

from agent_sessions.models import Session
from agent_sessions.storage import InvalidIndexError, directory_lock, atomic_write_text, validate_session_id

HEADER = """\
# Session Index

Searchable one-line-per-session log. Newest first.

| ID | Agent | Date | Branch | Duration | Messages | Summary | File |
|---|---|---|---|---|---|---|---|
"""


class IndexRenderer:

    @classmethod
    def make_entry(cls, session: Session) -> str:
        summary = _cell(session.summary or session.title)[:160].rstrip()
        parent = f" ← `{session.parent_id[:8]}…`" if session.parent_id else ""
        msg_count = f"{session.user_message_count}u/{session.assistant_message_count}a"

        return (
            f"| `{session.id[:8]}…` "
            f"| {session.agent.value} "
            f"| {session.date_str}{' (file mtime)' if session.date_source == 'file_mtime' else ''} "
            f"| `{_cell(session.branch)}` "
            f"| {session.duration_human} "
            f"| {msg_count} "
            f"| {summary}{parent} "
            f"| [{session.id}.md]({session.id}.md) |"
        )

    @classmethod
    def read_entries(cls, index_path: Path) -> tuple[list[str], dict[str, str]]:
        """Read and validate the table, preserving its header and row order."""
        if not index_path.exists():
            return HEADER.splitlines(), {}
        try:
            lines = index_path.read_text(encoding="utf-8").splitlines()
            sep_idx = next(i for i, line in enumerate(lines) if line.startswith("|---"))
            if not any(line.startswith("| ID | Agent |") for line in lines[:sep_idx]):
                raise ValueError("Missing index table header")
            entries = {}
            for line in lines[sep_idx + 1:]:
                if not line.strip():
                    continue
                match = re.search(r"\| \[([\w-]+)\.md\]\(\1\.md\) \|$", line)
                if not match or not line.startswith("| ") or match[1] in entries:
                    raise ValueError("Malformed or duplicate index row")
                entries[match[1]] = line
            return lines[:sep_idx + 1], entries
        except (OSError, UnicodeError, ValueError, StopIteration) as error:
            raise InvalidIndexError(
                f"Cannot update invalid or unreadable Markdown index at {index_path}. Run doctor before retrying."
            ) from error

    @classmethod
    def render_update(cls, session: Session, index_path: Path) -> str:
        validate_session_id(session.id)
        header, entries = cls.read_entries(index_path)
        entries.pop(session.id, None)
        return "\n".join(header + [cls.make_entry(session)] + list(entries.values())) + "\n"

    @classmethod
    def update(cls, session: Session, index_path: Path) -> None:
        validate_session_id(session.id)
        with directory_lock(index_path.parent):
            atomic_write_text(index_path, cls.render_update(session, index_path))


def _cell(text: str) -> str:
    return " ".join(text.split()).replace("|", "&#124;")
