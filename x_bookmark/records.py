"""Normalized bookmark records for JSONL preview and Docs append."""

from __future__ import annotations

from typing import Any, Optional

from x_bookmark.classify import Classification, classify
from x_bookmark.constants import SOURCE


def canonical_url(post: dict[str, Any]) -> str:
    handle = _handle(post)
    x_id = str(post["id"])
    if handle and handle != "unknown":
        return f"https://x.com/{handle}/status/{x_id}"
    existing = str(post.get("url") or "").strip()
    if existing:
        return existing
    return f"https://x.com/i/web/status/{x_id}"


def _handle(post: dict[str, Any]) -> str:
    author = str(post.get("author") or "").strip().lstrip("@")
    if author:
        return author
    return "unknown"


def saved_at(post: dict[str, Any]) -> str:
    """Prefer export saved_at; otherwise tweet created_at. Never fabricate text."""
    for key in ("saved_at", "created_at"):
        value = post.get(key)
        if value:
            return str(value)
    return ""


def verbatim_text(post: dict[str, Any]) -> str:
    text = post.get("text")
    if text is None:
        return ""
    return str(text)


def to_record(post: dict[str, Any], classification: Optional[Classification] = None) -> dict[str, Any]:
    """Structured record. `text` is copied from the export only."""
    if classification is None:
        classification = classify(post)
    handle = _handle(post)
    author = f"@{handle}" if handle != "unknown" else "@unknown"
    return {
        "url": canonical_url(post),
        "author": author,
        "x_id": str(post["id"]),
        "saved_at": saved_at(post),
        "topics": list(classification.topics),
        "confidence": int(classification.confidence),
        "source": SOURCE,
        "text": verbatim_text(post),
        "doc": classification.doc,
        "classify_reason": classification.reason,
    }
