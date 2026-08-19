"""Parser for OpenAI Codex CLI JSONL transcripts.

Location: ~/.codex/sessions/YYYY/MM/DD/rollout-<datetime>-<session_id>.jsonl
Index:    ~/.codex/session_index.jsonl (thread_name per session)

Event types (payload.type):
  session_meta    — cwd, model_provider, cli_version, session_id
  task_started    — turn start (started_at timestamp)
  turn_aborted / turn_completed — turn end (duration_ms)
  user_message    — user text
  agent_message   — assistant text
  token_count     — cumulative token usage (info.total_token_usage)
  response_item   — role + content blocks (input_text, output_text)
  thread_settings_applied — config events (skipped)
  world_state     — sandbox state (skipped)
  turn_context    — cwd, workspace_roots at turn time
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from agent_sessions.models import (
    Agent,
    Message,
    Session,
    TokenUsage,
    ToolCall,
    ToolResult,
)

logger = logging.getLogger(__name__)


class CodexParser:
    AGENT = Agent.CODEX

    @classmethod
    def find_sessions_dir(cls) -> Path:
        return Path.home() / ".codex" / "sessions"

    @classmethod
    def find_session_file(cls, session_id: str) -> Optional[Path]:
        base = cls.find_sessions_dir()
        if not base.exists():
            return None
        for path in base.rglob(f"*{session_id}*.jsonl"):
            return path
        return None

    @classmethod
    def list_sessions(cls) -> list[Path]:
        base = cls.find_sessions_dir()
        if not base.exists():
            return []
        return sorted(base.rglob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)

    @classmethod
    def _load_thread_names(cls) -> dict[str, str]:
        """Load session_id -> thread_name from the codex session index."""
        idx_path = Path.home() / ".codex" / "session_index.jsonl"
        names: dict[str, str] = {}
        if not idx_path.exists():
            return names
        with open(idx_path) as f:
            for line in f:
                try:
                    d = json.loads(line.strip())
                    sid = d.get("id", "")
                    name = d.get("thread_name", "")
                    if sid and name:
                        names[sid] = name
                except json.JSONDecodeError:
                    continue
        return names

    @classmethod
    def parse(cls, path: Path) -> Optional[Session]:
        thread_names = cls._load_thread_names()

        messages: list[Message] = []
        session_id = ""
        cwd = ""
        model_provider = ""
        title = "Codex Session"
        first_ts: Optional[datetime] = None
        last_ts: Optional[datetime] = None
        total_usage = TokenUsage()
        last_usage = TokenUsage()

        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue

                event_type = d.get("type")
                payload = d.get("payload", {})

                if event_type == "session_meta":
                    session_id = payload.get("session_id") or payload.get("id", "")
                    cwd = payload.get("cwd", "")
                    model_provider = payload.get("model_provider", "")
                    ts = _parse_ts(payload.get("timestamp"))
                    if ts and first_ts is None:
                        first_ts = ts

                elif event_type == "event_msg":
                    sub = payload.get("type", "")

                    if sub == "task_started":
                        ts = _parse_ts(payload.get("started_at"))
                        if ts:
                            if first_ts is None:
                                first_ts = ts
                            last_ts = ts

                    elif sub in ("turn_completed", "turn_aborted"):
                        ts = _parse_ts(payload.get("completed_at"))
                        if ts:
                            last_ts = ts

                    elif sub == "user_message":
                        text = payload.get("message", "").strip()
                        if text:
                            messages.append(Message(role="user", text=text))

                    elif sub == "agent_message":
                        text = payload.get("message", "").strip()
                        if text:
                            messages.append(Message(role="assistant", text=text))

                    elif sub == "token_count":
                        info = payload.get("info") or {}
                        total = info.get("total_token_usage") or {}
                        if total:
                            last_usage = TokenUsage(
                                input_tokens=total.get("input_tokens", 0),
                                output_tokens=total.get("output_tokens", 0),
                                cache_read_tokens=total.get("cached_input_tokens", 0),
                                cache_write_tokens=total.get("cache_write_input_tokens", 0),
                                reasoning_tokens=total.get("reasoning_output_tokens", 0),
                            )

                elif event_type == "response_item":
                    role = payload.get("role", "")
                    content = payload.get("content", [])
                    if role in ("user", "assistant") and isinstance(content, list):
                        texts = []
                        for block in content:
                            if not isinstance(block, dict):
                                continue
                            bt = block.get("type", "")
                            if bt in ("input_text", "output_text"):
                                texts.append(block.get("text", ""))
                        text = "\n".join(t for t in texts if t).strip()
                        if text and role == "user":
                            messages.append(Message(role="user", text=text))
                        elif text and role == "assistant":
                            messages.append(Message(role="assistant", text=text))

                elif event_type == "turn_context":
                    if not cwd:
                        cwd = payload.get("cwd", "")

        if not session_id:
            # Extract from filename: rollout-<datetime>-<uuid>.jsonl
            stem = path.stem
            parts = stem.split("-", 3)
            if len(parts) >= 4:
                session_id = parts[3]
            else:
                session_id = stem

        if session_id in thread_names:
            title = thread_names[session_id]

        # Use last cumulative usage snapshot
        total_usage = last_usage

        if not messages:
            return None

        return Session(
            id=session_id,
            agent=Agent.CODEX,
            title=title,
            branch="unknown",
            cwd=cwd,
            model=model_provider,
            started_at=first_ts,
            ended_at=last_ts,
            messages=messages,
            usage=total_usage,
            source_path=str(path),
        )


def _parse_ts(value) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, (int, float)):
        try:
            if value > 1e12:
                value = value / 1000
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except (OSError, ValueError):
            return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
