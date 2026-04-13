"""Video input routes: upload, YouTube import, listing, detail, deletion."""

from __future__ import annotations

import json
import logging
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, UploadFile

from gemma_clipper.api.models import (
    JobDetailResponse,
    JobResponse,
    JobStatus,
    YouTubeRequest,
)
from gemma_clipper.api.routes._helpers import clip_from_row, job_from_row, scene_from_row
from gemma_clipper.config import settings
from gemma_clipper.db import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/videos", tags=["videos"])


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

    return job_from_row(job_row)


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

    return job_from_row(job_row)


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

    base = job_from_row(job_row)
    return JobDetailResponse(
        **base.model_dump(),
        scenes=[scene_from_row(r) for r in scene_rows],
        clips=[clip_from_row(r) for r in clip_rows],
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

    return [job_from_row(r) for r in rows]


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
