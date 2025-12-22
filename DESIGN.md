# Evernote Exporter: Storage and Search Plan

Goal: ingest the ENEX exports, store notes locally, and provide fast full-text search and browsing.

## Recommended stack
- SQLite with FTS5 for full-text search (single-file, zero services).
- Streaming ENEX parser (avoid loading whole export in memory).
- CLI first; extend to TUI/web later if needed.

## Schema sketch
- `notes(id INTEGER PRIMARY KEY, guid TEXT UNIQUE, title TEXT, created_at INTEGER, updated_at INTEGER, tags_json TEXT, html TEXT, text TEXT, source_file TEXT, resource_count INTEGER, imported_at INTEGER)`
- `resources(id INTEGER PRIMARY KEY, note_id INTEGER, mime TEXT, filename TEXT, data BLOB, hash TEXT, FOREIGN KEY(note_id) REFERENCES notes(id))`
- `notes_fts USING fts5(title, text, content='notes', content_rowid='id', tokenize='unicode61')`
- Triggers to keep `notes_fts` in sync with `notes`.
- Optional: store attachments on disk instead of BLOB; keep path + hash in `resources`.

## Import pipeline
- Stream-parse each `.enex` file.
- Extract: GUID, title, created/updated timestamps, tags, content XHTML, attachments.
- Produce both HTML (as-is) and plain text (XHTML → text) for FTS.
- Map filename to `source_file` to track batches; keep GUID-based dedupe (skip or update existing).
- Insert notes and resources inside a transaction per file for speed.

## Search and retrieval
- Query `notes_fts` with `MATCH` and rank via `bm25(notes_fts)`.
- Join back to `notes` for metadata; use `snippet(notes_fts, ...)` for previews.
- Filters: tags, created/updated ranges, source_file, attachment presence.
- Sorting: relevance by default; allow created/updated desc for recency.

## CLI shape (initial)
- `import <file.enex>`: parse and ingest; report inserted/updated/skipped counts.
- `search "<query>" [--tag t] [--after 2023-01-01] [--limit 20] [--sort rank|created|updated]`: show title + snippet + created date.
- `show <id|guid>`: print metadata and body; optionally dump attachments to disk.
- `reindex`: rebuild FTS if needed.

## UI options (next layer)
- TUI (e.g., `fzf`-style or curses) for quick browse/search + preview.
- Local web UI: small server exposing search API + a JS frontend (list + detail, keyboard nav, snippets).
- Optional: Electron/desktop wrapper if you want packaged app feel.
- Editor integrations (VS Code extension, Neovim plugin) to search/open notes where you work.
- Launcher integrations (Alfred/Raycast/Spotlight) for quick top-result access via local search API.
- Mobile-friendly responsive view if you expose the local web UI on LAN.

## Open questions
- Attachments: keep in DB as BLOBs vs. on-disk with path? Need OCR/extra text indexing?
- Updates: should later imports update existing notes by GUID or keep latest-wins?
- Security: any need for encryption at rest for the SQLite file and attachments?
