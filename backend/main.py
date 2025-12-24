from typing import List, Optional
from tempfile import NamedTemporaryFile
from pathlib import Path
import json

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .importer import import_enex_file

app = FastAPI(title="Evernote Exporter")


@app.on_event("startup")
def startup_event() -> None:
    conn = db.get_connection()
    db.init_db(conn)
    conn.close()


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/import/upload")
async def import_upload(files: List[UploadFile] = File(...)) -> dict:
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    conn = db.get_connection()
    results = []
    for upload in files:
        if not upload.filename.lower().endswith(".enex"):
            raise HTTPException(status_code=400, detail=f"Unsupported file: {upload.filename}")
        with NamedTemporaryFile(delete=True) as tmp:
            await _copy_upload(upload, tmp.name)
            stats = import_enex_file(conn, Path(tmp.name), source_name=upload.filename)
            stats["original_name"] = upload.filename
            results.append(stats)

    conn.close()
    return {"imports": results}


async def _copy_upload(upload: UploadFile, dest_path: str) -> None:
    with open(dest_path, "wb") as dest:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            dest.write(chunk)


@app.get("/api/notes")
def list_notes(limit: int = 0, offset: int = 0) -> dict:
    conn = db.get_connection()
    cur = conn.cursor()
    if limit and limit > 0:
        cur.execute(
            """
            SELECT id, guid, title, created_at, updated_at, tags_json, source_file, resource_count
            FROM notes
            ORDER BY COALESCE(updated_at, created_at) DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        )
    else:
        cur.execute(
            """
            SELECT id, guid, title, created_at, updated_at, tags_json, source_file, resource_count
            FROM notes
            ORDER BY COALESCE(updated_at, created_at) DESC, id DESC
            """
        )
    rows = cur.fetchall()
    conn.close()
    notes = []
    for row in rows:
        notes.append(
            {
                "id": row["id"],
                "guid": row["guid"],
                "title": row["title"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "tags": json_load(row["tags_json"]),
                "source_file": row["source_file"],
                "resource_count": row["resource_count"],
            }
        )
    return {"notes": notes}


@app.get("/api/notes/{note_id}")
def get_note(note_id: int) -> dict:
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, guid, title, created_at, updated_at, tags_json, html, text, source_file
        FROM notes WHERE id = ?
        """,
        (note_id,),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Note not found")

    cur.execute(
        """
        SELECT id, mime, filename, length(data) AS size
        FROM resources WHERE note_id = ?
        """,
        (note_id,),
    )
    resources = [
        {
            "id": r["id"],
            "mime": r["mime"],
            "filename": r["filename"],
            "size": r["size"],
        }
        for r in cur.fetchall()
    ]
    note = {
        "id": row["id"],
        "guid": row["guid"],
        "title": row["title"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "tags": json_load(row["tags_json"]),
        "html": row["html"],
        "text": row["text"],
        "source_file": row["source_file"],
        "resources": resources,
    }
    conn.close()
    return note


@app.get("/api/notes/{note_id}/attachments/{resource_id}")
def download_attachment(note_id: int, resource_id: int):
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT data, filename, mime FROM resources
        WHERE id = ? AND note_id = ?
        """,
        (resource_id, note_id),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Attachment not found")
    data = row["data"]
    filename = row["filename"] or f"attachment-{resource_id}"
    mime = row["mime"] or "application/octet-stream"
    return FileResponse(
        path=_write_temp_file(data, filename),
        media_type=mime,
        filename=filename,
    )


def _write_temp_file(data: bytes, filename: str) -> str:
    tmp = NamedTemporaryFile(delete=False)
    tmp.write(data)
    tmp.flush()
    tmp.close()
    return tmp.name


def json_load(raw: Optional[str]) -> list:
    if not raw:
        return []
    try:
        import json

        return json.loads(raw)
    except Exception:
        return []


app.mount("/", StaticFiles(directory="static", html=True), name="static")
