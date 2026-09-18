from __future__ import annotations

import json
import unittest
from pathlib import Path

from x_bookmark.ingest import load_export, posts_from_payload
from x_bookmark.records import to_record, verbatim_text


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "bookmarks.fixture.json"


class IngestTests(unittest.TestCase):
    def test_fixture_shape(self) -> None:
        posts = load_export(FIXTURE)
        self.assertEqual(len(posts), 5)
        self.assertEqual(posts[0]["id"], "1000000000000000001")

    def test_raw_list_accepted(self) -> None:
        posts = posts_from_payload([{"id": "1", "text": "hi"}])
        self.assertEqual(posts[0]["id"], "1")

    def test_rejects_missing_posts(self) -> None:
        with self.assertRaises(ValueError):
            posts_from_payload({"count": 0})

    def test_rejects_missing_id(self) -> None:
        with self.assertRaises(ValueError):
            posts_from_payload([{"text": "no id"}])


class RecordTests(unittest.TestCase):
    def test_verbatim_text_only_from_input(self) -> None:
        post = {
            "id": "9",
            "author": "fixture_ai",
            "created_at": "2026-09-16T15:51:31.000Z",
            "text": "[FIXTURE] exact wording",
        }
        rec = to_record(post)
        self.assertEqual(rec["text"], "[FIXTURE] exact wording")
        self.assertEqual(rec["text"], verbatim_text(post))
        self.assertEqual(rec["author"], "@fixture_ai")
        self.assertEqual(rec["url"], "https://x.com/fixture_ai/status/9")
        self.assertEqual(rec["source"], "x-bookmark")
        self.assertEqual(rec["x_id"], "9")

    def test_missing_text_is_empty_not_invented(self) -> None:
        rec = to_record({"id": "8", "author": "x"})
        self.assertEqual(rec["text"], "")

    def test_roundtrip_fixture_texts(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        for post in payload["posts"]:
            rec = to_record(post)
            self.assertEqual(rec["text"], post["text"])
            self.assertTrue(rec["text"].startswith("[FIXTURE]"))


if __name__ == "__main__":
    unittest.main()
