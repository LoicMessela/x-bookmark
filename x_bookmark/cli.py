"""Vault Scout CLI: X bookmark export → classify → Docs or Obsidian Drive.

X is read-only. This tool never posts, likes, replies, or deletes bookmarks.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Optional, Sequence

from x_bookmark.constants import (
    DEFAULT_DRIVE_FOLDER_ID,
    DEFAULT_DRIVE_FOLDER_URL,
    DEFAULT_OBSIDIAN_DRIVE_FOLDER_ID,
    DEFAULT_OBSIDIAN_DRIVE_FOLDER_URL,
    DEFAULT_OBSIDIAN_PREVIEW_DIR,
    DEFAULT_OUTPUT_DIR,
)
from x_bookmark.sync import sync


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="x-bookmark",
        description=(
            "Ingest a read-only X bookmark export, classify topics, and sync "
            "into Google Docs (default) or an Obsidian Markdown vault on Drive."
        ),
        epilog=(
            "X write actions are out of scope. Dry-run never calls Drive. "
            f"Docs folder: {DEFAULT_DRIVE_FOLDER_URL} "
            f"Obsidian vault: {DEFAULT_OBSIDIAN_DRIVE_FOLDER_URL}"
        ),
    )
    sub = parser.add_subparsers(dest="command")

    sync_p = sub.add_parser("sync", help="Classify export posts and sync (dry-run by default).")
    sync_p.add_argument(
        "--input",
        "-i",
        required=True,
        help="Path to Vault Scout export JSON ({ posts: [...] }).",
    )
    sync_p.add_argument(
        "--sink",
        choices=("docs", "obsidian"),
        default=None,
        help="Destination (default docs, or env X_BOOKMARK_SINK). Docs is Google Docs; obsidian is .md on Drive.",
    )
    sync_p.add_argument(
        "--obsidian",
        action="store_true",
        help="Same as --sink obsidian. Errors if combined with --sink docs.",
    )
    sync_p.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Write local preview only (default if --live is not set).",
    )
    sync_p.add_argument(
        "--live",
        action="store_true",
        help="Write to Drive: Google Docs (docs sink) or .md files (obsidian sink).",
    )
    sync_p.add_argument(
        "--out",
        "--output-dir",
        dest="out",
        default=None,
        help=(
            "Dry-run output directory (env OUTPUT_DIR). "
            f"Default {DEFAULT_OUTPUT_DIR} for docs, {DEFAULT_OBSIDIAN_PREVIEW_DIR} for obsidian."
        ),
    )
    sync_p.add_argument(
        "--folder-id",
        default=None,
        help="Docs Drive folder id (env DRIVE_FOLDER_ID; default is Jabba's X Bookmarks Docs folder).",
    )
    sync_p.add_argument(
        "--obsidian-folder-id",
        default=None,
        help=(
            "Obsidian Drive folder id (env OBSIDIAN_DRIVE_FOLDER_ID; "
            "default is Jabba's Obsidian Vault - X Bookmarks folder)."
        ),
    )
    sync_p.add_argument(
        "--markdown-preview",
        action="store_true",
        help="Docs dry-run only: also write example Markdown under the preview dir (not the Obsidian sink).",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "sync":
        return _cmd_sync(args)
    parser.error(f"unknown command {args.command}")
    return 2


def _cmd_sync(args: argparse.Namespace) -> int:
    live = bool(args.live)
    if args.dry_run and args.live:
        print("error: pass either --dry-run or --live, not both", file=sys.stderr)
        return 2

    if args.obsidian and args.sink == "docs":
        print("error: --obsidian cannot be combined with --sink docs", file=sys.stderr)
        return 2

    sink = args.sink
    if args.obsidian:
        sink = "obsidian"
    if not sink:
        sink = _env("X_BOOKMARK_SINK") or "docs"
    sink = sink.strip().lower()
    if sink not in {"docs", "obsidian"}:
        print("error: sink must be docs or obsidian", file=sys.stderr)
        return 2

    folder_id = args.folder_id or _env("DRIVE_FOLDER_ID") or DEFAULT_DRIVE_FOLDER_ID
    obsidian_folder_id = (
        args.obsidian_folder_id
        or _env("OBSIDIAN_DRIVE_FOLDER_ID")
        or DEFAULT_OBSIDIAN_DRIVE_FOLDER_ID
    )
    if sink == "obsidian" and not live:
        out_dir = args.out or _env("OUTPUT_DIR") or DEFAULT_OBSIDIAN_PREVIEW_DIR
    else:
        out_dir = args.out or _env("OUTPUT_DIR") or DEFAULT_OUTPUT_DIR

    try:
        plan = sync(
            args.input,
            live=live,
            out_dir=out_dir,
            folder_id=folder_id,
            markdown_preview=bool(args.markdown_preview),
            sink=sink,
            obsidian_folder_id=obsidian_folder_id,
        )
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    _print_plan(plan)
    return 0


def _print_plan(plan: dict) -> None:
    mode = plan.get("mode")
    imported = plan.get("imported")
    skipped = plan.get("skipped")
    print(f"sync complete ({mode})")
    print(f"  imported: {imported}")
    print(f"  skipped:  {skipped}")
    sink = plan.get("sink") or ""
    if plan.get("drive_writes"):
        print(f"  folder:   {plan.get('folder_url')}")
        appended = plan.get("appended") or {}
        if appended:
            print("  appended: " + ", ".join(f"{k}={v}" for k, v in sorted(appended.items())))
        if "obsidian" in str(sink):
            print("  markdown: text/markdown (not Google Docs)")
        index_doc = plan.get("index_doc") or {}
        if index_doc.get("url"):
            print(f"  index:    {index_doc.get('url')}")
    else:
        print(f"  output:   {plan.get('output_dir')}")
        would = plan.get("would_append") or {}
        if would:
            print("  would append: " + ", ".join(f"{k}={v}" for k, v in sorted(would.items())))
        print("  Drive writes: none (dry-run)")
    print(json.dumps({k: plan[k] for k in plan if k != "topic_docs"}, indent=2, sort_keys=True))
