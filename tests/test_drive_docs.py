from __future__ import annotations

import unittest
from pathlib import Path

from x_bookmark.docs_format import append_requests, section_body, section_heading
from x_bookmark.records import to_record
from x_bookmark.sinks.drive_docs import FakeDriveClient
from x_bookmark.sync import sync


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "bookmarks.fixture.json"


class DocsFormatTests(unittest.TestCase):
    def test_section_contains_required_fields_and_verbatim_text(self) -> None:
        rec = to_record(
            {
                "id": "42",
                "author": "fixture_ai",
                "created_at": "2026-09-16T15:51:31.000Z",
                "text": "[FIXTURE] hello from the export",
            }
        )
        body = section_body(rec)
        self.assertIn("x_id: 42", body)
        self.assertIn("author: @fixture_ai", body)
        self.assertIn("url: https://x.com/fixture_ai/status/42", body)
        self.assertIn("[FIXTURE] hello from the export", body)
        self.assertTrue(section_heading(rec).startswith("2026-09-16"))

    def test_append_requests_style_heading(self) -> None:
        rec = {
            "x_id": "1",
            "author": "@a",
            "saved_at": "2026-01-01T00:00:00.000Z",
            "url": "https://x.com/a/status/1",
            "topics": ["AI"],
            "confidence": 90,
            "source": "x-bookmark",
            "text": "[FIXTURE] x",
            "doc": "AI",
        }
        reqs = append_requests(rec, 1)
        self.assertEqual(reqs[0]["insertText"]["location"]["index"], 1)
        self.assertIn("[FIXTURE] x", reqs[0]["insertText"]["text"])
        self.assertEqual(
            reqs[1]["updateParagraphStyle"]["paragraphStyle"]["namedStyleType"],
            "HEADING_2",
        )


class FakeDriveSyncTests(unittest.TestCase):
    def test_live_path_appends_then_dedups(self) -> None:
        client = FakeDriveClient()
        first = sync(FIXTURE, live=True, drive_client=client)
        self.assertTrue(first["drive_writes"])
        self.assertEqual(first["imported"], 5)
        self.assertEqual(first["skipped"], 0)
        self.assertIn("AI", first["appended"])
        self.assertEqual(sum(first["appended"].values()), 5)

        ai_id = first["topic_docs"]["AI"]["id"]
        self.assertIn("[FIXTURE] Large language models", client.docs_text[ai_id])
        self.assertIn("_index", {meta["name"] for meta in client.files.values()})
        json_ids = [fid for fid, blob in client.json_blobs.items()]
        self.assertTrue(json_ids)
        stored = client.json_blobs[json_ids[0]]
        self.assertEqual(len(stored["imported_x_ids"]), 5)

        second = sync(FIXTURE, live=True, drive_client=client)
        self.assertEqual(second["imported"], 0)
        self.assertEqual(second["skipped"], 5)
        self.assertEqual(second.get("appended") or {}, {})

    def test_index_doc_lists_topics(self) -> None:
        client = FakeDriveClient()
        plan = sync(FIXTURE, live=True, drive_client=client)
        index_id = plan["index_doc"]["id"]
        text = client.docs_text[index_id]
        self.assertIn("X Bookmarks — index", text)
        self.assertIn("AI (", text)
        self.assertIn("needs-review (", text)


if __name__ == "__main__":
    unittest.main()
