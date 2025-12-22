# Tauri Implementation Notes

This captures how to build a Rust-first Tauri app for the Evernote importer/viewer.

## Stack and crates
- `tauri` v2: app shell, commands to front-end.
- `rusqlite` with FTS5 enabled: storage and search.
- `quick-xml`: streaming ENEX parser.
- `serde`/`serde_json`: data transfer types.
- `thiserror`: error handling.
- `time` or `chrono`: timestamp parsing/formatting.
- `base64`/`hex`: attachments and hashes.
- Optional: `tracing` for logs, `rayon`/`tokio` for background work.

## Project layout
- `src/main.rs`: Tauri setup; register commands; manage shared state (DB path/handle).
- `src/state.rs`: `AppState` and database initializer (create schema/FTS triggers if missing).
- `src/storage.rs`: schema DDL, CRUD, FTS search, GUID dedupe, transactions per import.
- `src/enex.rs`: streaming ENEX parsing to `Note` structs (metadata, HTML, text, resources).
- `src/models.rs`: `Note`, `Resource`, `SearchHit`, `ImportReport`, etc.
- `src/commands.rs`: Tauri commands calling storage/parser.
- `src/events.rs`: helpers to emit progress/status events to the webview.

## Schema (SQLite/FTS5)
- `notes(id INTEGER PRIMARY KEY, guid TEXT UNIQUE, title TEXT, created_at INTEGER, updated_at INTEGER, tags_json TEXT, html TEXT, text TEXT, source_file TEXT, resource_count INTEGER, imported_at INTEGER)`
- `resources(id INTEGER PRIMARY KEY, note_id INTEGER, mime TEXT, filename TEXT, data BLOB, hash TEXT, FOREIGN KEY(note_id) REFERENCES notes(id))`
- `notes_fts USING fts5(title, text, content='notes', content_rowid='id', tokenize='unicode61')`
- Triggers to sync `notes_fts` on insert/update/delete of `notes`.
- Option: store attachments on disk instead of BLOBs; keep path + hash in `resources`.

## Commands (called via `invoke`)
```rust
#[tauri::command]
async fn import_enex(path: String, state: State<'_, AppState>) -> Result<ImportReport, AppError>;

#[tauri::command]
async fn search(query: String, limit: Option<usize>, sort: Option<String>, state: State<'_, AppState>) -> Result<Vec<SearchHit>, AppError>;

#[tauri::command]
async fn get_note(id: i64, state: State<'_, AppState>) -> Result<NoteDetail, AppError>;
```
- Use `tauri::generate_handler!` in `main.rs` to register.
- Front-end uses `invoke("import_enex", { path })` etc.; no HTTP needed.
- For long imports, run off the UI thread and emit progress via `Window::emit`.

## Import flow
- Open/create DB; ensure schema.
- Stream-parse ENEX with `quick-xml`; extract guid/title/created/updated/tags/content/resources.
- Derive plain text from XHTML for FTS; keep HTML as-is.
- Transaction per ENEX file; upsert/dedupe by GUID (skip or update).
- Insert resources (BLOBs or file paths); let triggers update FTS.
- Emit progress events every N notes.

## Search flow
- `SELECT n.id, n.title, n.created_at, bm25(f) AS rank, snippet(f, ...) AS snippet FROM notes_fts f JOIN notes n ON n.id=f.rowid WHERE f MATCH ? ... ORDER BY rank LIMIT ?;`
- Add filters (tags/created/updated/source_file) in outer `WHERE`.
- Sort by relevance by default; allow created/updated desc.

## Build/distribution notes
- Cross-platform (macOS/Windows/Linux); build per target for best results.
- Windows needs WebView2 runtime; Linux needs WebKitGTK packages; macOS uses WKWebView (sign/notarize for smooth installs).
- Bundle size is small since the webview is system-provided.
