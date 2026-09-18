# x-bookmark

Read-only **X bookmark export → topic classify → Google Docs in Drive**.

Vault Scout (or any operator) feeds an export JSON. This repo classifies each post and appends it to **one Google Doc per topic** inside Jabba’s Drive folder. It never posts, likes, replies, unfollows, or deletes bookmarks on X. Tweet body text is copied from the export only — never invented.

Product sink: **Google Docs via Google Drive**. Local JSONL is dry-run / preview only. An optional Markdown dump exists behind `--markdown-preview` as an example renderer, not the architecture.

## Jabba’s target folder

| | |
| --- | --- |
| Name | **X Bookmarks** |
| Folder ID | `1sF85Lq7kU9y8y73GPyNqFl9I2ACayQBG` |
| URL | https://drive.google.com/drive/folders/1sF85Lq7kU9y8y73GPyNqFl9I2ACayQBG |

Live sync reads `DRIVE_FOLDER_ID` from the environment (or `--folder-id`). If both are omitted, the CLI uses this documented default. Dry-run does **not** call Drive and does **not** need credentials.

## Docs layout

Inside the folder:

| File | Role |
| --- | --- |
| `AI`, `Career`, `Fashion`, `Markets`, `Media`, `Misc` | Topic Docs |
| `needs-review` | Low-confidence / ambiguous posts |
| `_index` | Master index: topic counts + links to each Doc |
| `_import_index.json` | Dedup artifact: imported `x_id`s + Doc ids |

Each bookmark is appended as a dated `HEADING_2` section with `url`, `author`, `x_id`, `saved_at`, `topics`, `confidence`, `source`, then the **verbatim** export text.

Incremental runs skip `x_id`s already listed in `_import_index.json`.

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
| `DRIVE_FOLDER_ID` / `--folder-id` | Drive folder to write Docs into (Jabba’s id is the documented default) |
| `OUTPUT_DIR` / `--out` | Local dry-run directory (default `preview-out`) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Service-account JSON path for `--live` |
| `X_BOOKMARK_CLASSIFIER` | Optional `module:function` override for classification |

No secrets belong in git. `.env.example` is the filled folder-id example plus commented auth.

## Dry-run (no Drive)

```bash
python3 -m x_bookmark sync \
  --input fixtures/bookmarks.fixture.json \
  --dry-run \
  --out preview-out
```

Writes:

- `preview-out/records.jsonl` — structured records (`url`, `author`, `x_id`, `saved_at`, `topics`, `confidence`, `source`, `text`, `doc`)
- `preview-out/would_append_sections.jsonl` — the exact section text that would be appended to each topic Doc
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

1. Open (or confirm) the Drive folder: https://drive.google.com/drive/folders/1sF85Lq7kU9y8y73GPyNqFl9I2ACayQBG
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

`--live` creates missing topic Docs and `_index`, appends new sections, and upserts `_import_index.json` in the folder. Re-running the same export is a no-op (dedup).

Live smoke is **not** part of CI. Unit tests use an in-memory fake Drive client.

### Scopes

```
https://www.googleapis.com/auth/drive
https://www.googleapis.com/auth/documents
```

Share only the X Bookmarks folder with the service account. Do not put a JSON key in this repo.

If Vault Scout / Grok Bot already has a Google Drive connector, point that runtime at this CLI with `DRIVE_FOLDER_ID` and ADC/SA credentials — this package does not embed connector tokens.

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

No Google credentials and no network. Coverage: classify, ingest/verbatim text, dry-run dedup, fake-Drive live path + second-run skip.

## Constraints

- X: **read-only**. No post / like / reply / delete-bookmark / unfollow.
- Do not invent tweet text.
- Do not run concurrent `--live` syncs against the same folder (index read/update is not locked).

## Next steps (Jabba + Vault Scout)

1. Confirm the Drive folder above is the write target (already wired as default).
2. Issue a service account (or ADC) and share **X Bookmarks** with it; set `GOOGLE_APPLICATION_CREDENTIALS` on the bot host.
3. Point Vault Scout at `python3 -m x_bookmark sync --input <export.json> --dry-run`, then `--live` once the preview looks right.
4. Keep the X client read-only; this CLI is the Docs writer.
