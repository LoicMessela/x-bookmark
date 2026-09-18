"""Import-index helpers. Durable artifact: `_import_index.json`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Union

from x_bookmark.constants import ALL_DOC_NAMES, IMPORT_INDEX_NAME

PathLike = Union[str, Path]


def empty_index() -> dict[str, Any]:
    return {
        "imported_x_ids": [],
        "topic_docs": {
            name: {"id": None, "url": None, "count": 0} for name in ALL_DOC_NAMES
        },
        "index_doc": {"id": None, "url": None},
    }


def load_index_file(path: PathLike) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        return empty_index()
    data = json.loads(p.read_text(encoding="utf-8"))
    return merge_index(empty_index(), data if isinstance(data, dict) else {})


def merge_index(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    out = empty_index()
    ids = incoming.get("imported_x_ids") or base.get("imported_x_ids") or []
    out["imported_x_ids"] = [str(x) for x in ids]
    base_docs = base.get("topic_docs") or {}
    inc_docs = incoming.get("topic_docs") or {}
    for name in ALL_DOC_NAMES:
        merged = dict(base_docs.get(name) or {"id": None, "url": None, "count": 0})
        merged.update(inc_docs.get(name) or {})
        merged["count"] = int(merged.get("count") or 0)
        out["topic_docs"][name] = merged
    index_doc = dict(base.get("index_doc") or {})
    index_doc.update(incoming.get("index_doc") or {})
    out["index_doc"] = index_doc
    return out


def write_index_file(path: PathLike, index: dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(index)
    payload["imported_x_ids"] = sorted({str(x) for x in index.get("imported_x_ids") or []})
    p.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def imported_set(index: dict[str, Any]) -> set[str]:
    return {str(x) for x in index.get("imported_x_ids") or []}


def add_imported(index: dict[str, Any], x_ids: Iterable[str]) -> dict[str, Any]:
    ids = imported_set(index)
    ids.update(str(x) for x in x_ids)
    index = dict(index)
    index["imported_x_ids"] = sorted(ids)
    return index


def index_path(out_dir: PathLike) -> Path:
    return Path(out_dir) / IMPORT_INDEX_NAME
