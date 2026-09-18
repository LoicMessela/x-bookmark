"""Shared pipeline constants.

Sink is Google Docs inside a Drive folder. Local JSONL is dry-run / preview only.
"""

# Jabba's target folder: "X Bookmarks"
# https://drive.google.com/drive/folders/1sF85Lq7kU9y8y73GPyNqFl9I2ACayQBG
DEFAULT_DRIVE_FOLDER_ID = "1sF85Lq7kU9y8y73GPyNqFl9I2ACayQBG"
DEFAULT_DRIVE_FOLDER_URL = (
    f"https://drive.google.com/drive/folders/{DEFAULT_DRIVE_FOLDER_ID}"
)
DEFAULT_DRIVE_FOLDER_NAME = "X Bookmarks"

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
IMPORT_INDEX_NAME = "_import_index.json"

SOURCE = "x-bookmark"

# File a bookmark into a topic Doc at or above this confidence.
FILE_CONFIDENCE_THRESHOLD = 60

DEFAULT_OUTPUT_DIR = "preview-out"
