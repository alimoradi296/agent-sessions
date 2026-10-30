"""Compare wrapper-aware restoration with a transparent direct-call baseline."""

import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_sessions.analysis.captured_files import _direct_patches, _operations, recover_captured_adds


def evaluate():
    with tempfile.TemporaryDirectory(prefix="agent-sessions-public-restoration-") as temporary:
        root = Path(temporary)
        project = root / "synthetic-project"
        project.mkdir()
        source = root / "synthetic.jsonl"
        output = root / "private-output"

        wrapped_add = ("*** Begin Patch\n*** Add File: lost.py\n+VALUE = 1\n"
                       "*** Add File: helper.py\n+def helper():\n+    return 2\n*** End Patch\n")
        wrapped_update = ("*** Begin Patch\n*** Update File: lost.py\n@@\n-VALUE = 1\n"
                          "+VALUE = 7\n*** End Patch\n")
        direct_add = "*** Begin Patch\n*** Add File: visible.txt\n+visible\n*** End Patch\n"
        records = [
            {"type": "session_meta", "payload": {"id": "synthetic-public-restoration"}},
            {"type": "response_item", "payload": {"type": "custom_tool_call", "name": "exec",
             "call_id": "wrapped-add", "input": "text(await tools.apply_patch(" + json.dumps(wrapped_add) + "));"}},
            {"type": "response_item", "payload": {"type": "custom_tool_call", "name": "exec",
             "call_id": "wrapped-update", "input": "text(await tools.apply_patch(" + json.dumps(wrapped_update) + "));"}},
            {"type": "response_item", "payload": {"type": "custom_tool_call", "name": "apply_patch",
             "call_id": "direct-add", "input": direct_add}},
        ]
        source.write_text("".join(json.dumps(record) + "\n" for record in records))

        direct_files = set()
        for record in records:
            payload = record.get("payload", {})
            for patch in _direct_patches(payload.get("name", ""), payload.get("input", "")):
                for operation, path, _ in _operations(patch):
                    if operation == "add":
                        direct_files.add(path)

        report = recover_captured_adds(source, project, output)
        expected = {"lost.py": "VALUE = 7\n", "helper.py": "def helper():\n    return 2\n",
                    "visible.txt": "visible\n"}
        exact = all((output / path).read_text() == content for path, content in expected.items())
        return {
            "synthetic_only": True,
            "wrapper_aware_files": len(report["files"]),
            "direct_call_baseline_files": len(direct_files),
            "additional_files_recovered": len(report["files"]) - len(direct_files),
            "exact_updates_applied": report["exact_updates_applied"],
            "all_expected_bytes_match": exact,
            "current_comparison": report["current_comparison"],
            "archived_commands_executed": False,
            "limits": "Synthetic source-shape comparison; it does not establish adoption, exclusivity, or historical execution.",
        }


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2))
