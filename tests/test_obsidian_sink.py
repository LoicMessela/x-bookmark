from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from tempfile import TemporaryDirectory

from x_bookmark.cli import main
from x_bookmark.constants import (
    ALL_DOC_NAMES,
    DEFAULT_DRIVE_FOLDER_ID,
    DEFAULT_OBSIDIAN_DRIVE_FOLDER_ID,
    IMPORT_INDEX_NAME,
    INDEX_NOTE_NAME,
    MARKDOWN_MIME,
)
from x_bookmark.sinks.drive_docs import FakeDriveClient
from x_bookmark.sync import sync


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "bookmarks.fixture.json"


class ObsidianDryRunTests(unittest.TestCase):
    def test_fixture_layout_toc_and_newest_first(self) -> None:
        with TemporaryDirectory() as tmp:
            plan = sync(FIXTURE, live=False, sink="obsidian", out_dir=tmp)
            self.assertEqual(plan["mode"], "dry-run")
            self.assertFalse(plan["drive_writes"])
            self.assertEqual(plan["imported"], 5)
            self.assertEqual(plan["sink"], "obsidian-markdown-on-drive")
            root = Path(tmp)
            index = (root / INDEX_NOTE_NAME).read_text(encoding="utf-8")
            self.assertTrue(index.strip().startswith("# X Bookmarks"))
            self.assertLess(index.find("## Glossary"), index.find("## Contents"))
            for name in ALL_DOC_NAMES:
                folder = root / name
                self.assertTrue(folder.is_dir(), name)
                moc = (folder / f"{name}.md").read_text(encoding="utf-8")
                self.assertTrue(moc.startswith(f"# {name}"))
                self.assertIn("## Glossary", moc)
                self.assertIn("## Contents", moc)
            ai_note = next((root / "AI").glob("2026-09-16-*.md"))
            body = ai_note.read_text(encoding="utf-8")
            self.assertIn("source: x-bookmark", body)
            self.assertIn("x_id:", body)
            self.assertIn("[FIXTURE] Large language models", body)
            stored = json.loads((root / IMPORT_INDEX_NAME).read_text(encoding="utf-8"))
            self.assertEqual(len(stored["imported_x_ids"]), 5)

    def test_second_dry_run_skips(self) -> None:
        with TemporaryDirectory() as tmp:
            first = sync(FIXTURE, live=False, sink="obsidian", out_dir=tmp)
            n_ai = len(list((Path(tmp) / "AI").glob("2026-*.md")))
            second = sync(FIXTURE, live=False, sink="obsidian", out_dir=tmp)
            self.assertEqual(first["imported"], 5)
            self.assertEqual(second["imported"], 0)
            self.assertEqual(second["skipped"], 5)
            self.assertEqual(len(list((Path(tmp) / "AI").glob("2026-*.md"))), n_ai)

    def test_new_post_lands_newest_in_topic_moc(self) -> None:
        with TemporaryDirectory() as tmp:
            sync(FIXTURE, live=False, sink="obsidian", out_dir=tmp)
            extra = {
                "count": 1,
                "posts": [
                    {
                        "id": "1000000000000000099",
                        "author": "fixture_ai_new",
                        "created_at": "2026-09-18T00:00:00.000Z",
                        "text": "[FIXTURE] Another GPT-style agent eval note.",
                    }
                ],
            }
            extra_path = Path(tmp) / "extra.json"
            extra_path.write_text(json.dumps(extra), encoding="utf-8")
            plan = sync(extra_path, live=False, sink="obsidian", out_dir=tmp)
            self.assertEqual(plan["imported"], 1)
            moc = (Path(tmp) / "AI" / "AI.md").read_text(encoding="utf-8")
            contents = moc.split("## Contents", 1)[1]
            self.assertLess(contents.find("1000000000000000099"), contents.find("1000000000000000001"))


class ObsidianLiveDriveTests(unittest.TestCase):
    def test_uploads_markdown_not_google_docs(self) -> None:
        client = FakeDriveClient(DEFAULT_OBSIDIAN_DRIVE_FOLDER_ID)
        client.files[DEFAULT_OBSIDIAN_DRIVE_FOLDER_ID]["name"] = "Obsidian Vault - X Bookmarks"
        plan = sync(
            FIXTURE,
            live=True,
            sink="obsidian",
            drive_client=client,
            obsidian_folder_id=DEFAULT_OBSIDIAN_DRIVE_FOLDER_ID,
        )
        self.assertTrue(plan["drive_writes"])
        self.assertEqual(plan["imported"], 5)
        self.assertEqual(plan["folder_id"], DEFAULT_OBSIDIAN_DRIVE_FOLDER_ID)
        self.assertNotEqual(plan["folder_id"], DEFAULT_DRIVE_FOLDER_ID)

        index_meta = client.find_file(DEFAULT_OBSIDIAN_DRIVE_FOLDER_ID, INDEX_NOTE_NAME)
        self.assertIsNotNone(index_meta)
        assert index_meta is not None
        self.assertEqual(index_meta["mimeType"], MARKDOWN_MIME)
        self.assertNotIn("vnd.google-apps.document", index_meta["mimeType"])
        text = client.download_text(index_meta["id"])
        self.assertIn("## Glossary", text)

        ai_folder = client.find_file(DEFAULT_OBSIDIAN_DRIVE_FOLDER_ID, "AI")
        self.assertIsNotNone(ai_folder)
        assert ai_folder is not None
        self.assertEqual(ai_folder["mimeType"], "application/vnd.google-apps.folder")
        md_files = [
            m
            for m in client.list_files(ai_folder["id"])
            if str(m.get("name") or "").endswith(".md")
        ]
        self.assertTrue(md_files)
        for meta in md_files:
            self.assertEqual(meta["mimeType"], MARKDOWN_MIME)
            if meta["name"] != "AI.md":
                self.assertIn("[FIXTURE]", client.download_text(meta["id"]))

        json_file = client.find_file(DEFAULT_OBSIDIAN_DRIVE_FOLDER_ID, IMPORT_INDEX_NAME)
        self.assertIsNotNone(json_file)
        assert json_file is not None
        stored = client.download_json(json_file["id"])
        self.assertEqual(len(stored["imported_x_ids"]), 5)

        second = sync(
            FIXTURE,
            live=True,
            sink="obsidian",
            drive_client=client,
            obsidian_folder_id=DEFAULT_OBSIDIAN_DRIVE_FOLDER_ID,
        )
        self.assertEqual(second["imported"], 0)
        self.assertEqual(second["skipped"], 5)


class ObsidianCliTests(unittest.TestCase):
    def test_obsidian_flag_matches_sink(self) -> None:
        with TemporaryDirectory() as tmp:
            rc_a = main(
                ["sync", "-i", str(FIXTURE), "--sink", "obsidian", "--out", tmp]
            )
            self.assertEqual(rc_a, 0)
            self.assertTrue((Path(tmp) / INDEX_NOTE_NAME).is_file())
        with TemporaryDirectory() as tmp:
            rc_b = main(["sync", "-i", str(FIXTURE), "--obsidian", "--out", tmp])
            self.assertEqual(rc_b, 0)
            self.assertTrue((Path(tmp) / INDEX_NOTE_NAME).is_file())

    def test_obsidian_and_sink_docs_conflict(self) -> None:
        err = io.StringIO()
        with redirect_stderr(err):
            rc = main(
                ["sync", "-i", str(FIXTURE), "--sink", "docs", "--obsidian"]
            )
        self.assertEqual(rc, 2)
        self.assertIn("--obsidian", err.getvalue())

    def test_default_sink_is_docs_jsonl(self) -> None:
        with TemporaryDirectory() as tmp:
            plan_rc = main(["sync", "-i", str(FIXTURE), "--out", tmp])
            self.assertEqual(plan_rc, 0)
            self.assertTrue((Path(tmp) / "records.jsonl").is_file())
            self.assertFalse((Path(tmp) / INDEX_NOTE_NAME).exists())


if __name__ == "__main__":
    unittest.main()
