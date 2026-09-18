from __future__ import annotations

import unittest

from x_bookmark.classify import classify_heuristic


class ClassifyTests(unittest.TestCase):
    def test_ai(self) -> None:
        c = classify_heuristic(
            {"text": "[FIXTURE] Large language models and GPT-style evals for AI agents."}
        )
        self.assertEqual(c.doc, "AI")
        self.assertIn("AI", c.topics)
        self.assertGreaterEqual(c.confidence, 60)

    def test_fashion(self) -> None:
        c = classify_heuristic(
            {
                "text": "[FIXTURE] Runway couture and streetwear outfit notes from fashion week."
            }
        )
        self.assertEqual(c.doc, "Fashion")

    def test_markets(self) -> None:
        c = classify_heuristic(
            {
                "text": "[FIXTURE] Nasdaq and S&P futures, Fed rates, and bitcoin ETF flows."
            }
        )
        self.assertEqual(c.doc, "Markets")

    def test_career(self) -> None:
        c = classify_heuristic(
            {
                "text": "[FIXTURE] Hiring loop, resume rewrite, and interview prep for a staff role."
            }
        )
        self.assertEqual(c.doc, "Career")

    def test_media(self) -> None:
        c = classify_heuristic(
            {"text": "The newsroom journalist said the podcast newsletter dropped."}
        )
        self.assertEqual(c.doc, "Media")

    def test_misc(self) -> None:
        c = classify_heuristic({"text": "A cooking recipe for the travel day concert."})
        self.assertEqual(c.doc, "Misc")

    def test_needs_review_when_no_keywords(self) -> None:
        c = classify_heuristic({"text": "[FIXTURE] Noted for later."})
        self.assertEqual(c.doc, "needs-review")
        self.assertEqual(c.topics, ())
        self.assertLess(c.confidence, 60)

    def test_does_not_use_missing_text(self) -> None:
        c = classify_heuristic({"id": "1"})
        self.assertEqual(c.doc, "needs-review")

    def test_ai_word_boundary_does_not_match_email(self) -> None:
        c = classify_heuristic({"text": "please email the notes later"})
        self.assertEqual(c.doc, "needs-review")


if __name__ == "__main__":
    unittest.main()
