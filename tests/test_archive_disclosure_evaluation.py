"""Regression controls for source-role filtering in the synthetic leak probe."""

import unittest

from examples.evaluate_archive_disclosure import _user_prompt_links, evaluate


class ArchiveDisclosureEvaluationTests(unittest.TestCase):
    def test_user_prompt_mode_removes_assistant_public_content_false_alerts(self):
        report = evaluate()
        cases = {case["case"]: case for case in report["cases"]}
        self.assertTrue(cases["private_exact_copy"]["user_prompt_overlap"])
        self.assertTrue(cases["private_case_and_spacing_change"]["user_prompt_overlap"])
        self.assertFalse(cases["public_shared_copy"]["user_prompt_overlap"])
        self.assertFalse(cases["public_code_copy"]["user_prompt_overlap"])
        self.assertFalse(cases["private_paraphrase"]["user_prompt_overlap"])
        self.assertFalse(report["matched_source_text_emitted"])

    def test_source_links_are_fingerprint_anchored_and_excerpt_free(self):
        report = evaluate()
        exact = next(case for case in report["cases"] if case["case"] == "private_exact_copy")
        links = exact["user_prompt_links"]
        self.assertEqual(len(links), 2)
        self.assertTrue(all(link["verified"] for link in links))
        self.assertTrue(all(link["candidate_path"] == "public.md" for link in links))
        self.assertTrue(all(link["staged_line_start"] == 2 for link in links))
        self.assertTrue(all("text" not in link and "excerpt" not in link for link in links))

    def test_linker_returns_no_match_for_reworded_prompt(self):
        sources = {"codex": [{"role": "user", "text": "Private note: Northstar support credit is 73%."}]}
        self.assertEqual(_user_prompt_links(
            "The customer receives a temporary discount until autumn review.", sources
        ), [])


if __name__ == "__main__":
    unittest.main()
