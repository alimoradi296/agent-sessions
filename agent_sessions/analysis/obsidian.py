"""Export distilled sessions as Obsidian notes."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from agent_sessions.analysis.distiller import DistilledSession


class ObsidianExporter:
    """Write Zettelkasten-friendly Obsidian notes from distilled sessions."""

    DEFAULT_FOLDER = "Agent Sessions"

    @classmethod
    def note_path(cls, vault: Path, distilled: DistilledSession, folder: str = "") -> Path:
        folder_name = folder or cls.DEFAULT_FOLDER
        safe_date = distilled.date or "undated"
        slug = cls._slugify(distilled.topic or distilled.title)
        short_id = distilled.session_id[:8]
        filename = f"{safe_date} {slug} ({short_id}).md"
        return vault / folder_name / filename

    @classmethod
    def render(cls, distilled: DistilledSession, session_md_path: Optional[str] = None) -> str:
        tags = ["agent-session", distilled.agent]
        if distilled.outcome != "unknown":
            tags.append(f"outcome/{distilled.outcome}")
        for prd in distilled.prds[:3]:
            num = re.search(r"\d+", prd)
            if num:
                tags.append(f"PRD-{num.group().zfill(3)}")

        frontmatter = {
            "type": "agent-session",
            "session_id": distilled.session_id,
            "agent": distilled.agent,
            "date": distilled.date,
            "branch": distilled.branch,
            "project": distilled.project,
            "topic": distilled.topic,
            "outcome": distilled.outcome,
            "significance": distilled.significance,
            "duration": distilled.duration_human,
            "tokens": distilled.tokens_total,
            "prds": distilled.prds,
            "tags": tags,
        }

        lines = ["---"]
        for key, val in frontmatter.items():
            if isinstance(val, list):
                lines.append(f"{key}:")
                for item in val:
                    lines.append(f"  - {item}")
            else:
                lines.append(f"{key}: {val}")
        lines.append("---")
        lines.append("")

        lines.append(f"# {distilled.title}")
        lines.append("")
        lines.append(f"**Agent:** {distilled.agent} | **Branch:** `{distilled.branch}` | **Duration:** {distilled.duration_human}")
        if distilled.tokens_total:
            lines.append(f"**Tokens:** {distilled.tokens_total:,}")
        lines.append("")

        if distilled.summary:
            lines.append("## Summary")
            lines.append("")
            lines.append(distilled.summary)
            lines.append("")

        if distilled.prds:
            lines.append("## PRDs")
            lines.append("")
            for prd in distilled.prds:
                lines.append(f"- [[{prd}]]")
            lines.append("")

        if distilled.decisions:
            lines.append("## Decisions")
            lines.append("")
            for d in distilled.decisions:
                lines.append(f"- {d}")
            lines.append("")

        if distilled.bugs_found:
            lines.append("## Bugs / Issues")
            lines.append("")
            for b in distilled.bugs_found:
                lines.append(f"- {b}")
            lines.append("")

        if distilled.deferred:
            lines.append("## Deferred")
            lines.append("")
            for d in distilled.deferred:
                lines.append(f"- {d}")
            lines.append("")

        if distilled.open_questions:
            lines.append("## Open Questions")
            lines.append("")
            for q in distilled.open_questions:
                lines.append(f"- {q}")
            lines.append("")

        if distilled.files_touched:
            lines.append("## Files Touched")
            lines.append("")
            for f in distilled.files_touched[:20]:
                lines.append(f"- `{f}`")
            if len(distilled.files_touched) > 20:
                lines.append(f"- ... +{len(distilled.files_touched) - 20} more")
            lines.append("")

        if distilled.tools_used:
            lines.append(f"**Tools:** {', '.join(distilled.tools_used[:15])}")
            lines.append("")

        if session_md_path:
            lines.append(f"[[Full transcript|{session_md_path}]]")
        else:
            lines.append(f"Session ID: `{distilled.session_id}`")

        return "\n".join(lines)

    @classmethod
    def write(cls, vault: Path, distilled: DistilledSession, folder: str = "", session_md_path: Optional[str] = None) -> Path:
        path = cls.note_path(vault, distilled, folder)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(cls.render(distilled, session_md_path), encoding="utf-8")
        return path

    @staticmethod
    def _slugify(text: str, max_len: int = 50) -> str:
        slug = re.sub(r"[^\w\s-]", "", text.lower())
        slug = re.sub(r"[\s_]+", "-", slug).strip("-")
        return slug[:max_len] or "session"
