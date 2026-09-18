"""Obsidian note bodies: per-bookmark notes plus Index / topic MOCs.

Text bodies copy record['text'] only. These strings are written by
ObsidianSink; they are not the Google Docs layout.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from x_bookmark.constants import ALL_DOC_NAMES, DEFAULT_DRIVE_FOLDER_NAME, SOURCE
from x_bookmark.docs_format import filename_slug


def sort_newest_first(records: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Newest saved_at first. Missing/empty dates sort last."""
    dated = [r for r in records if str(r.get("saved_at") or "")]
    undated = [r for r in records if not str(r.get("saved_at") or "")]
    dated_sorted = sorted(
        dated, key=lambda r: str(r.get("saved_at") or ""), reverse=True
    )
    return dated_sorted + list(undated)


def wikilink_stem(record: Mapping[str, Any]) -> str:
    slug = filename_slug(record)
    return slug[:-3] if slug.endswith(".md") else slug


def bookmark_note(record: Mapping[str, Any]) -> str:
    """YAML frontmatter + verbatim export text. Never invents tweet body."""
    topics = record.get("topics") or []
    if isinstance(topics, (list, tuple)):
        topic_items = [str(t) for t in topics]
    else:
        topic_items = [str(topics)] if topics else []
    if topic_items:
        topics_yaml = "\n".join(f"  - {_yaml_scalar(t)}" for t in topic_items)
        topics_block = f"topics:\n{topics_yaml}"
    else:
        topics_block = "topics: []"
    text = str(record.get("text") or "")
    lines = [
        "---",
        f"url: {_yaml_scalar(str(record.get('url') or ''))}",
        f"author: {_yaml_scalar(str(record.get('author') or ''))}",
        f"x_id: {_yaml_scalar(str(record.get('x_id') or ''))}",
        f"saved_at: {_yaml_scalar(str(record.get('saved_at') or ''))}",
        topics_block,
        f"source: {_yaml_scalar(str(record.get('source') or SOURCE))}",
    ]
    if record.get("confidence") is not None and str(record.get("confidence")) != "":
        lines.append(f"confidence: {int(record['confidence'])}")
    lines.extend(["---", "", text, ""])
    return "\n".join(lines)


def topic_note(topic: str, records: Sequence[Mapping[str, Any]]) -> str:
    ordered = sort_newest_first(list(records))
    lines = [
        f"# {topic}",
        "",
        "## Glossary",
        "",
    ]
    lines.extend(_glossary_lines(current=topic))
    lines.extend(["", "## Contents", ""])
    if ordered:
        for rec in ordered:
            stem = wikilink_stem(rec)
            author = rec.get("author") or "@unknown"
            date = str(rec.get("saved_at") or "")[:10] or "undated"
            lines.append(f"- [[{stem}]] — {author} — {date}")
    else:
        lines.append("- (none)")
    lines.append("")
    return "\n".join(lines)


def index_note(
    records: Sequence[Mapping[str, Any]],
    *,
    counts: Optional[Mapping[str, int]] = None,
) -> str:
    by_topic: dict[str, list[Mapping[str, Any]]] = {name: [] for name in ALL_DOC_NAMES}
    for rec in records:
        name = str(rec.get("doc") or "needs-review")
        by_topic.setdefault(name, []).append(rec)
    if counts is None:
        counts = {name: len(by_topic.get(name) or []) for name in ALL_DOC_NAMES}

    lines = [
        f"# {DEFAULT_DRIVE_FOLDER_NAME}",
        "",
        "## Glossary",
        "",
    ]
    lines.extend(_glossary_lines(current=None))
    lines.extend(["", "## Topics", ""])
    for name in ALL_DOC_NAMES:
        n = int(counts.get(name) or 0)
        lines.append(f"- [[{name}/{name}|{name}]] ({n})")
    lines.extend(["", "## Contents", ""])
    for name in ALL_DOC_NAMES:
        ordered = sort_newest_first(by_topic.get(name) or [])
        lines.append(f"### {name}")
        lines.append("")
        if ordered:
            for rec in ordered:
                stem = wikilink_stem(rec)
                author = rec.get("author") or "@unknown"
                date = str(rec.get("saved_at") or "")[:10] or "undated"
                lines.append(f"- [[{name}/{stem}|{stem}]] — {author} — {date}")
        else:
            lines.append("- (none)")
        lines.append("")
    return "\n".join(lines)


def _glossary_lines(*, current: Optional[str]) -> list[str]:
    lines = ["- [[Index]]"]
    for name in ALL_DOC_NAMES:
        if current == name:
            lines.append(f"- [[{name}]]")
        else:
            lines.append(f"- [[{name}/{name}|{name}]]")
    return lines


def _yaml_scalar(value: str) -> str:
    if value == "":
        return '""'
    if value.isdigit() or any(ch in value for ch in ":#{}[]&*?|>!%@`'\"\n"):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if value.lower() in {"true", "false", "null", "yes", "no", "on", "off"}:
        return f'"{value}"'
    return value


def parse_bookmark_note(text: str, *, doc: str) -> dict[str, Any]:
    """Recover a record from a bookmark note. Body text is whatever the file stored."""
    rec: dict[str, Any] = {
        "doc": doc,
        "url": "",
        "author": "",
        "x_id": "",
        "saved_at": "",
        "topics": [],
        "source": SOURCE,
        "text": "",
        "confidence": 0,
    }
    raw = text.replace("\r\n", "\n")
    if not raw.startswith("---"):
        rec["text"] = raw
        return rec
    rest = raw[3:].lstrip("\n")
    fm, sep, body = rest.partition("\n---")
    if not sep:
        rec["text"] = raw
        return rec
    rec["text"] = body.lstrip("\n").rstrip("\n")
    topics: list[str] = []
    in_topics = False
    for line in fm.splitlines():
        if line.startswith("  - "):
            if in_topics:
                topics.append(line[4:].strip().strip('"'))
            continue
        in_topics = False
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"')
        if key == "topics":
            in_topics = True
            if value and value != "[]":
                topics.append(value)
        elif key in rec:
            if key == "confidence" and value:
                try:
                    rec[key] = int(value)
                except ValueError:
                    rec[key] = 0
            else:
                rec[key] = value
    rec["topics"] = topics
    return rec
