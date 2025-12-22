import base64
import json
import sqlite3
import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable, List, Optional
from xml.etree import ElementTree as ET


@dataclass
class Resource:
    mime: Optional[str] = None
    filename: Optional[str] = None
    data: bytes = b""
    hash: Optional[str] = None


@dataclass
class Note:
    guid: str
    title: str
    created_at: Optional[int]
    updated_at: Optional[int]
    tags: List[str]
    html: str
    text: str
    resources: List[Resource] = field(default_factory=list)
    source_file: str = ""


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: List[str] = []

    def handle_data(self, data: str) -> None:
        if data and data.strip():
            self.parts.append(data.strip())

    def get_text(self) -> str:
        return " ".join(self.parts)


def parse_timestamp(raw: Optional[str]) -> Optional[int]:
    if not raw:
        return None
    try:
        dt = datetime.strptime(raw.strip(), "%Y%m%dT%H%M%SZ")
        return int(dt.timestamp())
    except Exception:
        return None


def extract_text_from_html(html: str) -> str:
    parser = TextExtractor()
    parser.feed(html)
    return parser.get_text()


def parse_enex(file_path: Path, source_file: str) -> Iterable[Note]:
    """
    Stream parse an ENEX file and yield Note objects.
    """
    context = ET.iterparse(file_path, events=("end",))
    for event, elem in context:
        if elem.tag != "note":
            continue

        raw_guid = (elem.findtext("guid") or "").strip()
        title = (elem.findtext("title") or "").strip()
        created_at = parse_timestamp(elem.findtext("created"))
        updated_at = parse_timestamp(elem.findtext("updated"))
        tags = [t.text.strip() for t in elem.findall("tag") if t.text]

        content_elem = elem.find("content")
        html = content_elem.text or ""
        text = extract_text_from_html(html)

        resources: List[Resource] = []
        for res_elem in elem.findall("resource"):
            data_elem = res_elem.find("data")
            data = b""
            if data_elem is not None and data_elem.text:
                try:
                    data = base64.b64decode(data_elem.text, validate=False)
                except Exception:
                    data = b""
            mime = res_elem.findtext("mime")
            attrs = res_elem.find("resource-attributes")
            filename = attrs.findtext("file-name") if attrs is not None else None
            hash_elem = res_elem.find("recognition")
            resources.append(
                Resource(
                    mime=mime.strip() if mime else None,
                    filename=filename.strip() if filename else None,
                    data=data,
                    hash=hash_elem.text.strip() if hash_elem is not None and hash_elem.text else None,
                )
            )

        guid = derive_guid(raw_guid, title, created_at, updated_at, html)
        yield Note(
            guid=guid,
            title=title,
            created_at=created_at,
            updated_at=updated_at,
            tags=tags,
            html=html,
            text=text,
            resources=resources,
            source_file=source_file,
        )

        # free memory
        elem.clear()


def derive_guid(raw_guid: str, title: str, created_at: Optional[int], updated_at: Optional[int], html: str) -> str:
    if raw_guid:
        return raw_guid
    # Create a deterministic surrogate ID based on note contents and timestamps.
    hasher = hashlib.sha1()
    hasher.update((title or "").encode("utf-8"))
    hasher.update(str(created_at or "").encode("utf-8"))
    hasher.update(str(updated_at or "").encode("utf-8"))
    hasher.update((html or "").encode("utf-8"))
    return hasher.hexdigest()


def upsert_note(conn: sqlite3.Connection, note: Note, imported_at: int) -> str:
    """
    Insert or update a note by GUID. Returns 'inserted' or 'updated'.
    """
    cur = conn.cursor()
    cur.execute("SELECT id FROM notes WHERE guid = ?", (note.guid,))
    row = cur.fetchone()
    tags_json = json.dumps(note.tags)
    resource_count = len(note.resources)

    if row:
        note_id = row["id"]
        cur.execute(
            """
            UPDATE notes SET
                title = ?,
                created_at = ?,
                updated_at = ?,
                tags_json = ?,
                html = ?,
                text = ?,
                source_file = ?,
                resource_count = ?,
                imported_at = ?
            WHERE id = ?
            """,
            (
                note.title,
                note.created_at,
                note.updated_at,
                tags_json,
                note.html,
                note.text,
                note.source_file,
                resource_count,
                imported_at,
                note_id,
            ),
        )
        cur.execute("DELETE FROM resources WHERE note_id = ?", (note_id,))
        status = "updated"
    else:
        cur.execute(
            """
            INSERT INTO notes (guid, title, created_at, updated_at, tags_json, html, text, source_file, resource_count, imported_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                note.guid,
                note.title,
                note.created_at,
                note.updated_at,
                tags_json,
                note.html,
                note.text,
                note.source_file,
                resource_count,
                imported_at,
            ),
        )
        note_id = cur.lastrowid
        status = "inserted"

    if note.resources:
        cur.executemany(
            """
            INSERT INTO resources (note_id, mime, filename, data, hash)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (note_id, res.mime, res.filename, res.data, res.hash)
                for res in note.resources
            ],
        )

    return status


def import_enex_file(conn: sqlite3.Connection, file_path: Path, source_name: Optional[str] = None) -> dict:
    """
    Import a single ENEX file; returns stats dict.
    """
    source_file = source_name or file_path.name
    inserted = updated = skipped = 0
    started = time.time()
    imported_at = int(started)

    with conn:
        for note in parse_enex(file_path, source_file=source_file):
            status = upsert_note(conn, note, imported_at)
            if status == "inserted":
                inserted += 1
            elif status == "updated":
                updated += 1
            else:
                skipped += 1

    duration_ms = int((time.time() - started) * 1000)
    return {
        "file": source_file,
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "duration_ms": duration_ms,
    }
