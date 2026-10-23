"""Rule-based extraction of structured knowledge from sessions."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from agent_sessions.models import Session
from agent_sessions.analysis.transcript import clean_knowledge_text, conversation_sections

# ── Patterns ────────────────────────────────────────────────────────────────

PRD_PATTERN = re.compile(r"\bPRD[-\s]?(\d{2,3})\b(?:[-\s(]+([\w-]{4,}))?", re.IGNORECASE)
GARBAGE_PRD_SLUGS = frozenset({
    "and", "was", "for", "is", "to", "in", "the", "after", "main", "files",
    "date", "docs", "agent", "raed", "permission", "implemented", "revision",
    "history", "after-implementation", "biz-think",
})
FILE_PATH_PATTERN = re.compile(
    r"(?:^|[\s`'\"])([\w.-]+/(?:[\w./-]+\.(?:py|md|tsx?|json|yml|yaml|toml|sh)))(?:[\s`'\"]|$)",
    re.MULTILINE,
)
APPS_PATH_PATTERN = re.compile(r"apps/[\w/]+/[\w./-]+\.py")
DOCS_PATH_PATTERN = re.compile(r"docs/[\w./-]+\.md")

DEFERRED_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"defer(?:red|ring)?(?:\s+to|\s+until|\s+for)?\s+(.{10,120})",
        r"out of scope(?:\s+for now)?[:\s]+(.{10,120})",
        r"not in (?:this|the) sprint[:\s]+(.{10,120})",
        r"will (?:do|handle|address) (?:this )?later[:\s]+(.{10,120})",
        r"TODO(?:\s*\([^)]*\))?[:\s]+(.{10,120})",
        r"FIXME[:\s]+(.{10,120})",
    ]
]

DECISION_PATTERNS = [
    re.compile(p, re.IGNORECASE | re.MULTILINE)
    for p in [
        r"(?:decided|decision)[:\s]+(.{15,200})",
        r"(?:going with|we(?:'ll| will) use|chose to use)\s+(.{15,200})",
    ]
]

BUG_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"root cause[:\s]+(.{15,200})",
        r"(?:bug|issue)[:\s]+(.{15,200})",
        r"missing (?:company|archived|filter|permission)[^\n]{5,100}",
        r"(?:N\+1|deadlock|KeyError|data leak)[^\n]{5,100}",
    ]
]

OUTCOME_KEYWORDS = {
    "implemented": ["implement", "implemented", "shipped", "merged", "deployed"],
    "fixed": ["fix", "fixed", "bug fix", "resolved", "patch"],
    "reviewed": ["review", "reviewed", "audit", "post-prd-review"],
    "planned": ["plan", "prd-write", "sprint-analysis", "roadmap"],
    "debugged": ["debug", "investigate", "root cause", "reproduce"],
    "refactored": ["refactor", "extract", "cleanup", "restructure"],
    "tested": ["test", "pytest", "regression", "coverage"],
}

COMMAND_PATTERN = re.compile(r"(?:^|\s)/([a-zA-Z][\w-]{3,})(?![\w/-])", re.MULTILINE)
CURSOR_CMD_PATTERN = re.compile(r"Cursor Command:\s*([\w/-]+)")
PATH_LIKE_COMMANDS = frozenset({
    "apps", "docs", "home", "empty", "api", "v1", "dev", "null",
    "components", "settings", "services",
    "middleware", "users", "apis", "auth", "token", "login", "presence",
})


@dataclass
class DistilledSession:
    session_id: str
    agent: str
    title: str
    topic: str
    project: str
    branch: str
    date: str
    duration_seconds: Optional[float]
    duration_human: str
    tokens_total: int
    message_count: int
    parent_id: Optional[str]

    prds: list[str] = field(default_factory=list)
    files_touched: list[str] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    commands_used: list[str] = field(default_factory=list)

    outcome: str = "unknown"
    significance: int = 0

    decisions: list[str] = field(default_factory=list)
    bugs_found: list[str] = field(default_factory=list)
    deferred: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)

    summary: str = ""
    date_source: str = "unknown"
    outcome_source: str = "heuristic_unverified"
    distill_version: int = 2

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, out_dir: Path) -> Path:
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{self.session_id}.distilled.json"
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path) -> DistilledSession:
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(**data)


class Distiller:
    """Extract structured knowledge from a Session or exported markdown."""

    @classmethod
    def distill(cls, session: Session) -> DistilledSession:
        full_text = cls._full_text(session)
        knowledge_text = cls._knowledge_text(session)
        files = cls._extract_files(session, full_text)
        prds = cls._extract_prds(full_text)
        tools = cls._extract_tools(session)
        commands = cls._extract_commands(full_text)
        deferred = cls._extract_matches(knowledge_text, DEFERRED_PATTERNS, max_items=5)
        decisions = cls._extract_matches(knowledge_text, DECISION_PATTERNS, max_items=5)
        bugs = cls._extract_matches(knowledge_text, BUG_PATTERNS, max_items=5)
        questions = cls._extract_questions(knowledge_text)
        outcome = cls._infer_outcome(knowledge_text, session.title)
        topic = cls._infer_topic(session, prds)
        project = session.project_slug or cls._infer_project(session.cwd)
        significance = cls._score(session, prds, files, decisions, deferred, bugs)

        return DistilledSession(
            session_id=session.id,
            agent=session.agent.value,
            title=session.title[:200],
            topic=topic,
            project=project,
            branch=session.branch,
            date=session.date_str,
            date_source=session.date_source,
            duration_seconds=session.duration_seconds,
            duration_human=session.duration_human,
            tokens_total=session.usage.total_tokens,
            message_count=session.message_count,
            parent_id=session.parent_id,
            prds=prds,
            files_touched=sorted(files)[:50],
            tools_used=sorted(tools),
            commands_used=sorted(commands),
            outcome=outcome,
            significance=significance,
            decisions=decisions,
            bugs_found=bugs,
            deferred=deferred,
            open_questions=questions,
            summary=(session.summary or session.title)[:300],
        )

    @classmethod
    def distill_from_markdown(cls, md_path: Path, meta: Optional[dict] = None) -> Optional[DistilledSession]:
        """Distill from an exported markdown file + optional sessions.json metadata."""
        if not md_path.exists():
            return None
        content = md_path.read_text(encoding="utf-8", errors="replace")
        meta = meta or {}

        session_id = md_path.stem
        full_text = content
        # Export headers, tool evidence, and arbitrary source code are not
        # decision text. Only conversation sections feed knowledge heuristics.
        knowledge_text = "\n".join(text for _, text in conversation_sections(content))

        prds = cls._extract_prds(full_text)
        files = cls._extract_files_from_text(full_text)
        tools = cls._extract_tools_from_text(full_text)
        commands = cls._extract_commands(full_text)
        deferred = cls._extract_matches(knowledge_text, DEFERRED_PATTERNS, max_items=5)
        decisions = cls._extract_matches(knowledge_text, DECISION_PATTERNS, max_items=5)
        bugs = cls._extract_matches(knowledge_text, BUG_PATTERNS, max_items=5)
        questions = cls._extract_questions(knowledge_text)
        title = content.split("\n")[0].lstrip("# ").strip() if content else "Untitled"
        outcome = cls._infer_outcome(knowledge_text, title)
        topic = cls._infer_topic_from_title(title, prds)
        significance = cls._score_from_meta(meta, prds, files, decisions, deferred, bugs)

        return DistilledSession(
            session_id=session_id,
            agent=meta.get("agent", "unknown"),
            title=title[:200],
            topic=topic,
            project=cls._infer_project(meta.get("cwd", "")),
            branch=meta.get("branch", "unknown"),
            date=meta.get("date", ""),
            date_source=meta.get("date_source", "unknown"),
            duration_seconds=meta.get("duration_seconds"),
            duration_human=meta.get("duration_human", "unknown"),
            tokens_total=meta.get("tokens", {}).get("total", 0),
            message_count=meta.get("message_count", 0),
            parent_id=meta.get("parent_id"),
            prds=prds,
            files_touched=sorted(files)[:50],
            tools_used=sorted(tools),
            commands_used=sorted(commands),
            outcome=outcome,
            significance=significance,
            decisions=decisions,
            bugs_found=bugs,
            deferred=deferred,
            open_questions=questions,
            summary=(meta.get("summary") or title)[:300],
        )

    @classmethod
    def is_significant(cls, d: DistilledSession, min_duration_mins: int = 30) -> bool:
        if d.significance >= 3:
            return True
        if d.prds:
            return True
        if d.duration_seconds and d.duration_seconds >= min_duration_mins * 60:
            return True
        if len(d.files_touched) >= 5:
            return True
        if d.decisions or d.deferred or d.bugs_found:
            return True
        return False

    @staticmethod
    def _full_text(session: Session) -> str:
        parts = [session.title, session.summary, *session.earlier_summaries]
        for msg in session.messages:
            parts.append(msg.text)
            for tc in msg.tool_calls:
                parts.append(f"{tc.name} {tc.input_summary}")
        return "\n".join(parts)

    @classmethod
    def _knowledge_text(cls, session: Session) -> str:
        return "\n".join(clean_knowledge_text(msg.text) for msg in session.messages
                         if msg.role in ("user", "assistant") and msg.phase not in ("analysis", "commentary"))


    @staticmethod
    def _extract_prds(text: str) -> list[str]:
        by_num: dict[str, str] = {}
        counts: dict[str, int] = {}
        title_zone = text[:800]

        for m in PRD_PATTERN.finditer(text):
            num = m.group(1)
            slug = (m.group(2) or "").strip("-() ")
            key_num = num.zfill(3)

            if slug.lower() in GARBAGE_PRD_SLUGS or len(slug) < 4:
                label = f"PRD-{key_num}"
            else:
                label = f"PRD-{key_num} ({slug})"

            counts[key_num] = counts.get(key_num, 0) + 1
            if key_num not in by_num or len(label) > len(by_num[key_num]):
                by_num[key_num] = label

        # Keep PRDs mentioned 2+ times, in title zone, or with a real slug
        results: list[str] = []
        for key_num, label in sorted(by_num.items()):
            in_title = f"PRD-{key_num}" in title_zone.upper() or f"PRD {key_num}" in title_zone.upper()
            has_slug = "(" in label
            if counts[key_num] >= 2 or in_title or has_slug:
                results.append(label)
        return results

    @classmethod
    def _extract_files(cls, session: Session, text: str) -> set[str]:
        files = cls._extract_files_from_text(text)
        for msg in session.messages:
            for tc in msg.tool_calls:
                for m in FILE_PATH_PATTERN.finditer(tc.input_summary):
                    files.add(m.group(1).strip("`'\" "))
                for m in APPS_PATH_PATTERN.finditer(tc.input_summary):
                    files.add(m.group(0))
        return files

    @staticmethod
    def _extract_files_from_text(text: str) -> set[str]:
        files: set[str] = set()
        for pat in (APPS_PATH_PATTERN, DOCS_PATH_PATTERN, FILE_PATH_PATTERN):
            for m in pat.finditer(text):
                path = m.group(1) if pat == FILE_PATH_PATTERN else m.group(0)
                path = path.strip("`'\" ")
                if not path.startswith(("http", "www")):
                    files.add(path)
        return files

    @staticmethod
    def _extract_tools(session: Session) -> set[str]:
        tools: set[str] = set()
        for msg in session.messages:
            for tc in msg.tool_calls:
                tools.add(tc.name)
        return tools

    @staticmethod
    def _extract_tools_from_text(text: str) -> set[str]:
        tools: set[str] = set()
        for m in re.finditer(r"\*\[Tool:\s*(\w+)\]\*", text):
            tools.add(m.group(1))
        return tools

    @staticmethod
    def _extract_commands(text: str) -> set[str]:
        cmds: set[str] = set()
        for m in COMMAND_PATTERN.finditer(text):
            name = m.group(1)
            if name.lower() in PATH_LIKE_COMMANDS:
                continue
            if name.count("/") > 2:
                continue
            cmds.add(f"/{name}")
        for m in CURSOR_CMD_PATTERN.finditer(text):
            cmds.add(m.group(1))
        return cmds

    @staticmethod
    def _extract_matches(text: str, patterns: list[re.Pattern], max_items: int = 5) -> list[str]:
        seen: set[str] = set()
        results: list[str] = []
        for pat in patterns:
            for m in pat.finditer(text):
                snippet = (m.group(1) if m.lastindex else m.group(0)).strip()
                snippet = re.sub(r"\s+", " ", snippet)[:200]
                if len(snippet) < 10 or snippet in seen:
                    continue
                seen.add(snippet)
                results.append(snippet)
                if len(results) >= max_items:
                    return results
        return results

    @staticmethod
    def _extract_questions(text: str) -> list[str]:
        results: list[str] = []
        for line in text.split("\n"):
            line = line.strip()
            if "?" in line and 20 < len(line) < 200:
                if any(kw in line.lower() for kw in ("should we", "what about", "how do", "why ", "open question")):
                    results.append(line[:200])
            if len(results) >= 3:
                break
        return results

    @staticmethod
    def _infer_outcome(text: str, title: str) -> str:
        combined = f"{title} {text}".lower()
        scores: dict[str, int] = {}
        for outcome, keywords in OUTCOME_KEYWORDS.items():
            scores[outcome] = sum(combined.count(kw) for kw in keywords)
        best = max(scores, key=lambda k: scores[k])
        return best if scores[best] > 0 else "unknown"

    @staticmethod
    def _infer_topic(session: Session, prds: list[str]) -> str:
        if prds:
            return prds[0]
        title = session.title
        if len(title) > 10 and title != "Claude Code Session":
            return title[:120]
        if session.summary:
            return session.summary[:120]
        return "Untitled"

    @staticmethod
    def _infer_topic_from_title(title: str, prds: list[str]) -> str:
        if prds:
            return prds[0]
        return title[:120] if title else "Untitled"

    @staticmethod
    def _infer_project(cwd: str) -> str:
        if not cwd:
            return "unknown"
        parts = Path(cwd).parts
        return parts[-1] if parts else "unknown"

    @staticmethod
    def _score(
        session: Session,
        prds: list[str],
        files: set[str],
        decisions: list[str],
        deferred: list[str],
        bugs: list[str],
    ) -> int:
        score = 0
        if prds:
            score += 2
        if len(files) >= 5:
            score += 2
        elif files:
            score += 1
        if decisions:
            score += 2
        if deferred:
            score += 1
        if bugs:
            score += 1
        dur = session.duration_seconds or 0
        if dur >= 3600:
            score += 2
        elif dur >= 1800:
            score += 1
        if session.usage.total_tokens > 500_000:
            score += 1
        return score

    @staticmethod
    def _score_from_meta(
        meta: dict,
        prds: list[str],
        files: set[str],
        decisions: list[str],
        deferred: list[str],
        bugs: list[str],
    ) -> int:
        score = 0
        if prds:
            score += 2
        if len(files) >= 5:
            score += 2
        elif files:
            score += 1
        if decisions:
            score += 2
        if deferred:
            score += 1
        if bugs:
            score += 1
        dur = meta.get("duration_seconds") or 0
        if dur >= 3600:
            score += 2
        elif dur >= 1800:
            score += 1
        tokens = meta.get("tokens", {}).get("total", 0)
        if tokens > 500_000:
            score += 1
        return score
