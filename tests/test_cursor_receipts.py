import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from examples.otel_hook_capture_probe import evaluate as evaluate_otel
from examples.otel_capture_delivery_probe import evaluate as evaluate_delivery

from examples.cursor_receipt_probe import evaluate, fixture_records


class CursorReceiptProbeTests(unittest.TestCase):
    def test_result_evidence_survives_without_inferred_success(self):
        result = evaluate()
        self.assertEqual([case['parsed_is_error'] for case in result['cases']], [None, None, True])
        self.assertTrue(all(case['result_preserved'] and case['searchable_with_source_coordinates']
                            for case in result['cases']))
        self.assertFalse(result['native_cursor_session_observed'])

    def test_missing_call_id_cannot_create_a_pair(self):
        with self.assertRaisesRegex(ValueError, 'do not invent pairing'):
            fixture_records(dict(hook_event_name='postToolUse', tool_name='Shell',
                                 tool_input={}, tool_output='{}'))

    @unittest.skipUnless(shutil.which('node'), 'Optional native probe needs Node')
    def test_unpinned_bundle_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            marker = root / 'executed'
            (root / 'index.js').write_text("require('node:fs').writeFileSync(" + json.dumps(str(marker)) + ", 'bad');")
            script = Path(__file__).resolve().parents[1] / 'examples/cursor_native_hook_probe.cjs'
            run = subprocess.run([shutil.which('node'), str(script), str(root)], capture_output=True, text=True)
            self.assertNotEqual(run.returncode, 0)
            self.assertIn('Unpinned bundle; import refused', run.stderr)
            self.assertFalse(marker.exists())


class ExistingCaptureSourceGuardTests(unittest.TestCase):
    def test_unpinned_source_refused_before_dependency_check_or_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ('enrichment_connectors.py', 'otel_hook.py', 'pyproject.toml'):
                (root / name).write_text('untrusted')
            with patch('examples.otel_hook_capture_probe.subprocess.run') as run:
                with self.assertRaisesRegex(ValueError, 'Unpinned source'):
                    evaluate_otel(root, root / 'untrusted-python')
                with self.assertRaisesRegex(ValueError, 'Unpinned source'):
                    evaluate_delivery(root, root / 'untrusted-python')
                run.assert_not_called()
