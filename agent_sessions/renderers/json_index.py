"""Render and maintain sessions.json — machine-readable session index."""

from __future__ import annotations

import json
from pathlib import Path

from agent_sessions.models import Session


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
    def update(cls, session: Session, index_path: Path) -> None:
        entries: dict[str, dict] = {}

        if index_path.exists():
            try:
                data = json.loads(index_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    entries = {e["id"]: e for e in data.get("sessions", []) if "id" in e}
                elif isinstance(data, list):
                    entries = {e["id"]: e for e in data if isinstance(e, dict) and "id" in e}
            except (json.JSONDecodeError, KeyError):
                pass

        entries[session.id] = cls.session_to_dict(session)

        sorted_entries = sorted(
            entries.values(),
            key=lambda e: e.get("started_at") or e.get("date") or "",
            reverse=True,
        )

        output = {
            "version": 1,
            "count": len(sorted_entries),
            "sessions": sorted_entries,
        }

        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(
            json.dumps(output, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
