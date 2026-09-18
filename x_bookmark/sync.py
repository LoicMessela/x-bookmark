"""Orchestrate ingest → classify → dedup → sink."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Union

from x_bookmark.constants import DEFAULT_DRIVE_FOLDER_ID, DEFAULT_OUTPUT_DIR
from x_bookmark.import_index import imported_set, load_index_file, index_path
from x_bookmark.ingest import load_export
from x_bookmark.records import to_record
from x_bookmark.sinks.drive_docs import DriveDocsSink
from x_bookmark.sinks.preview import PreviewSink

PathLike = Union[str, Path]


def sync(
    input_path: PathLike,
    *,
    live: bool = False,
    out_dir: PathLike = DEFAULT_OUTPUT_DIR,
    folder_id: str = DEFAULT_DRIVE_FOLDER_ID,
    markdown_preview: bool = False,
    drive_client: Any = None,
) -> dict[str, Any]:
    posts = load_export(input_path)

    if live:
        sink = DriveDocsSink(folder_id, client=drive_client)
        index = sink.load_index()
    else:
        sink = PreviewSink(
            out_dir, folder_id=folder_id, markdown_preview=markdown_preview
        )
        index = load_index_file(index_path(out_dir))

    seen = imported_set(index)
    already = len(seen)
    new_records = []
    skipped = 0
    for post in posts:
        x_id = str(post["id"])
        if x_id in seen:
            skipped += 1
            continue
        new_records.append(to_record(post))
        seen.add(x_id)

    plan = sink.commit(
        new_records,
        index,
        skipped=skipped,
        already_imported=already,
    )
    plan["input"] = str(Path(input_path))
    plan["input_posts"] = len(posts)
    return plan
