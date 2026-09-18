"""Google Docs sink: one Doc per topic + master index inside a Drive folder.

Live writes require Google API client libraries (`pip install -e '.[drive]'`)
and Application Default Credentials or GOOGLE_APPLICATION_CREDENTIALS.

Tests inject FakeDriveClient — no network.
"""

from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Protocol, Sequence

from x_bookmark.constants import (
    ALL_DOC_NAMES,
    DEFAULT_DRIVE_FOLDER_ID,
    DEFAULT_DRIVE_FOLDER_URL,
    IMPORT_INDEX_NAME,
    INDEX_DOC_NAME,
)
from x_bookmark.docs_format import append_requests, index_document_text
from x_bookmark.import_index import add_imported, empty_index, merge_index

DOC_MIME = "application/vnd.google-apps.document"
FOLDER_MIME = "application/vnd.google-apps.folder"
DRIVE_SCOPES = (
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
)


class DriveClient(Protocol):
    def get_folder(self, folder_id: str) -> dict[str, Any]: ...

    def find_file(self, folder_id: str, name: str) -> Optional[dict[str, Any]]: ...

    def create_doc(self, folder_id: str, name: str) -> dict[str, Any]: ...

    def upsert_json(self, folder_id: str, name: str, payload: dict[str, Any]) -> dict[str, Any]: ...

    def download_json(self, file_id: str) -> dict[str, Any]: ...

    def doc_end_index(self, doc_id: str) -> int: ...

    def batch_update(self, doc_id: str, requests: list[dict[str, Any]]) -> None: ...

    def replace_doc_text(self, doc_id: str, text: str) -> None: ...


def docs_url(file_id: str) -> str:
    return f"https://docs.google.com/document/d/{file_id}/edit"


class FakeDriveClient:
    """In-memory Drive/Docs stand-in for tests."""

    def __init__(self, folder_id: str = DEFAULT_DRIVE_FOLDER_ID) -> None:
        self.folder_id = folder_id
        self.files: dict[str, dict[str, Any]] = {}
        self.docs_text: dict[str, str] = {}
        self.json_blobs: dict[str, dict[str, Any]] = {}
        self._n = 0
        self.files[folder_id] = {
            "id": folder_id,
            "name": "X Bookmarks",
            "mimeType": FOLDER_MIME,
        }

    def _id(self, prefix: str) -> str:
        self._n += 1
        return f"{prefix}{self._n}"

    def get_folder(self, folder_id: str) -> dict[str, Any]:
        info = self.files.get(folder_id)
        if not info:
            raise FileNotFoundError(folder_id)
        return info

    def find_file(self, folder_id: str, name: str) -> Optional[dict[str, Any]]:
        for meta in self.files.values():
            if meta.get("name") == name and folder_id in (meta.get("parents") or []):
                return dict(meta)
        return None

    def create_doc(self, folder_id: str, name: str) -> dict[str, Any]:
        existing = self.find_file(folder_id, name)
        if existing:
            return existing
        file_id = self._id("doc")
        meta = {
            "id": file_id,
            "name": name,
            "mimeType": DOC_MIME,
            "parents": [folder_id],
            "webViewLink": docs_url(file_id),
        }
        self.files[file_id] = meta
        self.docs_text[file_id] = "\n"
        return dict(meta)

    def upsert_json(self, folder_id: str, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        existing = self.find_file(folder_id, name)
        if existing:
            self.json_blobs[existing["id"]] = payload
            return dict(existing)
        file_id = self._id("json")
        meta = {
            "id": file_id,
            "name": name,
            "mimeType": "application/json",
            "parents": [folder_id],
        }
        self.files[file_id] = meta
        self.json_blobs[file_id] = payload
        return dict(meta)

    def download_json(self, file_id: str) -> dict[str, Any]:
        return dict(self.json_blobs.get(file_id) or {})

    def doc_end_index(self, doc_id: str) -> int:
        return len(self.docs_text.get(doc_id, "\n")) + 1

    def batch_update(self, doc_id: str, requests: list[dict[str, Any]]) -> None:
        text = self.docs_text.get(doc_id, "\n")
        for req in requests:
            insert = req.get("insertText")
            if insert:
                text += insert["text"]
        self.docs_text[doc_id] = text

    def replace_doc_text(self, doc_id: str, text: str) -> None:
        self.docs_text[doc_id] = text if text.endswith("\n") else text + "\n"


class GoogleDriveClient:
    """Thin wrapper around Drive v3 + Docs v1."""

    def __init__(self, creds: Any = None) -> None:
        try:
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaIoBaseUpload
        except ImportError as exc:
            raise RuntimeError(
                "Live Drive sync needs optional deps. From the repo root run:\n"
                "  pip install -e '.[drive]'\n"
                "Then set GOOGLE_APPLICATION_CREDENTIALS or ADC. Dry-run does not need this."
            ) from exc
        self._MediaIoBaseUpload = MediaIoBaseUpload
        if creds is None:
            creds = load_credentials()
        self.drive = build("drive", "v3", credentials=creds, cache_discovery=False)
        self.docs = build("docs", "v1", credentials=creds, cache_discovery=False)

    def get_folder(self, folder_id: str) -> dict[str, Any]:
        return (
            self.drive.files()
            .get(fileId=folder_id, fields="id,name,mimeType,webViewLink", supportsAllDrives=True)
            .execute()
        )

    def find_file(self, folder_id: str, name: str) -> Optional[dict[str, Any]]:
        q = (
            f"'{folder_id}' in parents and name = '{_escape_q(name)}' "
            "and trashed = false"
        )
        resp = (
            self.drive.files()
            .list(
                q=q,
                fields="files(id,name,mimeType,webViewLink)",
                pageSize=10,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute()
        )
        files = resp.get("files") or []
        return files[0] if files else None

    def create_doc(self, folder_id: str, name: str) -> dict[str, Any]:
        existing = self.find_file(folder_id, name)
        if existing:
            return existing
        body = {
            "name": name,
            "mimeType": DOC_MIME,
            "parents": [folder_id],
        }
        created = (
            self.drive.files()
            .create(
                body=body,
                fields="id,name,mimeType,webViewLink",
                supportsAllDrives=True,
            )
            .execute()
        )
        title = f"{name}\n\n"
        self.docs.documents().batchUpdate(
            documentId=created["id"],
            body={
                "requests": [
                    {"insertText": {"location": {"index": 1}, "text": title}},
                    {
                        "updateParagraphStyle": {
                            "range": {"startIndex": 1, "endIndex": 1 + len(name)},
                            "paragraphStyle": {"namedStyleType": "HEADING_1"},
                            "fields": "namedStyleType",
                        }
                    },
                ]
            },
        ).execute()
        return created

    def upsert_json(self, folder_id: str, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        raw = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        media = self._MediaIoBaseUpload(
            io.BytesIO(raw), mimetype="application/json", resumable=False
        )
        existing = self.find_file(folder_id, name)
        if existing:
            return (
                self.drive.files()
                .update(
                    fileId=existing["id"],
                    media_body=media,
                    fields="id,name,mimeType,webViewLink",
                    supportsAllDrives=True,
                )
                .execute()
            )
        body = {"name": name, "parents": [folder_id], "mimeType": "application/json"}
        return (
            self.drive.files()
            .create(
                body=body,
                media_body=media,
                fields="id,name,mimeType,webViewLink",
                supportsAllDrives=True,
            )
            .execute()
        )

    def download_json(self, file_id: str) -> dict[str, Any]:
        data = self.drive.files().get_media(fileId=file_id, supportsAllDrives=True).execute()
        if isinstance(data, bytes):
            text = data.decode("utf-8")
        else:
            text = str(data)
        parsed = json.loads(text or "{}")
        return parsed if isinstance(parsed, dict) else {}

    def doc_end_index(self, doc_id: str) -> int:
        doc = self.docs.documents().get(documentId=doc_id).execute()
        content = doc.get("body", {}).get("content") or []
        if not content:
            return 1
        return int(content[-1].get("endIndex") or 2) - 1

    def batch_update(self, doc_id: str, requests: list[dict[str, Any]]) -> None:
        if not requests:
            return
        self.docs.documents().batchUpdate(
            documentId=doc_id, body={"requests": requests}
        ).execute()

    def replace_doc_text(self, doc_id: str, text: str) -> None:
        end = self.doc_end_index(doc_id)
        requests: list[dict[str, Any]] = []
        if end > 1:
            requests.append(
                {
                    "deleteContentRange": {
                        "range": {"startIndex": 1, "endIndex": end}
                    }
                }
            )
        if text:
            requests.append({"insertText": {"location": {"index": 1}, "text": text}})
            first_line = text.split("\n", 1)[0]
            requests.append(
                {
                    "updateParagraphStyle": {
                        "range": {"startIndex": 1, "endIndex": 1 + len(first_line)},
                        "paragraphStyle": {"namedStyleType": "HEADING_1"},
                        "fields": "namedStyleType",
                    }
                }
            )
        self.batch_update(doc_id, requests)


def load_credentials() -> Any:
    try:
        from google.auth import default as google_auth_default
    except ImportError as exc:
        raise RuntimeError(
            "google-auth is not installed. Dry-run works without it. For --live:\n"
            "  pip install -e '.[drive]'\n"
            "  export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json"
        ) from exc
    creds, _ = google_auth_default(scopes=list(DRIVE_SCOPES))
    return creds


def _escape_q(name: str) -> str:
    return name.replace("\\", "\\\\").replace("'", "\\'")


class DriveDocsSink:
    def __init__(
        self,
        folder_id: str,
        client: Optional[DriveClient] = None,
        *,
        folder_url: Optional[str] = None,
    ) -> None:
        self.folder_id = folder_id
        self.folder_url = folder_url or f"https://drive.google.com/drive/folders/{folder_id}"
        self.client: DriveClient = client if client is not None else GoogleDriveClient()

    def load_index(self) -> dict[str, Any]:
        found = self.client.find_file(self.folder_id, IMPORT_INDEX_NAME)
        if not found:
            return empty_index()
        return merge_index(empty_index(), self.client.download_json(found["id"]))

    def commit(
        self,
        records: Sequence[Mapping[str, Any]],
        index: dict[str, Any],
        *,
        skipped: int,
        already_imported: int,
    ) -> dict[str, Any]:
        self.client.get_folder(self.folder_id)
        topic_files: dict[str, dict[str, Any]] = {}
        for name in ALL_DOC_NAMES:
            meta = self.client.create_doc(self.folder_id, name)
            topic_files[name] = meta
            url = meta.get("webViewLink") or docs_url(meta["id"])
            slot = index.setdefault("topic_docs", {}).setdefault(
                name, {"id": None, "url": None, "count": 0}
            )
            slot["id"] = meta["id"]
            slot["url"] = url

        append_counts: dict[str, int] = {}
        for rec in records:
            doc_name = str(rec.get("doc") or "needs-review")
            if doc_name not in topic_files:
                meta = self.client.create_doc(self.folder_id, doc_name)
                topic_files[doc_name] = meta
            file_meta = topic_files[doc_name]
            insert_at = self.client.doc_end_index(file_meta["id"])
            self.client.batch_update(file_meta["id"], append_requests(rec, insert_at))
            slot = index["topic_docs"].setdefault(
                doc_name, {"id": file_meta["id"], "url": None, "count": 0}
            )
            slot["count"] = int(slot.get("count") or 0) + 1
            append_counts[doc_name] = append_counts.get(doc_name, 0) + 1

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        index_meta = self.client.create_doc(self.folder_id, INDEX_DOC_NAME)
        index_url = index_meta.get("webViewLink") or docs_url(index_meta["id"])
        index["index_doc"] = {"id": index_meta["id"], "url": index_url}
        self.client.replace_doc_text(
            index_meta["id"],
            index_document_text(
                index.get("topic_docs") or {},
                folder_url=self.folder_url,
                last_sync=now,
            ),
        )

        new_index = add_imported(index, [str(r["x_id"]) for r in records])
        self.client.upsert_json(self.folder_id, IMPORT_INDEX_NAME, new_index)

        return {
            "mode": "live",
            "drive_writes": True,
            "sink": "google-docs-via-drive",
            "folder_id": self.folder_id,
            "folder_url": self.folder_url,
            "imported": len(records),
            "skipped": skipped,
            "already_imported_in_index": already_imported,
            "appended": append_counts,
            "index_doc": index["index_doc"],
            "topic_docs": {
                name: {
                    "id": (index.get("topic_docs") or {}).get(name, {}).get("id"),
                    "url": (index.get("topic_docs") or {}).get(name, {}).get("url"),
                    "count": (index.get("topic_docs") or {}).get(name, {}).get("count"),
                }
                for name in ALL_DOC_NAMES
            },
        }
