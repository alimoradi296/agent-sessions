"""Render a Session as a Markdown file."""

from __future__ import annotations

from pathlib import Path

from agent_sessions.models import Session


class MarkdownRenderer:

    @classmethod
    def render(cls, session: Session) -> str:
        lines = [f"# {session.title}", ""]

        lines.append(f"**Agent:** {session.agent.value}")
        lines.append(f"**Session ID:** `{session.id}`")
        if session.parent_id:
            lines.append(f"**Forked from:** `{session.parent_id}` (rewind/branch)")
        lines.append(f"**Branch:** `{session.branch}`")
        if session.model:
            lines.append(f"**Model:** `{session.model}`")
        lines.append(f"**Started:** {_fmt_dt(session.started_at)}")
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
            label = "User" if msg.role == "user" else "Assistant"
            header = f"## {label}"
            if msg.timestamp:
                header += f"  <sup>{_fmt_dt(msg.timestamp)}</sup>"
            lines.append(header)
            lines.append("")

            if msg.text:
                lines.append(msg.text)

            for tc in msg.tool_calls:
                lines.append(f"\n*[Tool: {tc.name}]* `{tc.input_summary}`")

            for tr in msg.tool_results:
                lines.append(f"\n*[Tool result]* {tr.content}")

            lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    @classmethod
    def write(cls, session: Session, out_dir: Path) -> Path:
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{session.id}.md"
        path.write_text(cls.render(session), encoding="utf-8")
        return path


def _fmt_dt(dt) -> str:
    if dt is None:
        return "unknown"
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
