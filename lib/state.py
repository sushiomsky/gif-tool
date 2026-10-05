"""SQLite upload ledger to prevent duplicate uploads.

Simplified from gifsync/state.py: keeps the hash+service upload table only.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS uploads (
    file_hash   TEXT NOT NULL,
    service     TEXT NOT NULL,
    file_path   TEXT NOT NULL,
    title       TEXT NOT NULL,
    tags_json   TEXT NOT NULL,
    remote_id   TEXT NOT NULL,
    remote_url  TEXT,
    uploaded_at TEXT NOT NULL,
    PRIMARY KEY (file_hash, service)
);
"""


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)


@contextmanager
def connect(db_path: Path):
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


def has_upload(db_path: Path, file_hash: str, service: str) -> bool:
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM uploads WHERE file_hash = ? AND service = ?",
            (file_hash, service),
        ).fetchone()
    return row is not None


def record_upload(
    db_path: Path,
    *,
    file_hash: str,
    service: str,
    file_path: Path,
    title: str,
    tags: list[str],
    remote_id: str,
    remote_url: str | None,
) -> None:
    payload = (
        file_hash,
        service,
        str(file_path),
        title,
        json.dumps(tags, ensure_ascii=True),
        remote_id,
        remote_url,
        datetime.now(timezone.utc).isoformat(),
    )
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO uploads (
                file_hash, service, file_path, title, tags_json,
                remote_id, remote_url, uploaded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(file_hash, service) DO UPDATE SET
                file_path = excluded.file_path,
                title = excluded.title,
                tags_json = excluded.tags_json,
                remote_id = excluded.remote_id,
                remote_url = excluded.remote_url,
                uploaded_at = excluded.uploaded_at
            """,
            payload,
        )
        conn.commit()


def list_uploads(db_path: Path, *, service: str | None = None) -> list[dict]:
    query = "SELECT file_hash, service, file_path, title, tags_json, remote_id, remote_url, uploaded_at FROM uploads"
    params: tuple[str, ...] = ()
    if service is not None:
        query += " WHERE service = ?"
        params = (service,)
    with connect(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [
        {
            "file_hash": row[0],
            "service": row[1],
            "file_path": row[2],
            "title": row[3],
            "tags": json.loads(row[4]),
            "remote_id": row[5],
            "remote_url": row[6],
            "uploaded_at": row[7],
        }
        for row in rows
    ]
