"""Canonical data model for agent sessions across all providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class Agent(Enum):
    CLAUDE = "claude"
    CODEX = "codex"
    CURSOR = "cursor"


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    reasoning_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def __iadd__(self, other: TokenUsage) -> TokenUsage:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_read_tokens += other.cache_read_tokens
        self.cache_write_tokens += other.cache_write_tokens
        self.reasoning_tokens += other.reasoning_tokens
        return self


@dataclass
class Message:
    role: str  # "user" | "assistant" | "system" | "tool"
    text: str
    timestamp: Optional[datetime] = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    phase: str = ""
    source_path: str = ""
    source_line: Optional[int] = None


@dataclass
class ToolCall:
    name: str
    input_summary: str  # truncated JSON of input
    call_id: str = ""
    arguments: str = ""


@dataclass
class ToolResult:
    content: str  # truncated result text
    call_id: str = ""
    is_error: Optional[bool] = None


@dataclass
class Session:
    id: str
    agent: Agent
    title: str = "Untitled Session"
    summary: str = ""
    earlier_summaries: list[str] = field(default_factory=list)
    branch: str = "unknown"
    cwd: str = ""
    model: str = ""
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    parent_id: Optional[str] = None
    messages: list[Message] = field(default_factory=list)
    usage: TokenUsage = field(default_factory=TokenUsage)
    source_path: str = ""
    source_paths: list[str] = field(default_factory=list)
    model_provider: str = ""
    project_slug: str = ""
    observed_at: Optional[datetime] = None

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.started_at and self.ended_at:
            return (self.ended_at - self.started_at).total_seconds()
        return None

    @property
    def duration_human(self) -> str:
        secs = self.duration_seconds
        if secs is None:
            return "unknown"
        mins, s = divmod(int(secs), 60)
        hours, m = divmod(mins, 60)
        if hours:
            return f"{hours}h {m}m"
        if m:
            return f"{m}m {s}s"
        return f"{s}s"

    @property
    def date_str(self) -> str:
        if self.started_at:
            return self.started_at.strftime("%Y-%m-%d")
        if self.observed_at:
            return self.observed_at.strftime("%Y-%m-%d")
        return ""

    @property
    def date_source(self) -> str:
        if self.started_at:
            return "transcript"
        if self.observed_at:
            return "file_mtime"
        return "unknown"

    @property
    def message_count(self) -> int:
        return len(self.messages)

    @property
    def user_message_count(self) -> int:
        return sum(1 for m in self.messages if m.role == "user")

    @property
    def assistant_message_count(self) -> int:
        return sum(1 for m in self.messages if m.role == "assistant")
