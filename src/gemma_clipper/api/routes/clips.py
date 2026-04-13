"""Clip management routes: listing, export, scenes, custom clips, download."""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from gemma_clipper.api.models import Clip, ExportRequest, Scene
from gemma_clipper.config import settings
from gemma_clipper.core.export import ExportOptions, export_clip
from gemma_clipper.db import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/clips", tags=["clips"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


async def _get_job_or_404(job_id: str):
    """Fetch a job row or raise 404."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = await cursor.fetchone()
    finally:
        await db.close()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found.")
    return row


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/{job_id}", response_model=list[Clip])
async def list_clips(job_id: str) -> list[Clip]:
    """Return all clips for a job, sorted by interest_score descending."""
    await _get_job_or_404(job_id)

    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM clips WHERE job_id = ? ORDER BY interest_score DESC", (job_id,)
        )
        rows = await cursor.fetchall()
    finally:
        await db.close()

    return [_clip_from_row(r) for r in rows]


@router.post("/{job_id}/export", response_model=list[str])
async def export_clips(job_id: str, req: ExportRequest) -> list[str]:
    """Export clips (all or a subset) and return their file paths."""
    job_row = await _get_job_or_404(job_id)

    source_path = job_row["source_path"]
    if not source_path or not Path(source_path).exists():
        raise HTTPException(status_code=400, detail="Source video file not found.")

    db = await get_db()
    try:
        if req.clip_ids:
            placeholders = ",".join("?" for _ in req.clip_ids)
            cursor = await db.execute(
                f"SELECT * FROM clips WHERE job_id = ? AND id IN ({placeholders})",
                (job_id, *req.clip_ids),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM clips WHERE job_id = ? ORDER BY interest_score DESC", (job_id,)
            )
        clip_rows = await cursor.fetchall()
    finally:
        await db.close()

    if not clip_rows:
        raise HTTPException(status_code=404, detail="No clips found to export.")

    opts = ExportOptions(
        format=req.format.value,
        crf=req.crf,
        max_width=req.max_width or settings.max_resolution_width,
        aspect_ratio=req.aspect_ratio.value,
    )

    output_dir = settings.output_dir / job_id
    output_dir.mkdir(parents=True, exist_ok=True)

    exported_paths: list[str] = []
    db = await get_db()
    try:
        for row in clip_rows:
            clip_id = row["id"]
            ext = req.format.value
            out_path = output_dir / f"{clip_id}.{ext}"

            await export_clip(
                source=Path(source_path),
                start=row["start_time"],
                end=row["end_time"],
                output=out_path,
                options=opts,
            )

            # Update the clip's exported_path in DB.
            await db.execute(
                "UPDATE clips SET exported_path = ? WHERE id = ?",
                (str(out_path), clip_id),
            )
            exported_paths.append(str(out_path))

        await db.commit()
    finally:
        await db.close()

    return exported_paths


@router.get("/{job_id}/scenes", response_model=list[Scene])
async def list_scenes(job_id: str) -> list[Scene]:
    """Return ranked scenes with thumbnails for a job."""
    await _get_job_or_404(job_id)

    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM scenes WHERE job_id = ? ORDER BY interest_score DESC", (job_id,)
        )
        rows = await cursor.fetchall()
    finally:
        await db.close()

    return [_scene_from_row(r) for r in rows]


@router.post("/{job_id}/custom", response_model=Clip, status_code=201)
async def create_custom_clip(
    job_id: str,
    start_time: float,
    end_time: float,
    reason: str = "Manual selection",
) -> Clip:
    """Create a custom clip from manual start/end time selection."""
    await _get_job_or_404(job_id)

    if end_time <= start_time:
        raise HTTPException(status_code=400, detail="end_time must be greater than start_time.")

    clip_id = uuid.uuid4().hex
    duration = round(end_time - start_time, 3)

    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO clips (id, job_id, start_time, end_time, duration, reason, interest_score)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (clip_id, job_id, start_time, end_time, duration, reason, 0.0),
        )
        await db.commit()

        cursor = await db.execute("SELECT * FROM clips WHERE id = ?", (clip_id,))
        row = await cursor.fetchone()
    finally:
        await db.close()

    return _clip_from_row(row)


@router.get("/download/{clip_id}", response_model=None)
async def download_clip(clip_id: str) -> FileResponse:
    """Serve an exported clip file for download."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM clips WHERE id = ?", (clip_id,))
        row = await cursor.fetchone()
    finally:
        await db.close()

    if not row:
        raise HTTPException(status_code=404, detail="Clip not found.")

    exported_path = row["exported_path"]
    if not exported_path or not Path(exported_path).exists():
        raise HTTPException(status_code=404, detail="Clip has not been exported yet.")

    return FileResponse(
        path=exported_path,
        media_type="application/octet-stream",
        filename=Path(exported_path).name,
    )
