"""Parsers for each agent's raw transcript format."""

from agent_sessions.parsers.claude import ClaudeParser
from agent_sessions.parsers.codex import CodexParser
from agent_sessions.parsers.cursor import CursorParser

PARSERS = {
    "claude": ClaudeParser,
    "codex": CodexParser,
    "cursor": CursorParser,
}

__all__ = ["ClaudeParser", "CodexParser", "CursorParser", "PARSERS"]
