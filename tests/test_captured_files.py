"""Synthetic captured-file recovery; no developer histories or paths."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agent_sessions.analysis.captured_files import recover_captured_adds
from agent_sessions.cli import main


class CapturedFileTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source_root = self.root / "historical-project"
        self.source_root.mkdir()
        self.source = self.root / "rollout.jsonl"
        self.output = self.root / "private-output"

    def write(self, calls):
        rows = [dict(type="session_meta", payload=dict(id="synthetic-captured")), *calls]
        self.source.write_text("".join(json.dumps(row) + "\n" for row in rows))

    def call(self, name, value, call_id="call-1"):
        return dict(type="response_item", payload=dict(
            type="custom_tool_call", name=name, call_id=call_id, input=value))

    def result(self, call_id, output=None, is_error=None):
        payload = dict(type="custom_tool_call_output", call_id=call_id, output=output or {})
        if is_error is not None:
            payload["is_error"] = is_error
        return dict(type="response_item", payload=payload)

    def test_nested_literal_recovers_multiple_files_without_execution_claim(self):
        first = self.source_root / "pkg" / "first.py"
        second = self.source_root / "pkg" / "second.py"
        patch_text = (f"*** Begin Patch\n*** Add File: {first}\n+VALUE = 1\n"
                      f"*** Add File: {second}\n+VALUE = 2\n*** End Patch")
        wrapper = "text(await tools.apply_patch(" + json.dumps(patch_text) + "));"
        self.write([self.call("exec", wrapper)])
        with patch("agent_sessions.analysis.captured_files._private_root", side_effect=lambda p: Path(p).resolve()):
            report = recover_captured_adds(self.source, self.source_root, self.output)
        self.assertEqual((self.output / "pkg" / "first.py").read_text(), "VALUE = 1\n")
        self.assertEqual((self.output / "pkg" / "second.py").read_text(), "VALUE = 2\n")
        self.assertEqual({f["origin"] for f in report["files"]}, {"nested_literal"})
        self.assertTrue(all(f["execution_status"] == "unknown" for f in report["files"]))
        self.assertFalse(report["execution_verified"])
        self.assertFalse(report["latest_state_verified"])

    def test_direct_patch_and_json_object_input_are_supported(self):
        target = self.source_root / "direct.txt"
        patch_text = f"*** Begin Patch\n*** Add File: {target}\n+captured\n*** End Patch\n"
        self.write([self.call("apply_patch", dict(patch=patch_text))])
        with patch("agent_sessions.analysis.captured_files._private_root", side_effect=lambda p: Path(p).resolve()):
            report = recover_captured_adds(self.source, self.source_root, self.output)
        self.assertEqual((self.output / "direct.txt").read_text(), "captured\n")
        self.assertEqual(report["files"][0]["origin"], "direct_call")
        self.assertEqual(report["files"][0]["current_status"], "missing")
        self.assertEqual(report["current_comparison"]["missing"], 1)

    def test_current_comparison_prioritizes_matching_and_changed_files(self):
        matching = self.source_root / "matching.txt"
        changed = self.source_root / "changed.txt"
        matching.write_text("same\n")
        changed.write_text("now\n")
        one = f"*** Begin Patch\n*** Add File: {matching}\n+same\n*** End Patch\n"
        two = f"*** Begin Patch\n*** Add File: {changed}\n+before\n*** End Patch\n"
        self.write([self.call("apply_patch", one, "one"), self.call("apply_patch", two, "two")])
        with patch("agent_sessions.analysis.captured_files._private_root", side_effect=lambda p: Path(p).resolve()):
            report = recover_captured_adds(self.source, self.source_root, self.output)
        statuses = {item["path"]: item["current_status"] for item in report["files"]}
        self.assertEqual(statuses, {"changed.txt": "different", "matching.txt": "matching"})
        self.assertEqual(report["current_comparison"]["matching"], 1)
        self.assertEqual(report["current_comparison"]["different"], 1)

    def test_absent_historical_root_can_be_recovered(self):
        target = self.source_root / "deleted-project.txt"
        patch_text = f"*** Begin Patch\n*** Add File: {target}\n+recovered\n*** End Patch\n"
        self.write([self.call("apply_patch", patch_text)])
        self.source_root.rmdir()
        with patch("agent_sessions.analysis.captured_files._private_root", side_effect=lambda p: Path(p).resolve()):
            report = recover_captured_adds(self.source, self.source_root, self.output)
        self.assertEqual((self.output / "deleted-project.txt").read_text(), "recovered\n")
        self.assertFalse(report["source_root_exists"])
        self.assertEqual(report["current_comparison"]["missing"], 1)

    def test_existing_non_directory_source_root_is_refused(self):
        self.source_root.rmdir()
        self.source_root.write_text("not a directory\n")
        self.write([])
        with patch("agent_sessions.analysis.captured_files._private_root", side_effect=lambda p: Path(p).resolve()):
            with self.assertRaisesRegex(ValueError, "directory or an absent"):
                recover_captured_adds(self.source, self.source_root, self.output)

    def test_update_is_applied_only_to_a_captured_exact_base(self):
        target = self.source_root / "updated.txt"
        add = f"*** Begin Patch\n*** Add File: {target}\n+alpha\n+beta\n*** End Patch\n"
        update = (f"*** Begin Patch\n*** Update File: {target}\n@@\n alpha\n-beta\n+gamma\n"
                  "*** End Patch\n")
        self.write([self.call("apply_patch", add, "add"), self.call("apply_patch", update, "update")])
        with patch("agent_sessions.analysis.captured_files._private_root", side_effect=lambda p: Path(p).resolve()):
            report = recover_captured_adds(self.source, self.source_root, self.output)
        self.assertEqual((self.output / "updated.txt").read_text(), "alpha\ngamma\n")
        self.assertEqual(report["exact_updates_applied"], 1)
        self.assertEqual(report["files"][0]["update_count"], 1)

    def test_ordered_sources_continue_an_exact_file_history(self):
        target = self.source_root / "resumed.txt"
        add = f"*** Begin Patch\n*** Add File: {target}\n+before\n*** End Patch\n"
        update = (f"*** Begin Patch\n*** Update File: {target}\n@@\n-before\n+after\n*** End Patch\n")
        self.write([self.call("apply_patch", add, "first")])
        second = self.root / "resumed.jsonl"
        first_rows = [dict(type="session_meta", timestamp="2026-01-01T00:00:00+00:00",
                           payload=dict(id="synthetic-captured")),
                      dict(self.call("apply_patch", add, "first"), timestamp="2026-01-01T00:00:01+00:00")]
        self.source.write_text("".join(json.dumps(row) + "\n" for row in first_rows))
        rows = [dict(type="session_meta", timestamp="2026-01-01T00:01:00+00:00",
                     payload=dict(id="synthetic-resumed")),
                dict(self.call("apply_patch", update, "second"), timestamp="2026-01-01T00:01:01+00:00")]
        second.write_text("".join(json.dumps(row) + "\n" for row in rows))
        with patch("agent_sessions.analysis.captured_files._private_root", side_effect=lambda p: Path(p).resolve()):
            report = recover_captured_adds([self.source, second], self.source_root, self.output)
        self.assertEqual((self.output / "resumed.txt").read_text(), "after\n")
        self.assertEqual(report["exact_updates_applied"], 1)
        self.assertEqual(report["files"][0]["source_number"], 2)
        self.assertEqual(len(report["sources"]), 2)
        self.assertIsNone(report["source"])
        self.assertTrue(report["chronology_verified"])

    def test_duplicate_source_is_refused(self):
        self.write([])
        with patch("agent_sessions.analysis.captured_files._private_root", side_effect=lambda p: Path(p).resolve()):
            with self.assertRaisesRegex(ValueError, "distinct"):
                recover_captured_adds([self.source, self.source], self.source_root, self.output)

    def test_multiple_sources_without_verifiable_chronology_are_refused(self):
        self.write([])
        second = self.root / "second.jsonl"
        second.write_text(json.dumps(dict(type="session_meta", payload=dict(id="second"))) + "\n")
        with patch("agent_sessions.analysis.captured_files._private_root", side_effect=lambda p: Path(p).resolve()):
            with self.assertRaisesRegex(ValueError, "require captured timestamps"):
                recover_captured_adds([self.source, second], self.source_root, self.output)

    def test_directory_discovers_only_timestamped_sources_for_selected_root(self):
        archive = self.root / "raw"
        archive.mkdir()
        target = self.source_root / "auto.txt"
        add = f"*** Begin Patch\n*** Add File: {target}\n+before\n*** End Patch\n"
        update = f"*** Begin Patch\n*** Update File: {target}\n@@\n-before\n+after\n*** End Patch\n"
        def write_source(path, timestamp, operation, cwd):
            rows = [dict(type="session_meta", timestamp=timestamp, payload=dict(id="synthetic", cwd=str(cwd))),
                    dict(self.call("apply_patch", operation), timestamp=timestamp)]
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        write_source(archive / "first.jsonl", "2026-01-01T00:00:00+00:00", add, self.source_root)
        write_source(archive / "second.jsonl", "2026-01-01T00:01:00+00:00", update, self.source_root)
        other = self.root / "other"
        other.mkdir()
        unrelated = f"*** Begin Patch\n*** Add File: {other / 'skip.txt'}\n+skip\n*** End Patch\n"
        write_source(archive / "other.jsonl", "2026-01-01T00:02:00+00:00", unrelated, other)
        with patch("agent_sessions.analysis.captured_files._private_root", side_effect=lambda p: Path(p).resolve()):
            report = recover_captured_adds(archive, self.source_root, self.output)
        self.assertEqual((self.output / "auto.txt").read_text(), "after\n")
        self.assertEqual(report["source_discovery"],
                         {"mode": "directory", "files_scanned": 3, "relevant_sources": 2})
        self.assertEqual(report["exact_updates_applied"], 1)

    def test_relative_path_uses_captured_subdirectory_cwd(self):
        subdirectory = self.source_root / "pkg"
        subdirectory.mkdir()
        patch_text = "*** Begin Patch\n*** Add File: module.py\n+VALUE = 1\n*** End Patch\n"
        rows = [dict(type="session_meta", payload=dict(id="synthetic", cwd=str(subdirectory))),
                self.call("apply_patch", patch_text)]
        self.source.write_text("".join(json.dumps(row) + "\n" for row in rows))
        with patch("agent_sessions.analysis.captured_files._private_root", side_effect=lambda p: Path(p).resolve()):
            recover_captured_adds(self.source, self.source_root, self.output)
        self.assertEqual((self.output / "pkg" / "module.py").read_text(), "VALUE = 1\n")
        self.assertFalse((self.output / "module.py").exists())

    def test_update_without_captured_base_is_not_reconstructed(self):
        target = self.source_root / "unknown.txt"
        update = (f"*** Begin Patch\n*** Update File: {target}\n@@\n-old\n+new\n*** End Patch\n")
        added = self.source_root / "safe.txt"
        add = f"*** Begin Patch\n*** Add File: {added}\n+safe\n*** End Patch\n"
        self.write([self.call("apply_patch", update, "update"), self.call("apply_patch", add, "add")])
        with patch("agent_sessions.analysis.captured_files._private_root", side_effect=lambda p: Path(p).resolve()):
            report = recover_captured_adds(self.source, self.source_root, self.output)
        self.assertFalse((self.output / "unknown.txt").exists())
        self.assertEqual(report["blocked_update_paths"], 1)

    def test_ambiguous_update_keeps_captured_base_and_reports_block(self):
        target = self.source_root / "ambiguous.txt"
        add = f"*** Begin Patch\n*** Add File: {target}\n+same\n+same\n*** End Patch\n"
        update = (f"*** Begin Patch\n*** Update File: {target}\n@@\n-same\n+changed\n*** End Patch\n")
        self.write([self.call("apply_patch", add, "add"), self.call("apply_patch", update, "update")])
        with patch("agent_sessions.analysis.captured_files._private_root", side_effect=lambda p: Path(p).resolve()):
            report = recover_captured_adds(self.source, self.source_root, self.output)
        self.assertEqual((self.output / "ambiguous.txt").read_text(), "same\nsame\n")
        self.assertEqual(report["exact_updates_applied"], 0)
        self.assertEqual(report["blocked_update_paths"], 1)
        self.assertEqual(report["files"][0]["status"], "captured_prefix")
        self.assertEqual(report["files"][0]["update_status"], "blocked")

    def test_later_add_resets_an_earlier_missing_base(self):
        target = self.source_root / "reset.txt"
        early = (f"*** Begin Patch\n*** Update File: {target}\n@@\n-old\n+ignored\n*** End Patch\n")
        add = f"*** Begin Patch\n*** Add File: {target}\n+old\n*** End Patch\n"
        later = (f"*** Begin Patch\n*** Update File: {target}\n@@\n-old\n+recovered\n*** End Patch\n")
        self.write([self.call("apply_patch", early, "early"), self.call("apply_patch", add, "add"),
                    self.call("apply_patch", later, "later")])
        with patch("agent_sessions.analysis.captured_files._private_root", side_effect=lambda p: Path(p).resolve()):
            report = recover_captured_adds(self.source, self.source_root, self.output)
        self.assertEqual((self.output / "reset.txt").read_text(), "recovered\n")
        self.assertEqual(report["files"][0]["status"], "captured_bytes")
        self.assertEqual(report["exact_updates_applied"], 1)

    def test_captured_delete_removes_output_and_records_tombstone(self):
        target = self.source_root / "removed.txt"
        add = f"*** Begin Patch\n*** Add File: {target}\n+temporary\n*** End Patch\n"
        delete = f"*** Begin Patch\n*** Delete File: {target}\n*** End Patch\n"
        self.write([self.call("apply_patch", add, "add"), self.call("apply_patch", delete, "delete")])
        with patch("agent_sessions.analysis.captured_files._private_root", side_effect=lambda p: Path(p).resolve()):
            report = recover_captured_adds(self.source, self.source_root, self.output)
        self.assertFalse((self.output / "removed.txt").exists())
        self.assertEqual(report["files"], [])
        self.assertEqual(report["deleted_files"][0]["path"], "removed.txt")
        self.assertEqual(report["deleted_files"][0]["status"], "captured_deletion")
        self.assertFalse(report["execution_verified"])

    def test_confirmed_results_apply_success_and_skip_failure(self):
        target = self.source_root / "receipts.txt"
        add = f"*** Begin Patch\n*** Add File: {target}\n+base\n*** End Patch\n"
        failed = f"*** Begin Patch\n*** Update File: {target}\n@@\n-base\n+wrong\n*** End Patch\n"
        self.write([self.call("apply_patch", add, "add"), self.result("add", is_error=False),
                    self.call("apply_patch", failed, "failed"),
                    self.result("failed", output={"exit_code": 1})])
        with patch("agent_sessions.analysis.captured_files._private_root", side_effect=lambda p: Path(p).resolve()):
            report = recover_captured_adds(self.source, self.source_root, self.output)
        self.assertEqual((self.output / "receipts.txt").read_text(), "base\n")
        self.assertEqual(report["files"][0]["execution_status"], "confirmed_success")
        self.assertEqual(report["files"][0]["result_line"], 3)
        self.assertEqual(report["files"][0]["result_status"], "confirmed_success")
        self.assertEqual(report["files"][0]["result_evidence"], "linked")
        self.assertEqual(report["failed_operations_skipped"], 1)
        self.assertEqual(report["skipped_operations"][0]["result_line"], 5)
        self.assertEqual(report["skipped_operations"][0]["reason"], "captured_result_failed")
        self.assertTrue(report["execution_verified"])

    def test_conflicting_duplicate_results_are_ambiguous(self):
        target = self.source_root / "duplicate-result.txt"
        add = f"*** Begin Patch\n*** Add File: {target}\n+value\n*** End Patch\n"
        self.write([self.call("apply_patch", add, "same-id"),
                    self.result("same-id", is_error=False),
                    self.result("same-id", output={"exit_code": 1})])
        with patch("agent_sessions.analysis.captured_files._private_root", side_effect=lambda p: Path(p).resolve()):
            report = recover_captured_adds(self.source, self.source_root, self.output)
        self.assertEqual(report["files"][0]["execution_status"], "unknown")
        self.assertEqual(report["files"][0]["result_status"], "unknown")
        self.assertEqual(report["files"][0]["result_evidence"], "ambiguous")
        self.assertIsNone(report["files"][0]["result_line"])
        self.assertFalse(report["execution_verified"])

    def test_outer_executor_success_does_not_certify_nested_patch(self):
        target = self.source_root / "structured.txt"
        add = f"*** Begin Patch\n*** Add File: {target}\n+ok\n*** End Patch\n"
        structured = [{"type": "text", "text": "Script completed\nWall time 0.1 seconds"},
                      {"type": "text", "text": '{"exit_code":0}'}]
        self.write([self.call("exec", "text(await tools.apply_patch(" + json.dumps(add) + "));", "wrapped"),
                    self.result("wrapped", output=structured)])
        with patch("agent_sessions.analysis.captured_files._private_root", side_effect=lambda p: Path(p).resolve()):
            report = recover_captured_adds(self.source, self.source_root, self.output)
        self.assertEqual(report["files"][0]["execution_status"], "unknown")
        self.assertEqual(report["files"][0]["result_evidence"], "nested_call")
        self.assertFalse(report["execution_verified"])

    def test_variable_patch_is_not_executed_or_recovered(self):
        self.write([self.call("exec", "text(await tools.apply_patch(dynamicPatch));")])
        with patch("agent_sessions.analysis.captured_files._private_root", side_effect=lambda p: Path(p).resolve()):
            with self.assertRaisesRegex(ValueError, "No complete literal"):
                recover_captured_adds(self.source, self.source_root, self.output)
        self.assertFalse(self.output.exists())

    def test_absolute_outside_root_is_skipped_and_relative_escape_is_refused(self):
        outside = self.root / "outside.txt"
        outside_patch = f"*** Begin Patch\n*** Add File: {outside}\n+x\n*** End Patch\n"
        self.write([self.call("apply_patch", outside_patch)])
        with patch("agent_sessions.analysis.captured_files._private_root", side_effect=lambda p: Path(p).resolve()):
            with self.assertRaisesRegex(ValueError, "No complete literal"):
                recover_captured_adds(self.source, self.source_root, self.output)
        escape_patch = "*** Begin Patch\n*** Add File: ../outside.txt\n+x\n*** End Patch\n"
        self.write([self.call("apply_patch", escape_patch)])
        with patch("agent_sessions.analysis.captured_files._private_root", side_effect=lambda p: Path(p).resolve()):
            with self.assertRaisesRegex(ValueError, "escapes"):
                recover_captured_adds(self.source, self.source_root, self.output)
        self.assertFalse(self.output.exists())

    def test_conflicting_bytes_are_refused_before_output(self):
        target = self.source_root / "same.txt"
        one = f"*** Begin Patch\n*** Add File: {target}\n+one\n*** End Patch\n"
        two = f"*** Begin Patch\n*** Add File: {target}\n+two\n*** End Patch\n"
        self.write([self.call("apply_patch", one, "one"), self.call("apply_patch", two, "two")])
        with patch("agent_sessions.analysis.captured_files._private_root", side_effect=lambda p: Path(p).resolve()):
            with self.assertRaisesRegex(ValueError, "Conflicting"):
                recover_captured_adds(self.source, self.source_root, self.output)
        self.assertFalse(self.output.exists())

    def test_existing_output_is_never_overwritten(self):
        target = self.source_root / "file.txt"
        patch_text = f"*** Begin Patch\n*** Add File: {target}\n+value\n*** End Patch\n"
        self.write([self.call("apply_patch", patch_text)])
        self.output.mkdir()
        sentinel = self.output / "keep.txt"
        sentinel.write_text("keep\n")
        with patch("agent_sessions.analysis.captured_files._private_root", side_effect=lambda p: Path(p).resolve()):
            with self.assertRaisesRegex(Exception, "new private"):
                recover_captured_adds(self.source, self.source_root, self.output)
        self.assertEqual(sentinel.read_text(), "keep\n")

    def test_cli_writes_private_json_report(self):
        target = self.source_root / "cli.txt"
        patch_text = f"*** Begin Patch\n*** Add File: {target}\n+cli\n*** End Patch\n"
        self.write([self.call("apply_patch", patch_text)])
        argv = ["agent-sessions", "restore", str(self.source), "--source-root",
                str(self.source_root), "-o", str(self.output), "--json"]
        stdout = io.StringIO()
        with patch("sys.argv", argv), contextlib.redirect_stdout(stdout):
            main()
        report = json.loads(stdout.getvalue())
        self.assertEqual(report["files"][0]["path"], "cli.txt")
        self.assertEqual((self.output / "cli.txt").read_text(), "cli\n")
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.output / "cli.txt").stat().st_mode & 0o777, 0o600)
