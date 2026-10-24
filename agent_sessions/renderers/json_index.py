"""Render and maintain sessions.json — machine-readable session index."""

from __future__ import annotations

import json
from pathlib import Path

from agent_sessions.models import Agent, Session
from agent_sessions.storage import StorageError, InvalidIndexError, directory_lock, atomic_write_text, validate_session_id


class JsonIndexRenderer:

    @classmethod
    def session_to_dict(cls, session: Session) -> dict:
        return {
            "id": session.id,
            "agent": session.agent.value,
            "title": session.title,
            "summary": (session.summary or "")[:300],
            "branch": session.branch,
            "cwd": session.cwd,
            "model": session.model,
            "model_provider": session.model_provider,
            "project_slug": session.project_slug,
            "date": session.date_str,
            "date_source": session.date_source,
            "observed_at": session.observed_at.isoformat() if session.observed_at else None,
            "source_paths": session.source_paths or ([session.source_path] if session.source_path else []),
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "ended_at": session.ended_at.isoformat() if session.ended_at else None,
            "duration_seconds": session.duration_seconds,
            "duration_human": session.duration_human,
            "parent_id": session.parent_id,
            "message_count": session.message_count,
            "user_messages": session.user_message_count,
            "assistant_messages": session.assistant_message_count,
            "tokens": {
                "input": session.usage.input_tokens,
                "output": session.usage.output_tokens,
                "cache_read": session.usage.cache_read_tokens,
                "cache_write": session.usage.cache_write_tokens,
                "reasoning": session.usage.reasoning_tokens,
                "total": session.usage.total_tokens,
            },
            "file": f"{session.id}.md",
        }

    @classmethod
    def render_update(cls, session: Session, index_path: Path) -> str:
        """Prepare an update without writing or discarding invalid entries."""
        validate_session_id(session.id)
        entries: dict[str, dict] = {}
        if index_path.exists():
            try:
                data = json.loads(index_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    rows = data.get("sessions")
                    if data.get("version", 1) != 1 or not isinstance(rows, list):
                        raise ValueError("Unsupported index shape or version")
                    if "count" in data and (type(data["count"]) is not int or data["count"] != len(rows)):
                        raise ValueError("Inconsistent index count")
                elif isinstance(data, list):
                    rows = data
                else:
                    raise ValueError("Expected an index object or list")
                for row in rows:
                    if not isinstance(row, dict):
                        raise ValueError("Expected an index entry object")
                    sid = row.get("id")
                    if not isinstance(sid, str) or not sid or sid in entries:
                        raise ValueError("Missing or duplicate session ID")
                    validate_session_id(sid)
                    if row.get("agent") not in [agent.value for agent in Agent]:
                        raise ValueError("Unknown agent")
                    if "file" in row and row["file"] != f"{sid}.md":
                        raise ValueError("Invalid transcript reference")
                    for field in ("started_at", "date"):
                        if row.get(field) is not None and not isinstance(row[field], str):
                            raise ValueError("Invalid date field")
                    entries[sid] = row
            except (ValueError, UnicodeError, OSError, StorageError) as error:
                raise InvalidIndexError(
                    f"Cannot update invalid or unreadable JSON index at {index_path}. Run doctor before retrying."
                ) from error
        if session.id in entries and entries[session.id]["agent"] != session.agent.value:
            raise InvalidIndexError("Session ID belongs to another agent. Export to a separate directory.")
        entries[session.id] = cls.session_to_dict(session)
        sorted_entries = sorted(entries.values(), key=lambda e: e.get("started_at") or e.get("date") or "", reverse=True)
        return json.dumps({"version": 1, "count": len(sorted_entries), "sessions": sorted_entries},
                          indent=2, ensure_ascii=False) + "\n"

    @classmethod
    def update(cls, session: Session, index_path: Path) -> None:
        validate_session_id(session.id)
        with directory_lock(index_path.parent):
            atomic_write_text(index_path, cls.render_update(session, index_path))
