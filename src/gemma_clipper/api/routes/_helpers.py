"""Shared row-to-model helpers for route modules."""

from __future__ import annotations

import json

from gemma_clipper.api.models import Clip, JobResponse, JobStatus, Scene


def job_from_row(row) -> JobResponse:
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


def scene_from_row(row) -> Scene:
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


def clip_from_row(row) -> Clip:
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
