"""Render a Session as a Markdown file."""

from __future__ import annotations

from pathlib import Path

from agent_sessions.models import Session
from agent_sessions.storage import directory_lock, atomic_write_text, validate_session_id


class MarkdownRenderer:

    @classmethod
    def render(cls, session: Session) -> str:
        lines = [f"# {session.title}", ""]

        lines.append(f"**Agent:** {session.agent.value}")
        lines.append(f"**Session ID:** `{session.id}`")
        if session.parent_id:
            lines.append(f"**Forked from:** `{session.parent_id}` (rewind/branch)")
        lines.append(f"**Branch:** `{session.branch}`")
        if session.project_slug:
            lines.append(f"**Project slug:** `{session.project_slug}` (source directory name)")
        if session.model:
            lines.append(f"**Model:** `{session.model}`")
        if session.model_provider:
            lines.append(f"**Model provider:** `{session.model_provider}`")
        lines.append(f"**Started:** {_fmt_dt(session.started_at)}")
        if session.date_source == "file_mtime":
            lines.append(f"**Observed:** {_fmt_dt(session.observed_at)} (file modification time; estimated date)")
        lines.append(f"**Date source:** {session.date_source}")
        if session.duration_human != "unknown":
            lines.append(f"**Duration:** {session.duration_human}")
        lines.append(f"**Messages:** {session.user_message_count} user / {session.assistant_message_count} assistant")

        if session.usage.total_tokens > 0:
            u = session.usage
            lines.append(f"**Tokens:** {u.input_tokens:,} in / {u.output_tokens:,} out (total: {u.total_tokens:,})")
            if u.cache_read_tokens:
                lines.append(f"**Cache:** {u.cache_read_tokens:,} read / {u.cache_write_tokens:,} write")

        lines.append("")

        if session.summary:
            lines.append("## Session Summary")
            lines.append("")
            lines.append(session.summary)
            if session.earlier_summaries:
                lines.append("")
                lines.append("<details><summary>Earlier mid-session summaries</summary>")
                lines.append("")
                for s in session.earlier_summaries:
                    lines.append(f"- {s}")
                lines.append("")
                lines.append("</details>")
            lines.append("")

        lines += ["---", ""]

        for msg in session.messages:
            label = {"user": "User", "assistant": "Assistant", "tool": "Tool", "system": "System"}.get(msg.role, msg.role)
            header = f"## {label}"
            if msg.phase:
                header += f" ({msg.phase})"
            if msg.timestamp:
                header += f"  <sup>{_fmt_dt(msg.timestamp)}</sup>"
            lines.append(header)
            lines.append("")

            if msg.text:
                lines.append(msg.text)

            for tc in msg.tool_calls:
                lines.append(f"\n*[Tool: {tc.name}]* `{tc.input_summary}`")
                if tc.call_id:
                    lines.append(f"\nCall ID: `{tc.call_id}`")
                if tc.arguments:
                    lines.append("\n" + _code_block(tc.arguments))

            for tr in msg.tool_results:
                call_ref = f" (call `{tr.call_id}`)" if tr.call_id else ""
                lines.append(f"\n*[Tool result]*{call_ref}")
                lines.append("\n" + _code_block(tr.content))

            lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    @classmethod
    def write(cls, session: Session, out_dir: Path) -> Path:
        validate_session_id(session.id)
        path = out_dir / f"{session.id}.md"
        with directory_lock(out_dir):
            atomic_write_text(path, cls.render(session))
        return path


def _fmt_dt(dt) -> str:
    if dt is None:
        return "unknown"
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def _code_block(text: str) -> str:
    # Source text can itself contain Markdown fences.
    fence = "```"
    while fence in text:
        fence += "`"
    return f"{fence}text\n{text}\n{fence}"
