"""Video input routes: upload, YouTube import, listing, detail, deletion."""

from __future__ import annotations

import json
import logging
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, UploadFile

from gemma_clipper.api.models import (
    Clip,
    JobDetailResponse,
    JobResponse,
    JobStatus,
    Scene,
    YouTubeRequest,
)
from gemma_clipper.config import settings
from gemma_clipper.db import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/videos", tags=["videos"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _job_from_row(row) -> JobResponse:
    """Build a JobResponse from a database row."""
    return JobResponse(
        id=row["id"],
        status=JobStatus(row["status"]),
        source_type=row["source_type"],
        source_name=row["source_name"],
        video_duration=row["video_duration"],
        scenes_found=row["scenes_found"] or 0,
        clips_generated=row["clips_generated"] or 0,
        progress=row["progress"] or 0.0,
        error=row["error"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _scene_from_row(row) -> Scene:
    """Build a Scene from a database row."""
    tags = json.loads(row["tags_json"]) if row["tags_json"] else []
    return Scene(
        id=row["id"],
        start_time=row["start_time"],
        end_time=row["end_time"],
        duration=row["duration"],
        thumbnail_path=row["thumbnail_path"],
        description=row["description"] or "",
        interest_score=row["interest_score"] or 0.0,
        tags=tags,
        has_speech=bool(row["has_speech"]),
        has_music=bool(row["has_music"]),
        is_silent=bool(row["is_silent"]),
    )


def _clip_from_row(row) -> Clip:
    """Build a Clip from a database row."""
    source_ids = json.loads(row["source_scene_ids_json"]) if row["source_scene_ids_json"] else []
    return Clip(
        id=row["id"],
        job_id=row["job_id"],
        start_time=row["start_time"],
        end_time=row["end_time"],
        duration=row["duration"],
        source_scene_ids=source_ids,
        reason=row["reason"] or "",
        interest_score=row["interest_score"] or 0.0,
        exported_path=row["exported_path"],
        thumbnail_path=row["thumbnail_path"],
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/upload", response_model=JobResponse, status_code=201)
async def upload_video(
    file: UploadFile,
    auto_clip: bool = True,
    max_clips: int = 10,
    min_clip_duration: float = 5.0,
    max_clip_duration: float = 60.0,
) -> JobResponse:
    """Accept a multipart file upload, save it, and create a processing job."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    job_id = uuid.uuid4().hex
    upload_path = settings.upload_dir / f"{job_id}_{file.filename}"

    # Stream file to disk.
    with open(upload_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            f.write(chunk)

    config = {
        "auto_clip": auto_clip,
        "max_clips": max_clips,
        "min_clip_duration": min_clip_duration,
        "max_clip_duration": max_clip_duration,
    }

    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO jobs (id, status, source_type, source_name, source_path, config_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (job_id, JobStatus.PENDING.value, "upload", file.filename, str(upload_path), json.dumps(config)),
        )
        await db.commit()
        row = await db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        job_row = await row.fetchone()
    finally:
        await db.close()

    return _job_from_row(job_row)


@router.post("/youtube", response_model=JobResponse, status_code=201)
async def import_youtube(req: YouTubeRequest) -> JobResponse:
    """Accept a YouTube URL, create a job in 'downloading' status."""
    job_id = uuid.uuid4().hex

    config = {
        "auto_clip": req.auto_clip,
        "max_clips": req.max_clips,
        "min_clip_duration": req.min_clip_duration,
        "max_clip_duration": req.max_clip_duration,
        "youtube_url": req.url,
    }

    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO jobs (id, status, source_type, source_name, config_json)
               VALUES (?, ?, ?, ?, ?)""",
            (job_id, JobStatus.PENDING.value, "youtube", req.url, json.dumps(config)),
        )
        await db.commit()
        row = await db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        job_row = await row.fetchone()
    finally:
        await db.close()

    return _job_from_row(job_row)


@router.get("/{job_id}", response_model=JobDetailResponse)
async def get_job(job_id: str) -> JobDetailResponse:
    """Return full job details including scenes and clips."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        job_row = await cursor.fetchone()
        if not job_row:
            raise HTTPException(status_code=404, detail="Job not found.")

        scene_cursor = await db.execute(
            "SELECT * FROM scenes WHERE job_id = ? ORDER BY start_time", (job_id,)
        )
        scene_rows = await scene_cursor.fetchall()

        clip_cursor = await db.execute(
            "SELECT * FROM clips WHERE job_id = ? ORDER BY interest_score DESC", (job_id,)
        )
        clip_rows = await clip_cursor.fetchall()
    finally:
        await db.close()

    base = _job_from_row(job_row)
    return JobDetailResponse(
        **base.model_dump(),
        scenes=[_scene_from_row(r) for r in scene_rows],
        clips=[_clip_from_row(r) for r in clip_rows],
    )


@router.get("", response_model=list[JobResponse])
async def list_jobs(status: str | None = Query(default=None)) -> list[JobResponse]:
    """List all jobs, optionally filtered by status, ordered by created_at desc."""
    db = await get_db()
    try:
        if status:
            cursor = await db.execute(
                "SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC", (status,)
            )
        else:
            cursor = await db.execute("SELECT * FROM jobs ORDER BY created_at DESC")
        rows = await cursor.fetchall()
    finally:
        await db.close()

    return [_job_from_row(r) for r in rows]


@router.delete("/{job_id}", status_code=204)
async def delete_job(job_id: str) -> None:
    """Delete a job and its associated files."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        job_row = await cursor.fetchone()
        if not job_row:
            raise HTTPException(status_code=404, detail="Job not found.")

        # Delete associated DB rows (scenes, clips first due to FK).
        await db.execute("DELETE FROM clips WHERE job_id = ?", (job_id,))
        await db.execute("DELETE FROM scenes WHERE job_id = ?", (job_id,))
        await db.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        await db.commit()
    finally:
        await db.close()

    # Clean up files on disk.
    source_path = job_row["source_path"]
    if source_path:
        p = Path(source_path)
        if p.exists():
            p.unlink(missing_ok=True)

    # Remove job-specific output and thumbnail directories.
    job_output = settings.output_dir / job_id
    if job_output.exists():
        shutil.rmtree(job_output, ignore_errors=True)

    job_thumbs = settings.thumbnails_dir / job_id
    if job_thumbs.exists():
        shutil.rmtree(job_thumbs, ignore_errors=True)
