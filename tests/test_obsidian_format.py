from __future__ import annotations

import unittest

from x_bookmark.constants import ALL_DOC_NAMES, SOURCE
from x_bookmark.obsidian_format import (
    bookmark_note,
    index_note,
    sort_newest_first,
    topic_note,
)
from x_bookmark.records import to_record


def _rec(**overrides: object) -> dict:
    post = {
        "id": "1000000000000000001",
        "author": "fixture_ai",
        "created_at": "2026-09-16T15:51:31.000Z",
        "text": "[FIXTURE] Large language models and GPT-style evals for AI agents.",
    }
    rec = to_record(post)
    rec.update(overrides)
    return rec


class BookmarkNoteTests(unittest.TestCase):
    def test_frontmatter_and_verbatim_text(self) -> None:
        rec = _rec()
        note = bookmark_note(rec)
        self.assertTrue(note.startswith("---\n"))
        self.assertIn("url:", note)
        self.assertIn("https://x.com/fixture_ai/status/1000000000000000001", note)
        self.assertIn('author: "@fixture_ai"', note)
        self.assertIn('x_id: "1000000000000000001"', note)
        self.assertIn("saved_at:", note)
        self.assertIn("2026-09-16T15:51:31.000Z", note)
        self.assertIn("topics:", note)
        self.assertIn("- AI", note)
        self.assertIn(f"source: {SOURCE}", note)
        self.assertIn("[FIXTURE] Large language models and GPT-style evals for AI agents.", note)
        self.assertEqual(note.count("[FIXTURE] Large language models"), 1)


class SortAndMocTests(unittest.TestCase):
    def test_newer_saved_at_first(self) -> None:
        older = _rec(
            x_id="old",
            saved_at="2026-09-10T00:00:00.000Z",
            text="[FIXTURE] older",
        )
        newer = _rec(
            x_id="new",
            saved_at="2026-09-16T15:51:31.000Z",
            text="[FIXTURE] newer",
        )
        ordered = sort_newest_first([older, newer])
        self.assertEqual([r["x_id"] for r in ordered], ["new", "old"])
        moc = topic_note("AI", [older, newer])
        contents = moc.split("## Contents", 1)[1]
        self.assertLess(contents.find("new"), contents.find("old"))
        self.assertTrue(moc.strip().startswith("# AI"))
        glossary = moc.split("## Contents", 1)[0]
        self.assertIn("## Glossary", glossary)
        self.assertIn("[[Index]]", glossary)

    def test_index_starts_with_glossary_of_all_topics(self) -> None:
        text = index_note([])
        self.assertTrue(text.strip().startswith("# X Bookmarks"))
        self.assertIn("## Glossary", text)
        glossary = text.split("## Glossary", 1)[1]
        first_body_heading = glossary.find("\n## ")
        glossary_only = glossary if first_body_heading < 0 else glossary[:first_body_heading]
        for name in ALL_DOC_NAMES:
            self.assertIn(name, glossary_only)

    def test_empty_topic_still_has_glossary(self) -> None:
        moc = topic_note("Media", [])
        self.assertIn("## Glossary", moc)
        self.assertIn("## Contents", moc)

    def test_missing_saved_at_sorts_last(self) -> None:
        dated = _rec(x_id="dated", saved_at="2026-09-16T00:00:00.000Z")
        undated = _rec(x_id="undated", saved_at="")
        ordered = sort_newest_first([undated, dated])
        self.assertEqual([r["x_id"] for r in ordered], ["dated", "undated"])


if __name__ == "__main__":
    unittest.main()
