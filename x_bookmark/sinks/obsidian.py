"""Obsidian sink: Markdown vault on Google Drive (phone), dry-run locally.

Live uploads real ``.md`` files with mime ``text/markdown``. It never converts
them to Google Docs. Dry-run writes the same tree under ``vault-preview/``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, Union

from x_bookmark.constants import (
    ALL_DOC_NAMES,
    DEFAULT_OBSIDIAN_DRIVE_FOLDER_ID,
    DEFAULT_OBSIDIAN_DRIVE_FOLDER_URL,
    IMPORT_INDEX_NAME,
    INDEX_NOTE_NAME,
    MARKDOWN_MIME,
)
from x_bookmark.docs_format import filename_slug
from x_bookmark.import_index import (
    add_imported,
    empty_index,
    index_path,
    load_index_file,
    merge_index,
    write_index_file,
)
from x_bookmark.obsidian_format import (
    bookmark_note,
    index_note,
    parse_bookmark_note,
    topic_note,
)
from x_bookmark.sinks.drive_docs import DriveClient, FOLDER_MIME, GoogleDriveClient

PathLike = Union[str, Path]


def _folder_url(folder_id: str) -> str:
    if folder_id == DEFAULT_OBSIDIAN_DRIVE_FOLDER_ID:
        return DEFAULT_OBSIDIAN_DRIVE_FOLDER_URL
    return f"https://drive.google.com/drive/folders/{folder_id}"


class ObsidianSink:
    """Write Index.md + topic folders as Markdown. Drive live or local dry-run."""

    def __init__(
        self,
        *,
        folder_id: str = DEFAULT_OBSIDIAN_DRIVE_FOLDER_ID,
        out_dir: Optional[PathLike] = None,
        client: Optional[DriveClient] = None,
        live: bool = False,
    ) -> None:
        self.folder_id = folder_id
        self.folder_url = _folder_url(folder_id)
        self.out_dir = Path(out_dir) if out_dir is not None else None
        self.live = live
        self.client: Optional[DriveClient] = client
        if live and self.client is None:
            self.client = GoogleDriveClient()

    def load_index(self) -> dict[str, Any]:
        if self.live:
            assert self.client is not None
            found = self.client.find_file(self.folder_id, IMPORT_INDEX_NAME)
            if not found:
                return empty_index()
            return merge_index(empty_index(), self.client.download_json(found["id"]))
        if self.out_dir is None:
            return empty_index()
        return load_index_file(index_path(self.out_dir))

    def commit(
        self,
        records: Sequence[Mapping[str, Any]],
        index: dict[str, Any],
        *,
        skipped: int,
        already_imported: int,
    ) -> dict[str, Any]:
        existing = self._scan_existing()
        files, merged = build_vault_files(records, existing)

        counts = {name: len(merged.get(name) or []) for name in ALL_DOC_NAMES}
        for name in ALL_DOC_NAMES:
            slot = index.setdefault("topic_docs", {}).setdefault(
                name, {"id": None, "url": None, "count": 0}
            )
            slot["count"] = counts[name]

        if self.live:
            written = self._write_drive(files)
        else:
            written = self._write_local(files)

        new_index = add_imported(index, [str(r["x_id"]) for r in records])
        if self.live:
            assert self.client is not None
            self.client.upsert_json(self.folder_id, IMPORT_INDEX_NAME, new_index)
        else:
            assert self.out_dir is not None
            write_index_file(index_path(self.out_dir), new_index)

        would = {}
        for rec in records:
            doc = str(rec.get("doc") or "needs-review")
            would[doc] = would.get(doc, 0) + 1

        plan: dict[str, Any] = {
            "mode": "live" if self.live else "dry-run",
            "drive_writes": bool(self.live),
            "sink": "obsidian-markdown-on-drive",
            "folder_id": self.folder_id,
            "folder_url": self.folder_url,
            "imported": len(records),
            "skipped": skipped,
            "already_imported_in_index": already_imported,
            "markdown_mime": MARKDOWN_MIME,
            "note": (
                "Live Obsidian uploads .md files (text/markdown) into the Drive vault. "
                "They are not converted to Google Docs."
                if self.live
                else (
                    "Dry-run only. No Drive API calls were made. "
                    "Pass --sink obsidian --live after auth to upload these notes."
                )
            ),
        }
        if self.live:
            plan["appended"] = would
            plan["files_upserted"] = written
        else:
            plan["would_append"] = would
            plan["output_dir"] = str(self.out_dir.resolve()) if self.out_dir else ""
        plan["topic_docs"] = {
            name: {
                "id": (index.get("topic_docs") or {}).get(name, {}).get("id"),
                "url": (index.get("topic_docs") or {}).get(name, {}).get("url"),
                "count": (index.get("topic_docs") or {}).get(name, {}).get("count"),
            }
            for name in ALL_DOC_NAMES
        }
        return plan

    def _scan_existing(self) -> dict[str, list[dict[str, Any]]]:
        if self.live:
            return self._scan_drive()
        return self._scan_local()

    def _scan_local(self) -> dict[str, list[dict[str, Any]]]:
        by_topic: dict[str, list[dict[str, Any]]] = {name: [] for name in ALL_DOC_NAMES}
        if self.out_dir is None or not self.out_dir.is_dir():
            return by_topic
        for name in ALL_DOC_NAMES:
            folder = self.out_dir / name
            if not folder.is_dir():
                continue
            for path in sorted(folder.glob("*.md")):
                if path.name == f"{name}.md":
                    continue
                rec = parse_bookmark_note(path.read_text(encoding="utf-8"), doc=name)
                rec["doc"] = name
                by_topic[name].append(rec)
        return by_topic

    def _scan_drive(self) -> dict[str, list[dict[str, Any]]]:
        assert self.client is not None
        by_topic: dict[str, list[dict[str, Any]]] = {name: [] for name in ALL_DOC_NAMES}
        for name in ALL_DOC_NAMES:
            folder = self.client.find_file(self.folder_id, name)
            if not folder or folder.get("mimeType") != FOLDER_MIME:
                continue
            for meta in self.client.list_files(folder["id"]):
                fname = str(meta.get("name") or "")
                mime = str(meta.get("mimeType") or "")
                if mime == FOLDER_MIME or not fname.endswith(".md"):
                    continue
                if fname == f"{name}.md":
                    continue
                if mime not in {MARKDOWN_MIME, "text/plain", "application/octet-stream"}:
                    # Skip Google Docs that happen to share a name.
                    if mime.startswith("application/vnd.google-apps."):
                        continue
                body = self.client.download_text(meta["id"])
                rec = parse_bookmark_note(body, doc=name)
                rec["doc"] = name
                by_topic[name].append(rec)
        return by_topic

    def _write_local(self, files: Mapping[str, str]) -> int:
        assert self.out_dir is not None
        self.out_dir.mkdir(parents=True, exist_ok=True)
        for rel, content in files.items():
            path = self.out_dir / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return len(files)

    def _write_drive(self, files: Mapping[str, str]) -> int:
        assert self.client is not None
        self.client.get_folder(self.folder_id)
        topic_folders: dict[str, dict[str, Any]] = {}
        for name in ALL_DOC_NAMES:
            topic_folders[name] = self.client.create_folder(self.folder_id, name)
        n = 0
        for rel, content in files.items():
            parent_id, name = _split_vault_path(rel, self.folder_id, topic_folders)
            self.client.upsert_text_file(parent_id, name, content, mime=MARKDOWN_MIME)
            n += 1
        return n


def build_vault_files(
    new_records: Sequence[Mapping[str, Any]],
    existing_by_topic: Mapping[str, Sequence[Mapping[str, Any]]],
) -> tuple[dict[str, str], dict[str, list[Mapping[str, Any]]]]:
    merged: dict[str, list[Mapping[str, Any]]] = {
        name: list(existing_by_topic.get(name) or []) for name in ALL_DOC_NAMES
    }
    files: dict[str, str] = {}
    for rec in new_records:
        topic = str(rec.get("doc") or "needs-review")
        merged.setdefault(topic, [])
        xid = str(rec.get("x_id") or "")
        merged[topic] = [r for r in merged[topic] if str(r.get("x_id") or "") != xid]
        merged[topic].append(rec)
        files[f"{topic}/{filename_slug(rec)}"] = bookmark_note(rec)

    all_recs: list[Mapping[str, Any]] = []
    for name in ALL_DOC_NAMES:
        files[f"{name}/{name}.md"] = topic_note(name, merged.get(name) or [])
        all_recs.extend(merged.get(name) or [])
    files[INDEX_NOTE_NAME] = index_note(all_recs)
    return files, merged


def _split_vault_path(
    rel: str,
    vault_id: str,
    topic_folders: Mapping[str, Mapping[str, Any]],
) -> tuple[str, str]:
    parts = rel.replace("\\", "/").split("/")
    if len(parts) == 1:
        return vault_id, parts[0]
    topic = parts[0]
    folder = topic_folders.get(topic) or {}
    return str(folder.get("id") or vault_id), parts[-1]
