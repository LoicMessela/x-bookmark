"""Plain-text bodies for Google Docs sections and the master index.

These strings are inserted via the Docs API (live) or shown in Docs dry-run plans.
Obsidian Markdown lives in x_bookmark.obsidian_format.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

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
        "Glossary",
        "",
    ]
    for name in ALL_DOC_NAMES:
        meta = topic_docs.get(name) or {}
        count = int(meta.get("count") or 0)
        url = meta.get("url") or "(doc not created yet)"
        lines.append(f"- {name} ({count}) — {url}")
    lines.extend(
        [
            "",
            f"Drive folder: {folder_url}",
            f"Last sync: {last_sync or '(not yet)'}",
            "",
            "One Google Doc per topic. New x_id sections only; newest saved_at first.",
            "",
        ]
    )
    return "\n".join(lines)


def is_section_heading(line: str) -> bool:
    parts = line.split(" — ")
    if len(parts) < 3:
        return False
    date = parts[0]
    if date == "undated":
        return True
    return len(date) == 10 and date[4] == "-" and date[7] == "-"


def parse_doc_sections(text: str) -> list[dict[str, str]]:
    """Split generated Doc text into dated sections. Header/glossary is dropped."""
    lines = str(text or "").split("\n")
    starts = [i for i, line in enumerate(lines) if is_section_heading(line)]
    sections: list[dict[str, str]] = []
    for idx, start in enumerate(starts):
        end = starts[idx + 1] if idx + 1 < len(starts) else len(lines)
        chunk = lines[start:end]
        while chunk and chunk[-1] == "":
            chunk.pop()
        body = "\n".join(chunk) + "\n"
        heading = lines[start]
        saved_at = ""
        x_id = heading.split(" — ")[-1] if " — " in heading else ""
        for raw in chunk:
            if raw.startswith("saved_at:"):
                saved_at = raw.split(":", 1)[1].strip()
            elif raw.startswith("x_id:"):
                x_id = raw.split(":", 1)[1].strip()
        sections.append(
            {"heading": heading, "body": body, "saved_at": saved_at, "x_id": str(x_id)}
        )
    return sections


def leftover_unparsed_text(text: str, doc_name: str) -> str:
    """Keep non-generated preamble that is not title/glossary/TOC."""
    lines = str(text or "").split("\n")
    starts = [i for i, line in enumerate(lines) if is_section_heading(line)]
    preamble = lines[: starts[0]] if starts else lines
    keep: list[str] = []
    skip_prefixes = (
        "Drive folder:",
        "Last sync:",
        "One Google Doc",
        "url:",
        "author:",
        "x_id:",
        "saved_at:",
        "topics:",
        "confidence:",
        "source:",
    )
    skip_exact = {
        doc_name,
        "X Bookmarks — index",
        "Glossary",
        "Contents",
        "Topics",
        "",
    }
    for line in preamble:
        stripped = line.strip()
        if stripped in skip_exact:
            continue
        if stripped.startswith("- "):
            continue
        if any(stripped.startswith(p) for p in skip_prefixes):
            continue
        keep.append(line)
    leftover = "\n".join(keep).strip()
    return leftover


def sort_sections_newest_first(sections: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    dated = [s for s in sections if str(s.get("saved_at") or "")]
    undated = [s for s in sections if not str(s.get("saved_at") or "")]
    dated_sorted = sorted(
        dated, key=lambda s: str(s.get("saved_at") or ""), reverse=True
    )
    return list(dated_sorted) + list(undated)


def topic_document_text(
    name: str,
    sections: Sequence[Mapping[str, Any]],
    topic_docs: Mapping[str, Mapping[str, Any]],
    *,
    index_url: str = "",
    leftover: str = "",
) -> str:
    ordered = sort_sections_newest_first(list(sections))
    lines = [name, "", "Glossary", ""]
    if index_url:
        lines.append(f"- _index — {index_url}")
    for topic in ALL_DOC_NAMES:
        meta = topic_docs.get(topic) or {}
        url = meta.get("url") or ""
        marker = " (this Doc)" if topic == name else ""
        lines.append(f"- {topic}{marker} — {url}")
    lines.extend(["", "Contents", ""])
    if ordered:
        for sec in ordered:
            lines.append(f"- {sec.get('heading') or ''}")
    else:
        lines.append("- (none)")
    lines.append("")
    for sec in ordered:
        body = str(sec.get("body") or "").rstrip("\n")
        lines.append(body)
        lines.append("")
    extra = leftover.strip()
    if extra:
        lines.extend(["Unparsed", "", extra, ""])
    return "\n".join(lines)


def heading_style_requests(text: str, insert_index: int = 1) -> list[dict[str, Any]]:
    """Docs batchUpdate paragraph styles for a fully replaced document body."""
    requests: list[dict[str, Any]] = []
    idx = insert_index
    for i, line in enumerate(text.split("\n")):
        start = idx
        end = idx + len(line)
        style = None
        if line and i == 0:
            style = "HEADING_1"
        elif line in {"Glossary", "Contents", "Topics", "Unparsed"} or is_section_heading(
            line
        ):
            style = "HEADING_2"
        if style and end > start:
            requests.append(
                {
                    "updateParagraphStyle": {
                        "range": {"startIndex": start, "endIndex": end},
                        "paragraphStyle": {"namedStyleType": style},
                        "fields": "namedStyleType",
                    }
                }
            )
        idx = end + 1
    return requests


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
