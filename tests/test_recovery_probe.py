import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from examples.recovery_archive_probe import evaluate, validate_editor


class RecoveryArchiveProbeTests(unittest.TestCase):
    def test_unpinned_editor_refused_before_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            editor = Path(temporary) / 'apply_patch'
            editor.write_text('#!/bin/sh\necho untrusted\n')
            with patch('examples.recovery_archive_probe.subprocess.run') as run:
                with self.assertRaisesRegex(ValueError, 'execution refused'):
                    validate_editor(editor)
                run.assert_not_called()

    def test_incomplete_source_rejected_before_runtime_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch('examples.recovery_archive_probe.subprocess.run') as run:
                with self.assertRaises(ValueError):
                    evaluate(Path(temporary), Path(temporary) / 'untrusted-runtime')
                run.assert_not_called()


@unittest.skipUnless(shutil.which('node'), 'Optional comparison probe needs Node')
class RecoveryProbeTests(unittest.TestCase):
    def test_unpinned_source_is_rejected_before_import(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            marker = root / 'executed'
            source = root / 'untrusted.mjs'
            source.write_text("import { writeFileSync } from 'node:fs';\nwriteFileSync(new URL('./executed', import.meta.url), 'executed');\n")
            probe = Path(__file__).resolve().parents[1] / 'examples/recovery_patch_probe.mjs'
            result = subprocess.run([shutil.which('node'), str(probe), str(source)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('import refused', result.stderr)
            self.assertFalse(marker.exists())
