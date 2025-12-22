import sqlite3
from pathlib import Path
from typing import Iterable

DB_PATH = Path("evernote.db")


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY,
            guid TEXT UNIQUE,
            title TEXT,
            created_at INTEGER,
            updated_at INTEGER,
            tags_json TEXT,
            html TEXT,
            text TEXT,
            source_file TEXT,
            resource_count INTEGER DEFAULT 0,
            imported_at INTEGER
        );

        CREATE TABLE IF NOT EXISTS resources (
            id INTEGER PRIMARY KEY,
            note_id INTEGER NOT NULL,
            mime TEXT,
            filename TEXT,
            data BLOB,
            hash TEXT,
            FOREIGN KEY(note_id) REFERENCES notes(id) ON DELETE CASCADE
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts
        USING fts5(
            title,
            text,
            content='notes',
            content_rowid='id',
            tokenize='unicode61'
        );

        CREATE TRIGGER IF NOT EXISTS notes_ai AFTER INSERT ON notes BEGIN
            INSERT INTO notes_fts(rowid, title, text) VALUES (new.id, new.title, new.text);
        END;

        CREATE TRIGGER IF NOT EXISTS notes_ad AFTER DELETE ON notes BEGIN
            INSERT INTO notes_fts(notes_fts, rowid, title, text) VALUES ('delete', old.id, old.title, old.text);
        END;

        CREATE TRIGGER IF NOT EXISTS notes_au AFTER UPDATE ON notes BEGIN
            INSERT INTO notes_fts(notes_fts, rowid, title, text) VALUES ('delete', old.id, old.title, old.text);
            INSERT INTO notes_fts(rowid, title, text) VALUES (new.id, new.title, new.text);
        END;
        """
    )


def executemany(conn: sqlite3.Connection, query: str, rows: Iterable[tuple]) -> None:
    conn.executemany(query, rows)
