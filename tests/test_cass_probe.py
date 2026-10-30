"""The public comparison fixtures stay synthetic and retain their tool fields."""

import tempfile
import unittest
from pathlib import Path

from examples.compare_cass_importer import compare, fixtures
from agent_sessions.parsers.codex import CodexParser
from agent_sessions.parsers.cursor import CursorParser
from agent_sessions.renderers.markdown import MarkdownRenderer


class CassProbeTests(unittest.TestCase):
    def test_native_fixture_fields_survive_our_export(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths, markers = fixtures(Path(temporary))
            rendered = []
            for agent, parser in (('codex', CodexParser), ('cursor', CursorParser)):
                session = parser.parse(paths[agent])
                rendered.append(MarkdownRenderer.render(session))
            for marker in markers:
                self.assertIn(marker, '\n'.join(rendered))
            self.assertIn('[is_error: true]', rendered[1])
            self.assertEqual(len(markers), len(set(markers)))

    def test_unpinned_binary_is_rejected_before_execution_or_output_creation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            binary = root / 'unknown-binary'
            binary.write_bytes(b'not the verified release')
            with self.assertRaisesRegex(ValueError, 'release binary'):
                compare(binary, root / 'probe')
            self.assertFalse((root / 'probe').exists())


if __name__ == '__main__':
    unittest.main()
