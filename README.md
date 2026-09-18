# x-bookmark

Read-only **X bookmark export → topic classify → Google Docs or Obsidian Markdown on Drive**.

Vault Scout (or any operator) feeds an export JSON. This repo classifies each post and writes it to **one of two sinks** you select:

1. **Docs (default)** — Google Docs inside Jabba’s **X Bookmarks** Drive folder.
2. **Obsidian** — real `.md` files inside **Obsidian Vault - X Bookmarks** (phone Obsidian; not a computer vault path). Uploads stay Markdown (`text/markdown`). They are **not** converted to Google Docs.

It never posts, likes, replies, unfollows, or deletes bookmarks on X. Tweet body text is copied from the export only — never invented.

Local JSONL (`preview-out`) is Docs dry-run. Obsidian dry-run writes `vault-preview/`. `--markdown-preview` is an example renderer for the Docs path, not the Obsidian sink.

## Choose a sink (Vault Scout)

| Mode | How | Where it writes |
| --- | --- | --- |
| Docs dry-run (default) | `sync --input export.json` | `preview-out/` JSONL, no Drive |
| Docs live | `sync --input export.json --live` | Google Docs in `DRIVE_FOLDER_ID` |
| Obsidian dry-run | `sync --input export.json --sink obsidian` (or `--obsidian`) | `vault-preview/` `.md` tree, no Drive |
| Obsidian live | `sync --input export.json --sink obsidian --live` | `.md` files in `OBSIDIAN_DRIVE_FOLDER_ID` |

Docs remains the default when `--sink` / `--obsidian` / `X_BOOKMARK_SINK` are omitted. `--obsidian` cannot be combined with `--sink docs`.

## Jabba’s Drive folders

### Docs — Google Docs

| | |
| --- | --- |
| Name | **X Bookmarks** |
| Folder ID | `1sF85Lq7kU9y8y73GPyNqFl9I2ACayQBG` |
| URL | https://drive.google.com/drive/folders/1sF85Lq7kU9y8y73GPyNqFl9I2ACayQBG |
| Env | `DRIVE_FOLDER_ID` / `--folder-id` |

### Obsidian — Markdown vault (phone)

| | |
| --- | --- |
| Name | **Obsidian Vault - X Bookmarks** |
| Folder ID | `1fzceV_WpXsNSOwNk_GgiXhlP2D668li6` |
| URL | https://drive.google.com/drive/folders/1fzceV_WpXsNSOwNk_GgiXhlP2D668li6 |
| Env | `OBSIDIAN_DRIVE_FOLDER_ID` / `--obsidian-folder-id` |

Live sync uses those ids when flags/env are omitted. Dry-run does **not** call Drive and does **not** need credentials. Share **both** folders with the service account if Vault Scout runs both sinks.

Obsidian is phone-only: point the phone vault at the Obsidian Drive folder. There is no `OBSIDIAN_VAULT_PATH` on a computer.

## Docs layout

Inside the folder:

| File | Role |
| --- | --- |
| `AI`, `Career`, `Fashion`, `Markets`, `Media`, `Misc` | Topic Docs |
| `needs-review` | Low-confidence / ambiguous posts |
| `_index` | Master index: topic counts + links to each Doc |
| `_import_index.json` | Dedup artifact: imported `x_id`s + Doc ids |

Each bookmark is a dated `HEADING_2` section with `url`, `author`, `x_id`, `saved_at`, `topics`, `confidence`, `source`, then the **verbatim** export text. Every Doc starts with a **Glossary / TOC**; entries are **newest `saved_at` first**. The Index glossary links sibling topic Docs.

Incremental runs skip `x_id`s already listed in `_import_index.json`.

## Obsidian layout

Inside **Obsidian Vault - X Bookmarks** (mirrored under `vault-preview/` on dry-run):

| Path | Role |
| --- | --- |
| `Index.md` | MOC: glossary/TOC at top, then topic lists (newest first within each topic) |
| `AI/`, `Career/`, `Fashion/`, `Markets/`, `Media/`, `Misc/`, `needs-review/` | Topic folders |
| `{Topic}/{Topic}.md` | Topic note with glossary/TOC at top, contents newest-first |
| `{Topic}/{date}-{author}-{x_id}.md` | One bookmark note (YAML frontmatter + verbatim text) |
| `_import_index.json` | Dedup: imported `x_id`s (same contract as the Docs sink; separate file) |

Frontmatter fields: `url`, `author`, `x_id`, `saved_at`, `topics[]`, `source: x-bookmark` (confidence optional).

Live Obsidian uses Drive `files.create` / `files.update` with mime **`text/markdown`**. It never uses `application/vnd.google-apps.document`.

## Install

Python 3.9+. Dry-run uses the stdlib only.

```bash
cd x-bookmark
python3 -m x_bookmark sync --help
```

Optional, for `--live` Drive writes:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[drive]"
```

Copy env template (already filled with Jabba’s folder id):

```bash
cp .env.example .env
# .env is gitignored. Do not commit keys or tokens.
```

## Config

| Variable / flag | Purpose |
| --- | --- |
| `--sink docs\|obsidian` / `--obsidian` / `X_BOOKMARK_SINK` | Choose Docs (default) or Obsidian |
| `DRIVE_FOLDER_ID` / `--folder-id` | Docs Drive folder (Jabba’s Docs id is the default) |
| `OBSIDIAN_DRIVE_FOLDER_ID` / `--obsidian-folder-id` | Obsidian Markdown Drive folder (Jabba’s vault id is the default) |
| `OUTPUT_DIR` / `--out` | Local dry-run directory (`preview-out` for Docs, `vault-preview` for Obsidian) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Service-account JSON path for `--live` |
| `X_BOOKMARK_CLASSIFIER` | Optional `module:function` override for classification |

No secrets belong in git. `.env.example` is the filled folder-id example plus commented auth.

## Dry-run (no Drive)

Docs (default):

```bash
python3 -m x_bookmark sync \
  --input fixtures/bookmarks.fixture.json \
  --dry-run \
  --out preview-out
```

Obsidian:

```bash
python3 -m x_bookmark sync \
  --input fixtures/bookmarks.fixture.json \
  --sink obsidian \
  --out vault-preview
```

Writes `vault-preview/Index.md` plus topic folders. Inspect glossary/TOC and newest-first ordering there.

Docs dry-run also writes:

- `preview-out/records.jsonl` — structured records (`url`, `author`, `x_id`, `saved_at`, `topics`, `confidence`, `source`, `text`, `doc`)
- `preview-out/would_append_sections.jsonl` — the exact section text that would be written to each topic Doc
- `preview-out/plan.json` — folder id/url, counts, `drive_writes: false`
- `preview-out/_import_index.json` — local dedup index

`--dry-run` is the default when `--live` is omitted. Dry-run never requires Google libraries or credentials.

### Dedup proof

Run the same command again against the same `--out` directory. The second run reports `imported: 0` and `skipped: 5` (fixture has five posts) because those `x_id`s are already in `_import_index.json`.

```bash
python3 -m x_bookmark sync -i fixtures/bookmarks.fixture.json --dry-run --out preview-out
python3 -m x_bookmark sync -i fixtures/bookmarks.fixture.json --dry-run --out preview-out
```

## Live sync (Google Docs)

1. Open (or confirm) the **Docs** Drive folder: https://drive.google.com/drive/folders/1sF85Lq7kU9y8y73GPyNqFl9I2ACayQBG
2. Copy the folder id into `.env` as `DRIVE_FOLDER_ID` (already filled in `.env.example`).
3. Auth (pick one; do not commit the files):
   - **Service account (bots / Vault Scout):** create a Google Cloud service account, download the JSON key, share the **X Bookmarks** folder with the SA email (Editor). Then `export GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/service-account.json`.
   - **User ADC (laptop):** `gcloud auth application-default login` with Drive + Docs scopes.
4. Dry-run a real export first (`--dry-run`). Inspect `records.jsonl` — text must match the export.
5. Then write Docs:

```bash
set -a && source .env && set +a
pip install -e ".[drive]"   # once
python3 -m x_bookmark sync --input path/to/export.json --live
```

`--live` (Docs sink) creates missing topic Docs and `_index`, rewrites glossary/TOC with newest-first sections, and upserts `_import_index.json` in the folder. Re-running the same export is a no-op (dedup).

## Live sync (Obsidian Markdown on Drive)

1. Open the **Obsidian** Drive folder: https://drive.google.com/drive/folders/1fzceV_WpXsNSOwNk_GgiXhlP2D668li6
2. Confirm `OBSIDIAN_DRIVE_FOLDER_ID` in `.env` (already filled in `.env.example`).
3. Share that folder with the same service account used for Docs (Editor).
4. Dry-run first (`--sink obsidian`). Inspect `vault-preview/`.
5. Then upload `.md` files:

```bash
set -a && source .env && set +a
pip install -e ".[drive]"   # once
python3 -m x_bookmark sync --input path/to/export.json --sink obsidian --live
```

`--sink obsidian --live` upserts `Index.md`, topic folders, bookmark notes, and `_import_index.json` as **Markdown/JSON files**. Google Docs conversion is disabled (mime `text/markdown`). Point phone Obsidian at this folder.

Live smoke is **not** part of CI. Unit tests use an in-memory fake Drive client.

### Scopes

```
https://www.googleapis.com/auth/drive
https://www.googleapis.com/auth/documents
```

Share only the X Bookmarks **Docs** folder and/or the Obsidian vault folder with the service account. Do not put a JSON key in this repo.

If Vault Scout / Grok Bot already has a Google Drive connector, point that runtime at this CLI with the matching folder id (`DRIVE_FOLDER_ID` vs `OBSIDIAN_DRIVE_FOLDER_ID`) and ADC/SA credentials — this package does not embed connector tokens.

## Export JSON (input)

Vault Scout shape:

```json
{
  "count": 196,
  "pages_fetched": 1,
  "posts": [
    {
      "id": "2100251243755061566",
      "author_id": "...",
      "author": "mathieuhq",
      "author_name": "mathieu",
      "created_at": "2026-09-16T15:51:31.000Z",
      "text": "...",
      "url": "https://x.com/i/web/status/2100251243755061566"
    }
  ]
}
```

`fixtures/bookmarks.fixture.json` is synthetic and labeled `[FIXTURE]`. It is not a live bookmark dump. `saved_at` in output uses export `saved_at` when present, otherwise tweet `created_at`.

## Classification

Default is offline keyword heuristics in `x_bookmark/classify.py`.

- Strong single-topic match → that topic Doc (`AI`, `Career`, `Fashion`, `Markets`, `Media`, `Misc`)
- No hits, low confidence, or a near-tie → `needs-review` (guessed topics still recorded when available)

Confidence is 0–100. Filing into a topic Doc requires ≥ 60.

To plug a better classifier (LLM or otherwise) later without changing the sink:

```bash
export X_BOOKMARK_CLASSIFIER=my_package.mod:classify
```

The callable must accept the export `post` dict and return `x_bookmark.classify.Classification` (`doc`, `topics`, `confidence`, `reason`).

## Tests

```bash
python3 -m unittest discover -s tests -v
```

No Google credentials and no network. Coverage: classify, ingest/verbatim text, Docs dry-run dedup, fake-Drive Docs live + TOC/newest-first, Obsidian dry-run `vault-preview` layout, fake-Drive Obsidian `.md` upload (not Docs mime).

## Constraints

- X: **read-only**. No post / like / reply / delete-bookmark / unfollow.
- Do not invent tweet text.
- Do not run concurrent `--live` syncs against the same folder (index read/update is not locked).

## Next steps (Jabba + Vault Scout)

1. Docs: confirm the Drive folder above is the Google Docs write target (already wired as default).
2. Obsidian: point **phone** Obsidian at https://drive.google.com/drive/folders/1fzceV_WpXsNSOwNk_GgiXhlP2D668li6 (`OBSIDIAN_DRIVE_FOLDER_ID` is the documented default).
3. Issue a service account (or ADC) and share **both** folders; set `GOOGLE_APPLICATION_CREDENTIALS` on the bot host.
4. Vault Scout Docs path: `python3 -m x_bookmark sync --input <export.json> --dry-run`, then `--live`.
5. Vault Scout Obsidian path: same with `--sink obsidian` (dry-run), then `--sink obsidian --live`.
6. Keep the X client read-only; this CLI is the Docs / Markdown writer.
