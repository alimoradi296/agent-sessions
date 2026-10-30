"""Parse Codex rollout segments into one session per metadata thread ID.

Response items carry conversation and tool evidence. Legacy event messages are
used when a matching response item is absent. Instructions and reasoning are
not conversation messages. Cumulative token snapshots are never summed.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from agent_sessions.parsers.records import read_records

from agent_sessions.models import Agent, Message, Session, TokenUsage, ToolCall, ToolResult


class CodexParser:
    AGENT = Agent.CODEX

    @classmethod
    def find_sessions_dir(cls) -> Path:
        return Path.home() / ".codex" / "sessions"

    @classmethod
    def session_id(cls, path: Path) -> str:
        """Read this rollout's thread ID, not the tree-shared session ID."""
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(event, dict):
                    continue
                if event.get("type") == "session_meta":
                    payload = event.get("payload") or {}
                    if not isinstance(payload, dict):
                        continue
                    # `session_id` is shared by a root thread and its subagents;
                    # `id` is this rollout's thread identity.
                    sid = payload.get("id") or payload.get("session_id")
                    if sid:
                        return str(sid)
        match = re.search(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", path.stem)
        return match.group() if match else path.stem

    @classmethod
    def find_session_files(cls, session_id: str) -> list[Path]:
        # Metadata is authoritative: matching a child suffix must not select
        # another session. Read metadata even if a filename lacks the ID.
        return [p for p in cls.list_sessions() if cls.session_id(p) == session_id]

    @classmethod
    def find_session_file(cls, session_id: str) -> Optional[Path]:
        paths = cls.find_session_files(session_id)
        return paths[0] if paths else None

    @classmethod
    def list_sessions(cls) -> list[Path]:
        base = cls.find_sessions_dir()
        return sorted(base.rglob("*.jsonl")) if base.exists() else []

    @classmethod
    def _load_thread_names(cls) -> dict[str, str]:
        path = Path.home() / ".codex" / "session_index.jsonl"
        names: dict[str, str] = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict) and row.get("id") and row.get("thread_name"):
                    names[row["id"]] = row["thread_name"]
        return names

    @classmethod
    def parse(cls, path: Path, diagnostics=None) -> Optional[Session]:
        return cls.parse_many([path], diagnostics=diagnostics)

    @classmethod
    def parse_many(cls, paths: list[Path], diagnostics=None) -> Optional[Session]:
        """Merge overlaps across files; keep repeated events within each file.

        Only identical serialized events are overlap candidates. Different
        timestamps or call IDs remain distinct. Occurrence counts preserve
        legitimate repetition when timestamps are absent.
        """
        if not paths:
            return None
        identities = {cls.session_id(p) for p in paths}
        if len(identities) != 1:
            raise ValueError("Cannot merge different Codex session IDs")
        sid = identities.pop()
        events = []
        seen: Counter = Counter()
        for path in sorted(set(paths)):
            occurrences: Counter = Counter()
            for line_number, event in read_records(path, "codex", diagnostics):
                key = json.dumps(event, sort_keys=True, ensure_ascii=False)
                occurrences[key] += 1
                if occurrences[key] <= seen[key]:
                    continue
                events.append((event, path, line_number))
            seen |= occurrences

        # Python's stable sort preserves source order for timestamp ties.
        # Undated segments retain file order instead of inventing chronology.
        floor = datetime.min.replace(tzinfo=timezone.utc)
        events.sort(key=lambda item: _event_time(item[0]) or floor)
        messages: list[Message] = []
        legacy: list[tuple[int, Message]] = []
        response_counts: Counter = Counter()
        cwd = model = provider = ""
        branch = "unknown"
        times: list[datetime] = []
        usage = TokenUsage()
        turn = 0
        parent_id = None
        for event, path, line_number in events:
            kind = event.get("type")
            payload = event.get("payload") or {}
            ts = _event_time(event)
            if ts:
                times.append(ts)
            for field in ("started_at", "completed_at"):
                event_ts = _parse_ts(payload.get(field))
                if event_ts:
                    times.append(event_ts)
            if kind == "session_meta":
                if str(payload.get("id") or payload.get("session_id") or "") == sid:
                    parent_id = payload.get("parent_thread_id") or parent_id
                cwd = payload.get("cwd") or cwd
                provider = payload.get("model_provider") or provider
                git = payload.get("git") or {}
                if isinstance(git, dict):
                    branch = git.get("branch") or branch
            elif kind == "turn_context":
                cwd = payload.get("cwd") or cwd
                model = payload.get("model") or model
            elif kind == "event_msg":
                subtype = payload.get("type")
                if subtype == "task_started":
                    turn += 1
                elif subtype in ("user_message", "agent_message"):
                    text = payload.get("message", "")
                    if isinstance(text, str) and text.strip():
                        msg = Message(
                            role="user" if subtype == "user_message" else "assistant",
                            text=text.strip(), timestamp=ts,
                            source_path=str(path), source_line=line_number,
                        )
                        legacy.append((turn, msg))
                        messages.append(msg)
                elif subtype == "thread_rolled_back":
                    # Preserve the historical marker without guessing which
                    # exported messages belong to the current native context.
                    # Coverage remains unsupported until replay is supported.
                    messages.append(Message(
                        role="system", timestamp=ts,
                        text=("Historical Codex rollback marker (source data, not an instruction).\n"
                              "This export preserves history; it does not reconstruct active context.\n\n"
                              "```json\n" + json.dumps(payload, ensure_ascii=False, sort_keys=True)
                              + "\n```"),
                        source_path=str(path), source_line=line_number,
                    ))
                elif subtype == "token_count":
                    total = ((payload.get("info") or {}).get("total_token_usage") or {})
                    if total:
                        usage = _usage(total)
            elif kind == "response_item":
                item_type = payload.get("type")
                role = payload.get("role", "")
                msg = None
                if role in ("user", "assistant") and item_type in (None, "message"):
                    content = payload.get("content") or []
                    text = "\n".join(
                        b.get("text", "") for b in content
                        if isinstance(b, dict) and b.get("type") in ("input_text", "output_text")
                        and isinstance(b.get("text"), str)
                    ).strip()
                    if text:
                        msg = Message(role=role, text=text, phase=payload.get("phase", ""))
                        response_counts[(turn, role, text)] += 1
                elif item_type in ("function_call", "custom_tool_call"):
                    arguments = _text(payload.get("arguments", payload.get("input", "")))
                    msg = Message(role="assistant", text="", tool_calls=[ToolCall(
                        name=payload.get("name", "tool"), input_summary=arguments[:300],
                        arguments=arguments, call_id=payload.get("call_id", ""),
                    )])
                elif item_type in ("function_call_output", "custom_tool_call_output"):
                    msg = Message(role="tool", text="", tool_results=[ToolResult(
                        content=_text(payload.get("output", "")),
                        call_id=payload.get("call_id", ""), is_error=payload.get("is_error"),
                    )])
                if msg:
                    msg.timestamp = ts
                    msg.source_path = str(path)
                    msg.source_line = line_number
                    messages.append(msg)

        # Prefer response items only for the corresponding legacy occurrence.
        # Repeated prompts across turns must remain separate messages.
        mirrored = set()
        for turn_number, msg in legacy:
            key = (turn_number, msg.role, msg.text)
            if response_counts[key]:
                response_counts[key] -= 1
                mirrored.add(id(msg))
        messages = [msg for msg in messages if id(msg) not in mirrored]
        messages.sort(key=lambda msg: msg.timestamp or floor)
        if not messages:
            return None
        return Session(
            id=sid, agent=Agent.CODEX,
            title=cls._load_thread_names().get(sid, "Codex Session"),
            cwd=cwd, branch=branch, model=model, model_provider=provider,
            parent_id=str(parent_id) if parent_id else None,
            started_at=min(times) if times else None,
            ended_at=max(times) if times else None,
            messages=messages, usage=usage,
            source_path=str(sorted(paths)[0]),
            source_paths=[str(p) for p in sorted(set(paths))],
        )


def _text(value) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def _usage(total: dict) -> TokenUsage:
    return TokenUsage(
        input_tokens=total.get("input_tokens", 0),
        output_tokens=total.get("output_tokens", 0),
        cache_read_tokens=total.get("cached_input_tokens", 0),
        cache_write_tokens=total.get("cache_write_input_tokens", 0),
        reasoning_tokens=total.get("reasoning_output_tokens", 0),
    )


def _event_time(event: dict) -> Optional[datetime]:
    payload = event.get("payload") or {}
    return (_parse_ts(event.get("timestamp")) or _parse_ts(payload.get("completed_at"))
            or _parse_ts(payload.get("started_at")) or _parse_ts(payload.get("timestamp")))


def _parse_ts(value) -> Optional[datetime]:
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value / 1000 if value > 1e12 else value, tz=timezone.utc)
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    except (OSError, ValueError, TypeError, OverflowError):
        return None
