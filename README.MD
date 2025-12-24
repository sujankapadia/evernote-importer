# Evernote Importer & Local Viewer

FastAPI + SQLite app that imports Evernote `.enex` exports, stores notes and attachments locally, and serves a privacy-first web UI for browsing and downloading your content.

## Features
- Upload one or many ENEX files; notes are upserted by GUID to avoid duplicates.
- Notes list sorted by last modified date (falls back to created date).
- Attachments saved locally and downloadable per note.
- Full-text data stored in SQLite FTS for search (UI uses metadata and filters today).
- Simple, zero-cloud stack: FastAPI backend, static HTML/JS frontend, single `evernote.db` file.

## Quickstart
1. Install Python 3.10+.
2. Create a virtualenv and install deps:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Run the server:
   ```bash
   uvicorn backend.main:app --reload
   ```
4. Open the UI at http://127.0.0.1:8000 and upload your `.enex` export(s).

The SQLite database lives at `evernote.db` in the project root; schema is created on startup.

## API
- `GET /api/health` – service status.
- `POST /api/import/upload` – multipart form upload; field name `files` (supports multiple). Example:
  ```bash
  curl -F "files=@/path/to/export.enex" http://127.0.0.1:8000/api/import/upload
  ```
- `GET /api/notes?limit=50&offset=0` – list notes ordered by `updated_at` desc (fallback `created_at`).
- `GET /api/notes/{id}` – note detail including HTML, text, tags, and attachments metadata.
- `GET /api/notes/{note_id}/attachments/{resource_id}` – download an attachment.

## Project Layout
- `backend/` – FastAPI app (`main.py`), importer/parser (`importer.py`), SQLite helpers (`db.py`).
- `static/` – single-page UI served by FastAPI.
- `evernote.db` – local SQLite store created automatically.

## Development Tips
- Restart the server after changing backend code to reload routes and schema.
- Imports are idempotent: re-uploading the same ENEX updates existing notes and replaces attachments.
