"""Weekly and aggregate reports from session data."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional


class WeeklyReport:
    def __init__(self, sessions: list[dict], distilled: Optional[list[dict]] = None):
        self.sessions = sessions
        self.distilled = distilled or []

    @classmethod
    def from_directory(cls, directory: Path, since: Optional[str] = None) -> WeeklyReport:
        json_idx = directory / "sessions.json"
        sessions: list[dict] = []
        if json_idx.exists():
            data = json.loads(json_idx.read_text(encoding="utf-8"))
            sessions = data.get("sessions", []) if isinstance(data, dict) else data

        distilled_dir = directory / "distilled"
        distilled: list[dict] = []
        if distilled_dir.exists():
            for path in distilled_dir.glob("*.distilled.json"):
                try:
                    d = json.loads(path.read_text(encoding="utf-8"))
                    distilled.append(d)
                except (json.JSONDecodeError, OSError):
                    continue

        if since:
            sessions = [s for s in sessions if (s.get("date") or "") >= since]
            distilled = [d for d in distilled if (d.get("date") or "") >= since]

        return cls(sessions, distilled)

    def render(self, period_label: str = "All time") -> str:
        lines = [f"# Agent Sessions Report — {period_label}", ""]

        if not self.sessions:
            lines.append("No sessions found.")
            return "\n".join(lines)

        total_tokens = sum(s.get("tokens", {}).get("total", 0) for s in self.sessions)
        total_duration = sum(s.get("duration_seconds") or 0 for s in self.sessions)
        total_messages = sum(s.get("message_count", 0) for s in self.sessions)

        lines.append("## Overview")
        lines.append("")
        lines.append(f"- **Sessions:** {len(self.sessions)}")
        lines.append(f"- **Messages:** {total_messages:,}")
        lines.append(f"- **Tokens:** {total_tokens:,}")
        lines.append(f"- **Duration:** {total_duration / 3600:.1f}h")
        lines.append("")

        # By agent
        by_agent: dict[str, list] = defaultdict(list)
        for s in self.sessions:
            by_agent[s.get("agent", "unknown")].append(s)

        lines.append("## By Agent")
        lines.append("")
        lines.append("| Agent | Sessions | Tokens | Duration |")
        lines.append("|---|---|---|---|")
        for agent in sorted(by_agent):
            ss = by_agent[agent]
            tokens = sum(s.get("tokens", {}).get("total", 0) for s in ss)
            dur = sum(s.get("duration_seconds") or 0 for s in ss)
            lines.append(f"| {agent} | {len(ss)} | {tokens:,} | {dur/3600:.1f}h |")
        lines.append("")

        # Top branches
        branch_counter: Counter = Counter()
        for s in self.sessions:
            b = s.get("branch", "unknown")
            if b != "unknown":
                branch_counter[b] += 1

        if branch_counter:
            lines.append("## Top Branches")
            lines.append("")
            for branch, count in branch_counter.most_common(10):
                lines.append(f"- `{branch}` — {count} sessions")
            lines.append("")

        # Longest sessions
        ranked = sorted(
            self.sessions,
            key=lambda s: s.get("duration_seconds") or 0,
            reverse=True,
        )[:10]
        if any(s.get("duration_seconds") for s in ranked):
            lines.append("## Longest Sessions")
            lines.append("")
            for s in ranked:
                if not s.get("duration_seconds"):
                    break
                title = (s.get("title") or "?")[:60]
                lines.append(
                    f"- [{s.get('agent')}] {s.get('date')} {s.get('duration_human', '?')} — {title}"
                )
            lines.append("")

        # Distilled insights
        if self.distilled:
            lines.extend(self._distilled_section())

        return "\n".join(lines)

    def _distilled_section(self) -> list[str]:
        lines = ["## Extracted Knowledge", ""]

        prd_counter: Counter = Counter()
        outcome_counter: Counter = Counter()
        all_deferred: list[str] = []
        all_decisions: list[str] = []
        significant = [d for d in self.distilled if d.get("significance", 0) >= 3]

        for d in self.distilled:
            for prd in d.get("prds", []):
                prd_counter[prd.split(" ")[0]] += 1
            outcome = d.get("outcome", "unknown")
            if outcome != "unknown":
                outcome_counter[outcome] += 1
            all_deferred.extend(d.get("deferred", [])[:2])
            all_decisions.extend(d.get("decisions", [])[:2])

        if prd_counter:
            lines.append("### PRDs Worked On")
            lines.append("")
            for prd, count in prd_counter.most_common(10):
                lines.append(f"- {prd} — {count} session(s)")
            lines.append("")

        if outcome_counter:
            lines.append("### Outcomes")
            lines.append("")
            for outcome, count in outcome_counter.most_common():
                lines.append(f"- {outcome}: {count}")
            lines.append("")

        if significant:
            lines.append(f"### Significant Sessions ({len(significant)})")
            lines.append("")
            for d in sorted(significant, key=lambda x: x.get("significance", 0), reverse=True)[:10]:
                lines.append(
                    f"- [{d.get('agent')}] {d.get('date')} score={d.get('significance')} — {d.get('topic', '')[:60]}"
                )
            lines.append("")

        if all_decisions:
            lines.append("### Recent Decisions")
            lines.append("")
            for dec in all_decisions[:8]:
                lines.append(f"- {dec[:120]}")
            lines.append("")

        if all_deferred:
            lines.append("### Deferred Work")
            lines.append("")
            for defr in all_deferred[:8]:
                lines.append(f"- {defr[:120]}")
            lines.append("")

        return lines

    def save(self, path: Path, period_label: str = "All time") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.render(period_label) + "\n", encoding="utf-8")


def week_start(days_ago: int = 7) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return dt.strftime("%Y-%m-%d")
