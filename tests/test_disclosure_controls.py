import unittest
from types import SimpleNamespace

from examples.compare_disclosure_matching import added_runs, bind_fragment, compact_matches, literal_windows, normalized_spans, normalize


class CompactMatchTests(unittest.TestCase):
    def test_literal_baseline_enumerates_overlapping_repeated_occurrences(self):
        hits = literal_windows({'s': 'aaaa'}, 'aaaa', window=3)
        self.assertEqual({(h.doc_position, h.scan_position) for h in hits}, {(0, 0), (0, 1), (1, 0), (1, 1)})

    def test_literal_baseline_does_not_join_independent_runs(self):
        self.assertFalse(literal_windows({'s': 'alpha beta'}, 'alpha', window=8))
        self.assertFalse(literal_windows({'s': 'alpha beta'}, ' beta', window=8))
        self.assertTrue(literal_windows({'s': 'alpha beta'}, 'alpha beta', window=8))

    @staticmethod
    def hit(doc, source, candidate, length):
        return SimpleNamespace(doc_id=doc, doc_position=source, scan_position=candidate, fragment_length=length)

    def test_overlapping_windows_preserve_union(self):
        hits = [self.hit('s', 0, 0, 7), self.hit('s', 3, 3, 7)]
        findings = compact_matches({'s': 'alpha beta'}, 'ALPHA BETA', hits)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]['windows'], 2)
        self.assertEqual((findings[0]['source']['char_start'], findings[0]['source']['char_end']), (0, 10))

    def test_source_occurrences_and_candidate_occurrences_remain_separate(self):
        text = 'alpha beta\n\nalpha beta'
        findings = compact_matches({'s': text}, text, [self.hit('s', 0, 0, 10), self.hit('s', 11, 0, 10), self.hit('s', 0, 11, 10)])
        self.assertEqual(len(findings), 3)
        self.assertEqual({(f['source']['line_start'], f['candidate']['line_start']) for f in findings}, {(1, 1), (3, 1), (1, 3)})

    def test_gap_and_different_documents_do_not_merge(self):
        findings = compact_matches({'a': 'alpha beta', 'b': 'alpha beta'}, 'alpha beta',
            [self.hit('a', 0, 0, 3), self.hit('a', 7, 7, 3), self.hit('b', 0, 0, 3)])
        self.assertEqual(len(findings), 3)

    def test_invalid_window_is_not_hidden_by_valid_merged_span(self):
        with self.assertRaises(ValueError):
            compact_matches({'s': 'alpha beta'}, 'alpha beta', [self.hit('s', 0, 0, 10), self.hit('s', 1, 2, 2)])


class CitationTests(unittest.TestCase):
    def test_whitespace_coordinates_recover_original_lines(self):
        raw = '\n\tAlpha \t\n BETA\n'
        anchor = bind_fragment(raw, 'alpha beta', 0, 0, 10)
        source = anchor['source']
        self.assertEqual(raw[source['char_start']:source['char_end']], 'Alpha \t\n BETA')
        self.assertEqual((source['line_start'], source['line_end']), (2, 3))

    def test_repeated_fragment_keeps_selected_occurrence(self):
        raw = 'alpha beta\n\nalpha beta'
        source = bind_fragment(raw, 'alpha beta', 11, 0, 10)['source']
        self.assertEqual(source['char_start'], 12)
        self.assertEqual(source['line_start'], 3)

    def test_unicode_expansion_and_contextual_case(self):
        raw = 'İ ΟΣ 🧭'
        text, spans = normalized_spans(raw)
        self.assertEqual(text, normalize(raw))
        self.assertEqual(spans[:2], [(0, 1), (0, 1)])
        self.assertTrue(bind_fragment(raw, raw, 0, 0, len(text))['verified'])
        with self.assertRaises(ValueError):
            bind_fragment(raw, raw, 0, 0, 1)

    def test_mismatch_and_invalid_coordinates_are_rejected(self):
        for position, length in [(-1, 2), (0, 0), (0, 100), (True, 2)]:
            with self.assertRaises(ValueError):
                bind_fragment('alpha', 'alpha', position, 0, length)
        with self.assertRaises(ValueError):
            bind_fragment('alpha', 'omega', 0, 0, 5)

    def test_window_can_end_at_collapsed_whitespace(self):
        source = bind_fragment('alpha \t beta', 'alpha beta', 0, 0, 6)['source']
        self.assertEqual(source['char_end'], 8)


class AddedRunTests(unittest.TestCase):
    def test_context_removals_hunks_and_files_separate_runs(self):
        patch = '''diff --git a/a.md b/a.md
--- a/a.md
+++ b/a.md
@@ -1,3 +1,3 @@
 unchanged
-removed
+replacement
 context
@@ -10 +10,2 @@
 old
+later
diff --git a/b.md b/b.md
--- a/b.md
+++ b/b.md
@@ -0,0 +1 @@
+other file
'''
        runs = added_runs(patch)
        self.assertEqual([(r['path'], r['start_line'], r['end_line'], r['diff_lines']) for r in runs], [
            ('a.md', 2, 2, ['replacement']),
            ('a.md', 11, 11, ['later']),
            ('b.md', 1, 1, ['other file']),
        ])

    def test_header_like_content_and_no_final_newline(self):
        patch = '''diff --git a/a.md b/a.md
--- a/a.md
+++ b/a.md
@@ -0,0 +1,2 @@
+++ b/not-a-header
+@@ content
\\ No newline at end of file'''
        self.assertEqual(added_runs(patch), [dict(path='a.md', start_line=1, end_line=2,
            diff_lines=['++ b/not-a-header', '@@ content'])])

    def test_deleted_file_has_no_added_text(self):
        self.assertEqual(added_runs('''diff --git a/a.md b/a.md
--- a/a.md
+++ /dev/null
@@ -1 +0,0 @@
-removed
'''), [])
