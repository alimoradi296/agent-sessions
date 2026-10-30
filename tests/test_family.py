"""Tests for the exported session-family digest MVP."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from agent_sessions.analysis.family import (
    build_family_digest,
    evaluate_required_signals,
    render_family_digest,
)
from agent_sessions.cli import cmd_family
from agent_sessions.analysis.continuity import load_requirements
from agent_sessions.models import Agent, Message, Session
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.renderers.markdown import MarkdownRenderer
from examples.family_digest_demo import evaluate


def _write(archive: Path, session: Session) -> None:
    MarkdownRenderer.write(session, archive)
    JsonIndexRenderer.update(session, archive / "sessions.json")


class FamilyDigestTests(unittest.TestCase):
    def test_walks_ancestors_and_descendants_with_quotes(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary)
            started = datetime(2026, 10, 28, tzinfo=timezone.utc)
            parent = Session(
                id="parent-a",
                agent=Agent.CLAUDE,
                title="Parent",
                parent_id=None,
                started_at=started,
                messages=[
                    Message(role="user", text="Parent request with discovery-only scope."),
                    Message(role="assistant", text="Discovery only. Do not implement or publish."),
                ],
            )
            child = Session(
                id="child-b",
                agent=Agent.CLAUDE,
                title="Child",
                parent_id="parent-a",
                started_at=started,
                messages=[
                    Message(role="user", text="Child follow-up."),
                    Message(role="assistant", text="Child answer."),
                ],
            )
            grandchild = Session(
                id="child-c",
                agent=Agent.CLAUDE,
                title="Grandchild",
                parent_id="child-b",
                started_at=started,
                messages=[
                    Message(role="user", text="Grandchild request."),
                    Message(role="assistant", text="Grandchild answer."),
                ],
            )
            for session in (parent, child, grandchild):
                _write(archive, session)

            report = build_family_digest(archive, "child-b", max_quote_chars=80)
            self.assertEqual(
                [member["session_id"] for member in report["members"]],
                ["parent-a", "child-b", "child-c"],
            )
            self.assertEqual(
                [member["relation"] for member in report["members"]],
                ["ancestor", "focus", "descendant"],
            )
            self.assertEqual(report["members"][1]["edge"], "forked_from")
            self.assertIn("Do not implement", report["members"][0]["quotes"][1]["text"])
            self.assertTrue(any(signal["kind"] == "scope_boundary"
                                for signal in report["members"][0]["signals"]))
            self.assertGreaterEqual(report["family_summary"]["signal_count"], 1)
            self.assertGreaterEqual(len(report["pin_suggestions"]), 1)
            self.assertIn("pin_command_template", report["pin_suggestions"][0])
            self.assertIn("handoff pin", report["pin_suggestions"][0]["pin_command_template"])
            markdown = render_family_digest(report)
            self.assertIn("Session family: child-b", markdown)
            self.assertIn("Family summary", markdown)
            self.assertIn("Suggested pins", markdown)
            self.assertIn("```text", markdown)

    def test_codex_edge_and_missing_parent(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary)
            child = Session(
                id="codex-child",
                agent=Agent.CODEX,
                title="Codex child",
                parent_id="missing-parent",
                messages=[
                    Message(role="user", text="Spawned work."),
                    Message(role="assistant", text="Spawned answer."),
                ],
            )
            _write(archive, child)
            report = build_family_digest(archive, "codex-child")
            self.assertEqual(report["members"][0]["session_id"], "missing-parent")
            self.assertEqual(report["members"][0]["transcript"], "missing_index")
            self.assertEqual(report["members"][1]["edge"], "spawned_from")
            self.assertIn("missing-parent", report["missing_parents"])

    def test_quote_truncation(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary)
            long_text = "A" * 200
            session = Session(
                id="solo",
                agent=Agent.CURSOR,
                title="Solo",
                messages=[
                    Message(role="user", text=long_text),
                    Message(role="assistant", text="short"),
                ],
            )
            _write(archive, session)
            report = build_family_digest(archive, "solo", max_quote_chars=50)
            quote = report["members"][0]["quotes"][0]
            self.assertTrue(quote["truncated"])
            self.assertLessEqual(len(quote["text"]), 50)

    def test_cli_writes_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "exports"
            archive.mkdir()
            session = Session(
                id="cli-focus",
                agent=Agent.CLAUDE,
                title="CLI focus",
                messages=[
                    Message(role="user", text="Hello"),
                    Message(role="assistant", text="Hi"),
                ],
            )
            _write(archive, session)
            out = root / "family.json"
            with patch("sys.stdout", new_callable=io.StringIO) as stdout:
                cmd_family(
                    Namespace(
                        session_id="cli-focus",
                        directory=str(archive),
                        max_quote_chars=120,
                        max_signals=8,
                        max_pin_suggestions=12,
                        signal_kinds=None,
                        pin_signal_kinds=None,
                        focus_priority_bonus=15,
                        min_signal_priority=0,
                        profile="balanced",
                        require_signal_kinds=None,
                        requirements_out=None,
                        overwrite_requirements=False,
                        bundle_out=None,
                        query=None,
                        last=5,
                        max_chars=24000,
                        max_total_chars=120000,
                        audit_family_bundle=False,
                        json=True,
                        output=str(out),
                    )
                )
            self.assertIn("Family digest", stdout.getvalue())
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["focus"], "cli-focus")
            self.assertEqual(payload["member_count"], 1)

    def test_cli_generates_requirements_from_suggestions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "exports"
            archive.mkdir()
            parent = Session(
                id="parent-x",
                agent=Agent.CLAUDE,
                title="Parent",
                messages=[
                    Message(role="user", text="Plan this work."),
                    Message(role="assistant", text="Discovery only. Do not implement or publish."),
                ],
            )
            child = Session(
                id="child-y",
                agent=Agent.CLAUDE,
                title="Child",
                parent_id="parent-x",
                messages=[
                    Message(role="user", text="Continue."),
                    Message(role="assistant", text="Open question: should we keep this out of scope?"),
                ],
            )
            _write(archive, parent)
            _write(archive, child)
            requirements = root / "private" / "requirements.json"
            requirements.parent.mkdir()
            with patch("sys.stdout", new_callable=io.StringIO):
                cmd_family(
                    Namespace(
                        session_id="child-y",
                        directory=str(archive),
                        max_quote_chars=120,
                        max_signals=8,
                        max_pin_suggestions=12,
                        signal_kinds=None,
                        pin_signal_kinds=None,
                        focus_priority_bonus=15,
                        min_signal_priority=0,
                        profile="balanced",
                        require_signal_kinds=None,
                        requirements_out=str(requirements),
                        overwrite_requirements=False,
                        bundle_out=None,
                        query=None,
                        last=5,
                        max_chars=24000,
                        max_total_chars=120000,
                        audit_family_bundle=False,
                        json=True,
                        output=None,
                    )
                )
            contract = load_requirements(requirements)
            self.assertGreaterEqual(len(contract["requirements"]), 1)
            self.assertTrue(any("Discovery only" in item["quote"] or "Open question" in item["quote"]
                                for item in contract["requirements"]))

    def test_cli_generates_bundle_from_family(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "exports"
            archive.mkdir()
            parent = Session(
                id="bundle-parent",
                agent=Agent.CLAUDE,
                title="Bundle Parent",
                messages=[
                    Message(role="user", text="Check the feature shape."),
                    Message(role="assistant", text="Discovery only. Do not implement or publish."),
                ],
            )
            child = Session(
                id="bundle-child",
                agent=Agent.CLAUDE,
                title="Bundle Child",
                parent_id="bundle-parent",
                messages=[
                    Message(role="user", text="Continue the same investigation."),
                    Message(role="assistant", text="Open question: should we defer cache eviction?"),
                ],
            )
            _write(archive, parent)
            _write(archive, child)
            bundle = root / "private" / "bundle"
            with patch("sys.stdout", new_callable=io.StringIO) as stdout:
                cmd_family(
                    Namespace(
                        session_id="bundle-child",
                        directory=str(archive),
                        max_quote_chars=120,
                        max_signals=8,
                        max_pin_suggestions=12,
                        signal_kinds=None,
                        pin_signal_kinds=None,
                        focus_priority_bonus=15,
                        min_signal_priority=0,
                        profile="balanced",
                        require_signal_kinds=None,
                        requirements_out=None,
                        overwrite_requirements=False,
                        bundle_out=str(bundle),
                        query="family-bundle",
                        last=5,
                        max_chars=24000,
                        max_total_chars=120000,
                        audit_family_bundle=True,
                        json=True,
                        output=None,
                    )
                )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["family_bundle"]["path"], str(bundle))
            self.assertIn("audit", payload["family_bundle"])
            self.assertTrue((bundle / "handoff.md").is_file())
            self.assertTrue((bundle / "manifest.json").is_file())

    def test_cli_profile_questions_filters_to_open_questions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "exports"
            archive.mkdir()
            _write(archive, Session(
                id="profile-parent",
                agent=Agent.CLAUDE,
                title="Profile Parent",
                messages=[
                    Message(role="user", text="Plan this safely."),
                    Message(role="assistant", text="Discovery only. Do not implement or publish."),
                ],
            ))
            _write(archive, Session(
                id="profile-child",
                agent=Agent.CLAUDE,
                title="Profile Child",
                parent_id="profile-parent",
                messages=[
                    Message(role="user", text="Continue."),
                    Message(role="assistant", text="Open question: should we defer this?"),
                ],
            ))
            with patch("sys.stdout", new_callable=io.StringIO) as stdout:
                cmd_family(
                    Namespace(
                        session_id="profile-child",
                        directory=str(archive),
                        max_quote_chars=120,
                        max_signals=8,
                        max_pin_suggestions=12,
                        signal_kinds=None,
                        pin_signal_kinds=None,
                        focus_priority_bonus=15,
                        min_signal_priority=0,
                        profile="questions",
                        require_signal_kinds=None,
                        requirements_out=None,
                        overwrite_requirements=False,
                        bundle_out=None,
                        query=None,
                        last=5,
                        max_chars=24000,
                        max_total_chars=120000,
                        audit_family_bundle=False,
                        json=True,
                        output=None,
                    )
                )
            payload = json.loads(stdout.getvalue())
            pin_kinds = {item["kind"] for item in payload["pin_suggestions"]}
            self.assertEqual(pin_kinds, {"open_question"})
            self.assertEqual(payload["signal_profile"], "questions")

    def test_cli_profile_strict_bundle_with_requirements_and_audit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "exports"
            archive.mkdir()
            _write(archive, Session(
                id="strict-parent",
                agent=Agent.CLAUDE,
                title="Strict Parent",
                messages=[
                    Message(role="user", text="Initial discovery request."),
                    Message(role="assistant", text="Discovery only. Do not implement or publish."),
                ],
            ))
            _write(archive, Session(
                id="strict-child",
                agent=Agent.CLAUDE,
                title="Strict Child",
                parent_id="strict-parent",
                messages=[
                    Message(role="user", text="Continue analysis."),
                    Message(role="assistant", text="Open question: should we defer migration checks?"),
                ],
            ))
            requirements = root / "private" / "strict.requirements.json"
            requirements.parent.mkdir()
            bundle = root / "private" / "strict.bundle"
            with patch("sys.stdout", new_callable=io.StringIO) as stdout:
                cmd_family(
                    Namespace(
                        session_id="strict-child",
                        directory=str(archive),
                        max_quote_chars=120,
                        max_signals=8,
                        max_pin_suggestions=12,
                        signal_kinds=None,
                        pin_signal_kinds=None,
                        focus_priority_bonus=15,
                        min_signal_priority=0,
                        profile="strict",
                        require_signal_kinds=None,
                        requirements_out=str(requirements),
                        overwrite_requirements=False,
                        bundle_out=str(bundle),
                        query="strict-profile-bundle",
                        last=5,
                        max_chars=24000,
                        max_total_chars=120000,
                        audit_family_bundle=True,
                        json=True,
                        output=None,
                    )
                )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["signal_profile"], "strict")
            self.assertTrue(requirements.is_file())
            contract = load_requirements(requirements)
            self.assertGreaterEqual(len(contract["requirements"]), 1)
            self.assertTrue((bundle / "handoff.md").is_file())
            self.assertEqual(payload["family_bundle"]["audit"]["exit_code"], 0)

    def test_require_signal_kind_blocks_bundle_generation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "exports"
            archive.mkdir()
            _write(archive, Session(
                id="gate-parent",
                agent=Agent.CLAUDE,
                title="Gate Parent",
                messages=[
                    Message(role="user", text="Start."),
                    Message(role="assistant", text="Discovery only. Do not implement or publish."),
                ],
            ))
            _write(archive, Session(
                id="gate-child",
                agent=Agent.CLAUDE,
                title="Gate Child",
                parent_id="gate-parent",
                messages=[
                    Message(role="user", text="Continue."),
                    Message(role="assistant", text="Notes retained without blockers."),
                ],
            ))
            report = build_family_digest(archive, "gate-child")
            check = evaluate_required_signals(report, ["reported_blocker"])
            self.assertFalse(check["passed"])
            self.assertEqual(check["missing"], ["reported_blocker"])
            bundle = root / "private" / "blocked.bundle"
            with patch("sys.stdout", new_callable=io.StringIO), self.assertRaises(SystemExit) as raised:
                cmd_family(
                    Namespace(
                        session_id="gate-child",
                        directory=str(archive),
                        max_quote_chars=120,
                        max_signals=8,
                        max_pin_suggestions=12,
                        signal_kinds=None,
                        pin_signal_kinds=None,
                        focus_priority_bonus=15,
                        min_signal_priority=0,
                        profile="balanced",
                        require_signal_kinds=["reported_blocker"],
                        requirements_out=None,
                        overwrite_requirements=False,
                        bundle_out=str(bundle),
                        query="blocked",
                        last=5,
                        max_chars=24000,
                        max_total_chars=120000,
                        audit_family_bundle=False,
                        json=True,
                        output=None,
                    )
                )
            self.assertEqual(raised.exception.code, 1)
            self.assertFalse(bundle.exists())


class FamilyDigestDemoTests(unittest.TestCase):
    def test_end_to_end_synthetic_mvp(self):
        result = evaluate()
        self.assertTrue(result["synthetic_only"])
        self.assertTrue(result["scope_retained"])
        self.assertTrue(result["handoff_ready"])
        self.assertEqual(result["audit_exit_code"], 0)
        self.assertEqual(result["verification"], "not_checked")
        self.assertEqual(result["codex_edge"], "spawned_from")
        self.assertGreaterEqual(result["signal_count"], 1)
        self.assertGreaterEqual(result["pin_suggestion_count"], 1)
        self.assertTrue(result["one_command_ready"])
        self.assertEqual(result["one_command_audit_exit_code"], 0)
        self.assertTrue(result["required_scope_passed"])
        self.assertEqual(
            result["member_ids"],
            [
                "synthetic-family-parent",
                "synthetic-family-child",
                "synthetic-family-grandchild",
            ],
        )

    def test_signal_kind_filtering(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary)
            _write(archive, Session(
                id="filter-parent",
                agent=Agent.CLAUDE,
                title="Filter Parent",
                messages=[
                    Message(role="user", text="Plan the task."),
                    Message(role="assistant", text="Discovery only. Do not implement or publish."),
                ],
            ))
            _write(archive, Session(
                id="filter-child",
                agent=Agent.CLAUDE,
                title="Filter Child",
                parent_id="filter-parent",
                messages=[
                    Message(role="user", text="Continue."),
                    Message(role="assistant", text="Open question: should we defer cache eviction?"),
                ],
            ))
            report = build_family_digest(
                archive,
                "filter-child",
                signal_kinds=["open_question"],
                pin_signal_kinds=["open_question"],
                max_signals=8,
                max_pin_suggestions=8,
            )
            kinds = {signal["kind"] for member in report["members"] for signal in member["signals"]}
            self.assertEqual(kinds, {"open_question"})
            pin_kinds = {item["kind"] for item in report["pin_suggestions"]}
            self.assertEqual(pin_kinds, {"open_question"})
            strict = build_family_digest(
                archive,
                "filter-child",
                signal_kinds=["scope_boundary", "open_question"],
                pin_signal_kinds=["scope_boundary", "open_question"],
                min_signal_priority=100,
                max_signals=8,
                max_pin_suggestions=8,
            )
            strict_kinds = {signal["kind"] for member in strict["members"] for signal in member["signals"]}
            self.assertEqual(strict_kinds, {"scope_boundary"})


if __name__ == "__main__":
    unittest.main()
