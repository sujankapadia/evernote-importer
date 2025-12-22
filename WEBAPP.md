# Web App Plan (Import + Note Browser Slice)

Scope for first slice: upload ENEX via file picker, ingest into SQLite/FTS5, list notes, and view a note’s full content.

## Backend (Python, FastAPI)
- **DB**: SQLite with FTS5; schema as in DESIGN.md (`notes`, `resources`, `notes_fts` + triggers).
- **Endpoints (MVP)**:
  - `POST /import/upload` (multipart): accept one/many `.enex` files; parse + import; respond with per-file stats `{file, inserted, updated, skipped, duration_ms}`.
  - `GET /notes`: list notes (paged) sorted by `created_at desc` by default. Query params: `limit`, `offset`, optional `q` (FTS) for future.
  - `GET /notes/{id}`: note detail (title, dates, tags, html, text, source_file, attachments metadata).
  - `GET /notes/{id}/attachments/{resource_id}`: stream/download attachment (BLOB or path).
  - `GET /health`: basic ready check.
- **Import flow**: stream parse ENEX; transaction per file; upsert by GUID; derive plain text for FTS; store HTML; resources optional BLOB/path; update FTS via triggers.

## Front-end (HTML/JS + Pico.css)
- Single page, two panes on desktop, stacked on mobile.
- Header: app title + “Import ENEX” button (file input `accept=.enex` `multiple`). On selection, POST to `/import/upload`, then show status (counts) and refresh list.
- Left pane: note list (title, created date, maybe tags). Scrollable; click selects a note.
- Right pane: note detail fetched from `/notes/{id}`; render HTML body; show metadata and attachments list with download links.
- Feedback: loading states on import/list/detail; error banner on failures.

## Data/UX notes
- Preserve `created`/`updated` from ENEX; record `imported_at` separately.
- Use FTS5 `notes_fts` but for this slice, search box can be deferred; list is sorted by date.
- Keep the front-end minimal vanilla JS; later add search filters/snippets.

## Running (dev)
- Install deps: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- Start: `uvicorn backend.main:app --reload`
- Open: `http://127.0.0.1:8000` (static UI). APIs are under `/api`.
