"""Parser for Claude Code JSONL transcripts.

Location: ~/.claude/projects/<slug>/<session_id>.jsonl

Event types:
  user/assistant  — conversation messages (skip isSidechain=True)
  ai-title        — session title (aiTitle or title field)
  system          — subtype=away_summary has Claude's state summary
  attachment      — file attachments (skipped)
  custom-title    — user-set title override
  mode/agent-name — metadata events (skipped)

Messages carry: forkedFrom, gitBranch, cwd, timestamp, uuid, usage
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
    TokenUsage,
    ToolCall,
    ToolResult,
)

class ClaudeParser:
    AGENT = Agent.CLAUDE
    SESSIONS_GLOB = "*.jsonl"

    @classmethod
    def find_sessions_dir(cls) -> Path:
        return Path.home() / ".claude" / "projects"

    @classmethod
    def find_session_file(cls, session_id: str) -> Optional[Path]:
        base = cls.find_sessions_dir()
        if not base.exists():
            return None
        for path in base.rglob(f"{session_id}.jsonl"):
            return path
        return None

    @classmethod
    def list_sessions(cls, project_slug: Optional[str] = None) -> list[Path]:
        base = cls.find_sessions_dir()
        if not base.exists():
            return []
        if project_slug:
            target = base / project_slug
            if not target.exists():
                return []
            return sorted(target.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        return sorted(base.rglob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)

    @classmethod
    def parse(cls, path: Path, diagnostics=None) -> Optional[Session]:
        session_id = path.stem
        messages: list[Message] = []
        title = "Claude Code Session"
        away_summaries: list[str] = []
        forked_from: Optional[str] = None
        git_branch: Optional[str] = None
        cwd: Optional[str] = None
        model: Optional[str] = None
        first_ts: Optional[datetime] = None
        last_ts: Optional[datetime] = None
        total_usage = TokenUsage()

        for line_number, d in read_records(path, "claude", diagnostics):
            t = d.get("type")

            if t == "ai-title":
                title = d.get("aiTitle") or d.get("title") or title

            elif t == "custom-title":
                title = d.get("customTitle") or title

            elif t == "system":
                if d.get("subtype") == "away_summary":
                    content = d.get("content", "").strip()
                    if content and content not in away_summaries:
                        away_summaries.append(content)

            elif t in ("user", "assistant") and not d.get("isSidechain"):
                if forked_from is None and d.get("forkedFrom"):
                    forked_from = d["forkedFrom"].get("sessionId")
                if git_branch is None and d.get("gitBranch"):
                    git_branch = d["gitBranch"]
                if cwd is None and d.get("cwd"):
                    cwd = d["cwd"]

                ts = _parse_ts(d.get("timestamp"))
                if ts:
                    if first_ts is None:
                        first_ts = ts
                    last_ts = ts

                usage = d.get("usage")
                if usage and isinstance(usage, dict):
                    if model is None:
                        model = d.get("model", "")
                    total_usage += TokenUsage(
                        input_tokens=usage.get("input_tokens", 0),
                        output_tokens=usage.get("output_tokens", 0),
                        cache_read_tokens=usage.get("cache_read_input_tokens", 0),
                        cache_write_tokens=usage.get("cache_creation_input_tokens", 0),
                    )

                text, tools, results = _extract_content((d.get("message") or {}).get("content", ""))
                if text or tools or results:
                    messages.append(Message(
                        role=t,
                        text=text,
                        timestamp=ts,
                        tool_calls=tools,
                        tool_results=results,
                        source_path=str(path),
                        source_line=line_number,
                    ))

        if not messages:
            return None

        return Session(
            id=session_id,
            agent=Agent.CLAUDE,
            title=title,
            summary=away_summaries[-1] if away_summaries else "",
            earlier_summaries=away_summaries[:-1] if len(away_summaries) > 1 else [],
            branch=git_branch or "unknown",
            cwd=cwd or "",
            model=model or "",
            started_at=first_ts,
            ended_at=last_ts,
            parent_id=forked_from,
            messages=messages,
            usage=total_usage,
            source_path=str(path),
        )


def _parse_ts(value) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except (OSError, ValueError):
            return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _extract_content(content) -> tuple[str, list[ToolCall], list[ToolResult]]:
    if isinstance(content, str):
        return content, [], []

    text_parts: list[str] = []
    tools: list[ToolCall] = []
    results: list[ToolResult] = []

    if not isinstance(content, list):
        return "", [], []

    for block in content:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "text":
            text_parts.append(block.get("text", ""))
        elif btype == "tool_use":
            name = block.get("name", "tool")
            inp = json.dumps(block.get("input", {}), ensure_ascii=False)
            call_id = block.get("id")
            tools.append(ToolCall(name=name, input_summary=inp[:300], arguments=inp,
                                  call_id=call_id if isinstance(call_id, str) else ""))
        elif btype == "tool_result":
            rc = block.get("content", "")
            if isinstance(rc, list):
                rc = " ".join(c.get("text", "") for c in rc if isinstance(c, dict))
            call_id = block.get("tool_use_id")
            error = block.get("is_error")
            results.append(ToolResult(content=str(rc), call_id=call_id if isinstance(call_id, str) else "",
                                      is_error=error if isinstance(error, bool) else None))

    return "\n".join(p for p in text_parts if p), tools, results
