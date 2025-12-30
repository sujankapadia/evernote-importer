#!/usr/bin/env python3
"""
Rebuild the SQLite FTS index for existing notes.

Usage:
  python rebuild_fts.py            # uses evernote.db in repo root
  python rebuild_fts.py --db /path/to/evernote.db
"""

import argparse
import sqlite3
import sys
from pathlib import Path

from backend import db


def rebuild(db_path: Path) -> int:
    conn = db.get_connection(db_path)
    try:
        # Ensure schema exists, then rebuild the FTS index from notes.
        db.init_db(conn)
        conn.execute("INSERT INTO notes_fts(notes_fts) VALUES('rebuild');")
        conn.commit()
        cur = conn.execute("SELECT COUNT(*) FROM notes_fts;")
        return cur.fetchone()[0]
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild FTS index for notes.")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("evernote.db"),
        help="Path to SQLite DB (default: evernote.db)",
    )
    args = parser.parse_args()

    try:
        count = rebuild(args.db)
    except sqlite3.Error as exc:
        sys.exit(f"Failed to rebuild FTS: {exc}")

    print(f"Rebuilt FTS index with {count} rows for {args.db}")


if __name__ == "__main__":
    main()
