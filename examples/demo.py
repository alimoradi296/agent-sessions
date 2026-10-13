"""Export the synthetic fixture without reading real agent session directories."""
from pathlib import Path

from agent_sessions.cli import export_session
from agent_sessions.parsers.claude import ClaudeParser

repo = Path(__file__).resolve().parents[1]
session = ClaudeParser.parse(repo / "examples" / "sample-session.jsonl")
if session is None:
    raise SystemExit("The sample transcript contains no messages.")
export_session(session, repo / "demo-output")
