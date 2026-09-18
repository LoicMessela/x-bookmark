"""Local dry-run sink: JSONL records + import index. No Drive writes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence, Union

from x_bookmark.constants import ALL_DOC_NAMES, DEFAULT_DRIVE_FOLDER_ID, DEFAULT_DRIVE_FOLDER_URL
from x_bookmark.docs_format import filename_slug, optional_markdown_preview, section_body
from x_bookmark.import_index import add_imported, index_path, write_index_file

PathLike = Union[str, Path]


class PreviewSink:
    """Writes what *would* be appended to Google Docs, without calling Drive."""

    def __init__(
        self,
        out_dir: PathLike,
        *,
        folder_id: str = DEFAULT_DRIVE_FOLDER_ID,
        markdown_preview: bool = False,
    ) -> None:
        self.out_dir = Path(out_dir)
        self.folder_id = folder_id
        self.markdown_preview = markdown_preview

    def commit(
        self,
        records: Sequence[Mapping[str, Any]],
        index: dict[str, Any],
        *,
        skipped: int,
        already_imported: int,
    ) -> dict[str, Any]:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        counts: dict[str, int] = {name: 0 for name in ALL_DOC_NAMES}
        for rec in records:
            doc = str(rec.get("doc") or "needs-review")
            counts[doc] = counts.get(doc, 0) + 1
            topic_meta = index.setdefault("topic_docs", {}).setdefault(
                doc, {"id": None, "url": None, "count": 0}
            )
            topic_meta["count"] = int(topic_meta.get("count") or 0) + 1

        would_append = {k: v for k, v in counts.items() if v}
        plan = {
            "mode": "dry-run",
            "drive_writes": False,
            "sink": "google-docs-via-drive (planned)",
            "folder_id": self.folder_id,
            "folder_url": (
                f"https://drive.google.com/drive/folders/{self.folder_id}"
                if self.folder_id
                else DEFAULT_DRIVE_FOLDER_URL
            ),
            "imported": len(records),
            "skipped": skipped,
            "already_imported_in_index": already_imported,
            "would_append": would_append,
            "would_ensure_docs": list(ALL_DOC_NAMES),
            "would_update_index_doc": True,
            "note": (
                "Dry-run only. No Google Drive or Docs API calls were made. "
                "Pass --live after auth to append these sections to Jabba's folder."
            ),
        }

        records_path = self.out_dir / "records.jsonl"
        with records_path.open("w", encoding="utf-8") as fh:
            for rec in records:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

        sections_path = self.out_dir / "would_append_sections.jsonl"
        with sections_path.open("w", encoding="utf-8") as fh:
            for rec in records:
                fh.write(
                    json.dumps(
                        {
                            "doc": rec.get("doc"),
                            "x_id": rec.get("x_id"),
                            "section": section_body(rec),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )

        (self.out_dir / "plan.json").write_text(
            json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

        if self.markdown_preview:
            md_root = self.out_dir / "markdown-example"
            md_root.mkdir(parents=True, exist_ok=True)
            (md_root / "README.txt").write_text(
                "Example-only Markdown preview. Product sink is Google Docs in Drive.\n",
                encoding="utf-8",
            )
            for rec in records:
                doc_dir = md_root / str(rec.get("doc") or "needs-review")
                doc_dir.mkdir(parents=True, exist_ok=True)
                (doc_dir / filename_slug(rec)).write_text(
                    optional_markdown_preview(rec), encoding="utf-8"
                )

        new_index = add_imported(index, [str(r["x_id"]) for r in records])
        write_index_file(index_path(self.out_dir), new_index)

        plan["output_dir"] = str(self.out_dir.resolve())
        plan["records_jsonl"] = str(records_path)
        return plan
