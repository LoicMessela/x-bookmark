"""Load Vault Scout X bookmark export JSON. Never invent post text."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Union

PathLike = Union[str, Path]


def load_export(path: PathLike) -> list[dict[str, Any]]:
    """Return the `posts` list from an export file.

    Accepts `{ "posts": [...] }` (Vault Scout shape) or a raw list.
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return posts_from_payload(raw)


def posts_from_payload(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        posts = raw
    elif isinstance(raw, dict) and isinstance(raw.get("posts"), list):
        posts = raw["posts"]
    else:
        raise ValueError(
            "Export JSON must be a list of posts or an object with a 'posts' array."
        )
    out: list[dict[str, Any]] = []
    for i, post in enumerate(posts):
        if not isinstance(post, dict):
            raise ValueError(f"posts[{i}] is not an object")
        if not post.get("id"):
            raise ValueError(f"posts[{i}] missing id")
        out.append(post)
    return out
