"""Shared pipeline constants.

Docs sink: Google Docs inside DRIVE_FOLDER_ID.
Obsidian sink: real .md files inside OBSIDIAN_DRIVE_FOLDER_ID (no Docs conversion).
Local JSONL / vault-preview are dry-run only.
"""

# Jabba's Docs folder: "X Bookmarks"
# https://drive.google.com/drive/folders/1sF85Lq7kU9y8y73GPyNqFl9I2ACayQBG
DEFAULT_DRIVE_FOLDER_ID = "1sF85Lq7kU9y8y73GPyNqFl9I2ACayQBG"
DEFAULT_DRIVE_FOLDER_URL = (
    f"https://drive.google.com/drive/folders/{DEFAULT_DRIVE_FOLDER_ID}"
)
DEFAULT_DRIVE_FOLDER_NAME = "X Bookmarks"

# Jabba's Obsidian vault (phone): "Obsidian Vault - X Bookmarks"
# https://drive.google.com/drive/folders/1fzceV_WpXsNSOwNk_GgiXhlP2D668li6
DEFAULT_OBSIDIAN_DRIVE_FOLDER_ID = "1fzceV_WpXsNSOwNk_GgiXhlP2D668li6"
DEFAULT_OBSIDIAN_DRIVE_FOLDER_URL = (
    f"https://drive.google.com/drive/folders/{DEFAULT_OBSIDIAN_DRIVE_FOLDER_ID}"
)
DEFAULT_OBSIDIAN_DRIVE_FOLDER_NAME = "Obsidian Vault - X Bookmarks"

# One Google Doc per name, plus a master index Doc.
TOPIC_DOCS = (
    "AI",
    "Career",
    "Fashion",
    "Markets",
    "Media",
    "Misc",
)
NEEDS_REVIEW = "needs-review"
ALL_DOC_NAMES = TOPIC_DOCS + (NEEDS_REVIEW,)

INDEX_DOC_NAME = "_index"
INDEX_NOTE_NAME = "Index.md"
IMPORT_INDEX_NAME = "_import_index.json"
MARKDOWN_MIME = "text/markdown"

SOURCE = "x-bookmark"

# File a bookmark into a topic Doc at or above this confidence.
FILE_CONFIDENCE_THRESHOLD = 60

DEFAULT_OUTPUT_DIR = "preview-out"
DEFAULT_OBSIDIAN_PREVIEW_DIR = "vault-preview"
