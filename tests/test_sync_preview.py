from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from x_bookmark.constants import DEFAULT_DRIVE_FOLDER_ID, IMPORT_INDEX_NAME
from x_bookmark.sync import sync


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "bookmarks.fixture.json"


class PreviewDedupTests(unittest.TestCase):
    def test_first_dry_run_imports_all_fixture_posts(self) -> None:
        with TemporaryDirectory() as tmp:
            plan = sync(FIXTURE, live=False, out_dir=tmp)
            self.assertEqual(plan["mode"], "dry-run")
            self.assertFalse(plan["drive_writes"])
            self.assertEqual(plan["imported"], 5)
            self.assertEqual(plan["skipped"], 0)
            self.assertEqual(plan["folder_id"], DEFAULT_DRIVE_FOLDER_ID)

            records_path = Path(tmp) / "records.jsonl"
            lines = [json.loads(line) for line in records_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(lines), 5)
            docs = {row["doc"] for row in lines}
            self.assertEqual(docs, {"AI", "Fashion", "Markets", "Career", "needs-review"})
            for row in lines:
                self.assertTrue(row["text"].startswith("[FIXTURE]"))
                self.assertEqual(row["source"], "x-bookmark")

            index = json.loads((Path(tmp) / IMPORT_INDEX_NAME).read_text(encoding="utf-8"))
            self.assertEqual(len(index["imported_x_ids"]), 5)

    def test_second_dry_run_skips_already_imported_x_ids(self) -> None:
        with TemporaryDirectory() as tmp:
            first = sync(FIXTURE, live=False, out_dir=tmp)
            second = sync(FIXTURE, live=False, out_dir=tmp)
            self.assertEqual(first["imported"], 5)
            self.assertEqual(second["imported"], 0)
            self.assertEqual(second["skipped"], 5)
            records = (Path(tmp) / "records.jsonl").read_text(encoding="utf-8").strip()
            self.assertEqual(records, "")

    def test_new_post_is_imported_after_index_exists(self) -> None:
        with TemporaryDirectory() as tmp:
            sync(FIXTURE, live=False, out_dir=tmp)
            extra = {
                "count": 1,
                "posts": [
                    {
                        "id": "1000000000000000099",
                        "author": "fixture_media",
                        "created_at": "2026-09-18T00:00:00.000Z",
                        "text": "[FIXTURE] A journalist newsletter from the newsroom podcast.",
                    }
                ],
            }
            extra_path = Path(tmp) / "extra.json"
            extra_path.write_text(json.dumps(extra), encoding="utf-8")
            plan = sync(extra_path, live=False, out_dir=tmp)
            self.assertEqual(plan["imported"], 1)
            self.assertEqual(plan["skipped"], 0)
            self.assertEqual(plan["would_append"].get("Media"), 1)


if __name__ == "__main__":
    unittest.main()
