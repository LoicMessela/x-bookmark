from __future__ import annotations

from x_bookmark.sinks.drive_docs import DriveDocsSink, FakeDriveClient, GoogleDriveClient
from x_bookmark.sinks.obsidian import ObsidianSink
from x_bookmark.sinks.preview import PreviewSink

__all__ = [
    "DriveDocsSink",
    "FakeDriveClient",
    "GoogleDriveClient",
    "ObsidianSink",
    "PreviewSink",
]
