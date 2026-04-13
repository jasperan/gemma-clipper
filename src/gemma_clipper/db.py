"""SQLite database layer for job and clip persistence."""

from __future__ import annotations

import aiosqlite

from gemma_clipper.config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'pending',
    source_type TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_path TEXT,
    video_duration REAL,
    scenes_found INTEGER DEFAULT 0,
    clips_generated INTEGER DEFAULT 0,
    progress REAL DEFAULT 0.0,
    error TEXT,
    config_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS scenes (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(id),
    start_time REAL NOT NULL,
    end_time REAL NOT NULL,
    duration REAL NOT NULL,
    thumbnail_path TEXT,
    description TEXT DEFAULT '',
    interest_score REAL DEFAULT 0.0,
    tags_json TEXT DEFAULT '[]',
    has_speech INTEGER DEFAULT 0,
    has_music INTEGER DEFAULT 0,
    is_silent INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS clips (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(id),
    start_time REAL NOT NULL,
    end_time REAL NOT NULL,
    duration REAL NOT NULL,
    source_scene_ids_json TEXT DEFAULT '[]',
    reason TEXT DEFAULT '',
    interest_score REAL DEFAULT 0.0,
    exported_path TEXT,
    thumbnail_path TEXT
);

CREATE INDEX IF NOT EXISTS idx_scenes_job ON scenes(job_id);
CREATE INDEX IF NOT EXISTS idx_clips_job ON clips(job_id);
"""


async def get_db() -> aiosqlite.Connection:
    """Get a database connection (caller must close)."""
    db = await aiosqlite.connect(str(settings.db_path))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db() -> None:
    """Initialize the database schema."""
    db = await get_db()
    try:
        await db.executescript(_SCHEMA)
        await db.commit()
    finally:
        await db.close()
