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
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from agent_sessions.parsers.records import read_records

from agent_sessions.models import (
    Agent,
    Message,
    Session,
    ToolCall,
    ToolResult,
)

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
        for path in cls.list_sessions():
            if path.stem == session_id:
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
        for project in base.iterdir():
            target = project / "agent-transcripts"
            if target.is_dir():
                paths.extend(p for p in target.glob("*/*.jsonl") if p.parent.name == p.stem)
        return sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True)

    @classmethod
    def parse(cls, path: Path, diagnostics=None) -> Optional[Session]:
        session_id = path.stem
        messages: list[Message] = []
        title = "Cursor Session"
        first_user_text: Optional[str] = None
        aborted = False

        for line_number, d in read_records(path, "cursor", diagnostics):
            role = d.get("role")
            event_type = d.get("type")

            if role in ("user", "assistant"):
                message = d.get("message") or {}
                text, tools, results = _extract_content(message.get("content", "") if isinstance(message, dict) else "")
                if not text and not tools and not results:
                    continue

                if role == "user" and first_user_text is None and text:
                    first_user_text = text

                if text or tools:
                    messages.append(Message(
                        role=role, text=text, tool_calls=tools,
                        source_path=str(path), source_line=line_number,
                    ))
                if results:
                    messages.append(Message(
                        role="tool", text="", tool_results=results,
                        source_path=str(path), source_line=line_number,
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

        slug = ""
        parts = path.parts
        try:
            proj_idx = parts.index("projects")
            slug = parts[proj_idx + 1]
        except (ValueError, IndexError):
            pass

        stat = path.stat()
        observed_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)

        return Session(
            id=session_id,
            agent=Agent.CURSOR,
            title=title,
            project_slug=slug,
            observed_at=observed_at,
            messages=messages,
            source_path=str(path),
            source_paths=[str(path)],
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
            inp = json.dumps(block.get("input", {}), ensure_ascii=False)
            tools.append(ToolCall(name=name, input_summary=inp[:300], arguments=inp,
                                  call_id=block.get("id", "")))
        elif btype == "tool_result":
            rc = block.get("content", "")
            if isinstance(rc, list):
                rc = " ".join(c.get("text", "") for c in rc if isinstance(c, dict))
            results.append(ToolResult(content=str(rc), call_id=block.get("tool_use_id", ""),
                                      is_error=block.get("is_error")))

    return "\n".join(p for p in text_parts if p), tools, results
