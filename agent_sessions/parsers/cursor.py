"""Parser for Cursor IDE agent transcript JSONL files.

Location: ~/.cursor/projects/<slug>/agent-transcripts/<id>/<id>.jsonl

Event structure is minimal compared to Claude/Codex:
  {"role": "user"|"assistant", "message": {"content": [...]}}
  {"type": "turn_ended", "status": "success"|"aborted", "error": "..."}

No built-in title, summary, branch, usage, or timestamp fields.
Title is inferred from the first user message.
"""

from __future__ import annotations

import json
import logging
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


class CursorParser:
    AGENT = Agent.CURSOR

    @classmethod
    def find_sessions_dir(cls) -> Path:
        return Path.home() / ".cursor" / "projects"

    @classmethod
    def find_session_file(cls, session_id: str) -> Optional[Path]:
        base = cls.find_sessions_dir()
        if not base.exists():
            return None
        expected = base / "**" / "agent-transcripts" / session_id / f"{session_id}.jsonl"
        for path in base.rglob(f"agent-transcripts/{session_id}/{session_id}.jsonl"):
            return path
        return None

    @classmethod
    def list_sessions(cls, project_slug: Optional[str] = None) -> list[Path]:
        base = cls.find_sessions_dir()
        if not base.exists():
            return []
        if project_slug:
            target = base / project_slug / "agent-transcripts"
            if not target.exists():
                return []
            paths = []
            for d in target.iterdir():
                if d.is_dir():
                    jsonl = d / f"{d.name}.jsonl"
                    if jsonl.exists():
                        paths.append(jsonl)
            return sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True)

        paths = []
        for jsonl in base.rglob("agent-transcripts/*/*.jsonl"):
            paths.append(jsonl)
        return sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True)

    @classmethod
    def parse(cls, path: Path) -> Optional[Session]:
        session_id = path.stem
        messages: list[Message] = []
        title = "Cursor Session"
        first_user_text: Optional[str] = None
        aborted = False

        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue

                role = d.get("role")
                event_type = d.get("type")

                if role in ("user", "assistant"):
                    text, tools, results = _extract_content(d.get("message", {}).get("content", ""))
                    if not text and not tools:
                        continue

                    if role == "user" and first_user_text is None and text:
                        first_user_text = text

                    messages.append(Message(
                        role=role,
                        text=text,
                        tool_calls=tools,
                        tool_results=results,
                    ))

                elif event_type == "turn_ended":
                    if d.get("status") == "aborted":
                        aborted = True

        if not messages:
            return None

        if first_user_text:
            lines = first_user_text.split("\n")
            title = "Cursor Session"
            for ln in lines:
                ln = ln.strip()
                if not ln:
                    continue
                if ln.startswith(("<", "```", "#", "---", "Read ", "//", "/*")):
                    continue
                if ln.startswith("Implement ") or ln.startswith("Fix ") or ln.startswith("Add "):
                    title = ln[:120]
                    break
                if len(ln) > 10 and not ln.startswith("-"):
                    title = ln[:120]
                    break

        cwd = ""
        parts = path.parts
        try:
            proj_idx = parts.index("projects")
            slug = parts[proj_idx + 1]
            cwd = "/" + slug.replace("-", "/")
        except (ValueError, IndexError):
            pass

        stat = path.stat()
        from datetime import datetime, timezone
        ended_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)

        return Session(
            id=session_id,
            agent=Agent.CURSOR,
            title=title,
            cwd=cwd,
            ended_at=ended_at,
            messages=messages,
            source_path=str(path),
        )


def _extract_content(content) -> tuple[str, list[ToolCall], list[ToolResult]]:
    if isinstance(content, str):
        return content, [], []

    if not isinstance(content, list):
        return "", [], []

    text_parts: list[str] = []
    tools: list[ToolCall] = []
    results: list[ToolResult] = []

    for block in content:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "text":
            text_parts.append(block.get("text", ""))
        elif btype == "tool_use":
            name = block.get("name", "tool")
            inp = json.dumps(block.get("input", {}), ensure_ascii=False)[:300]
            tools.append(ToolCall(name=name, input_summary=inp))
        elif btype == "tool_result":
            rc = block.get("content", "")
            if isinstance(rc, list):
                rc = " ".join(c.get("text", "") for c in rc if isinstance(c, dict))
            results.append(ToolResult(content=str(rc)[:500]))

    return "\n".join(p for p in text_parts if p), tools, results
