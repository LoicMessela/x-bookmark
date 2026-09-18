"""Plain-text bodies for Google Docs sections and the master index.

These strings are inserted via the Docs API (live) or shown in dry-run plans.
They are not an Obsidian vault layout.
"""

from __future__ import annotations

from typing import Any, Mapping

from x_bookmark.constants import ALL_DOC_NAMES, DEFAULT_DRIVE_FOLDER_URL, SOURCE


def section_heading(record: Mapping[str, Any]) -> str:
    date = _date_prefix(str(record.get("saved_at") or ""))
    author = str(record.get("author") or "@unknown")
    x_id = str(record.get("x_id") or "")
    return f"{date} — {author} — {x_id}"


def section_body(record: Mapping[str, Any]) -> str:
    """Full append payload including heading. Text is record['text'] only."""
    topics = record.get("topics") or []
    if isinstance(topics, (list, tuple)):
        topics_s = ", ".join(str(t) for t in topics) if topics else "(none)"
    else:
        topics_s = str(topics)
    text = str(record.get("text") or "")
    lines = [
        section_heading(record),
        "",
        f"url: {record.get('url') or ''}",
        f"author: {record.get('author') or ''}",
        f"x_id: {record.get('x_id') or ''}",
        f"saved_at: {record.get('saved_at') or ''}",
        f"topics: {topics_s}",
        f"confidence: {record.get('confidence')}",
        f"source: {record.get('source') or SOURCE}",
        "",
        text,
        "",
    ]
    return "\n".join(lines)


def index_document_text(
    topic_docs: Mapping[str, Mapping[str, Any]],
    *,
    folder_url: str = DEFAULT_DRIVE_FOLDER_URL,
    last_sync: str = "",
) -> str:
    lines = [
        "X Bookmarks — index",
        "",
        f"Drive folder: {folder_url}",
        f"Last sync: {last_sync or '(not yet)'}",
        "",
        "One Google Doc per topic. Incremental sync appends new x_id sections only.",
        "",
        "Topics",
        "",
    ]
    for name in ALL_DOC_NAMES:
        meta = topic_docs.get(name) or {}
        count = int(meta.get("count") or 0)
        url = meta.get("url") or "(doc not created yet)"
        lines.append(f"- {name} ({count}) — {url}")
    lines.append("")
    return "\n".join(lines)


def heading_range(insert_index: int, heading: str) -> tuple[int, int]:
    """Inclusive start, exclusive end of the heading inside an insertText payload."""
    start = insert_index
    end = insert_index + len(heading)
    return start, end


def append_requests(record: Mapping[str, Any], insert_index: int) -> list[dict[str, Any]]:
    """Docs batchUpdate requests: insert a heading + body, style heading as HEADING_2."""
    heading = section_heading(record)
    body = section_body(record)
    # Separate from previous section.
    payload = "\n" + body if insert_index > 1 else body
    heading_in_payload = payload.find(heading)
    start = insert_index + heading_in_payload
    end = start + len(heading)
    return [
        {"insertText": {"location": {"index": insert_index}, "text": payload}},
        {
            "updateParagraphStyle": {
                "range": {"startIndex": start, "endIndex": end},
                "paragraphStyle": {"namedStyleType": "HEADING_2"},
                "fields": "namedStyleType",
            }
        },
    ]


def _date_prefix(saved_at: str) -> str:
    if not saved_at:
        return "undated"
    return saved_at[:10]


def optional_markdown_preview(record: Mapping[str, Any]) -> str:
    """Example-only Markdown rendering. Not the product sink."""
    topics = record.get("topics") or []
    topics_yaml = "[" + ", ".join(str(t) for t in topics) + "]"
    text = str(record.get("text") or "")
    quoted = "\n".join(f"> {line}" if line else ">" for line in text.split("\n"))
    hashtag = str(record.get("doc") or "misc").lower().replace(" ", "-")
    return (
        "---\n"
        f"url: {record.get('url')}\n"
        f"author: \"{record.get('author')}\"\n"
        f"x_id: \"{record.get('x_id')}\"\n"
        f"saved_at: {record.get('saved_at')}\n"
        f"topics: {topics_yaml}\n"
        f"confidence: {record.get('confidence')}\n"
        f"source: {record.get('source') or SOURCE}\n"
        "---\n\n"
        f"{quoted}\n\n"
        f"[{record.get('author')} on X]({record.get('url')})\n\n"
        f"#{hashtag}\n"
    )


def filename_slug(record: Mapping[str, Any]) -> str:
    date = _date_prefix(str(record.get("saved_at") or ""))
    author = str(record.get("author") or "unknown").lstrip("@").lower()
    x_id = str(record.get("x_id") or "id")
    return f"{date}-{author}-{x_id}.md"
