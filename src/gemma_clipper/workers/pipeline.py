"""Async job processing pipeline: polls for pending jobs and runs the full pipeline."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from pathlib import Path

from gemma_clipper.ai.analyzer import VideoAnalysis, analyze_video
from gemma_clipper.ai.gemma_client import GemmaClient
from gemma_clipper.ai.ranker import rank_scenes, select_best_clips
from gemma_clipper.config import settings
from gemma_clipper.core.scenes import detect_scenes
from gemma_clipper.core.silence import detect_silence
from gemma_clipper.core.video import extract_frame, probe_video
from gemma_clipper.core.youtube import download_video
from gemma_clipper.db import get_db

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 2.0  # seconds


async def start_worker() -> None:
    """Background loop that polls for pending jobs and processes them one at a time."""
    logger.info("Worker started, polling every %.1fs.", _POLL_INTERVAL)
    while True:
        try:
            job_id = await _next_pending_job()
            if job_id:
                logger.info("Processing job %s", job_id)
                await process_job(job_id)
                logger.info("Finished job %s", job_id)
            else:
                await asyncio.sleep(_POLL_INTERVAL)
        except asyncio.CancelledError:
            logger.info("Worker cancelled, shutting down.")
            raise
        except Exception:
            logger.exception("Unexpected error in worker loop.")
            await asyncio.sleep(_POLL_INTERVAL)


async def _next_pending_job() -> str | None:
    """Return the oldest pending job ID, or None."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id FROM jobs WHERE status = ? ORDER BY created_at ASC LIMIT 1",
            ("pending",),
        )
        row = await cursor.fetchone()
    finally:
        await db.close()
    return row["id"] if row else None


async def _update_job(
    job_id: str,
    *,
    status: str | None = None,
    progress: float | None = None,
    error: str | None = None,
    **extras: object,
) -> None:
    """Update job fields in the database."""
    sets: list[str] = ["updated_at = datetime('now')"]
    params: list[object] = []

    if status is not None:
        sets.append("status = ?")
        params.append(status)
    if progress is not None:
        sets.append("progress = ?")
        params.append(progress)
    if error is not None:
        sets.append("error = ?")
        params.append(error)

    for col, val in extras.items():
        sets.append(f"{col} = ?")
        params.append(val)

    params.append(job_id)
    sql = f"UPDATE jobs SET {', '.join(sets)} WHERE id = ?"

    db = await get_db()
    try:
        await db.execute(sql, params)
        await db.commit()
    finally:
        await db.close()


async def process_job(job_id: str) -> None:
    """Run the full processing pipeline for a single job."""
    # Load job config.
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        job_row = await cursor.fetchone()
    finally:
        await db.close()

    if not job_row:
        logger.error("Job %s not found.", job_id)
        return

    config = json.loads(job_row["config_json"]) if job_row["config_json"] else {}
    source_type = job_row["source_type"]
    source_path = job_row["source_path"]

    try:
        # ---- Step 1: YouTube download (if needed) ----
        if source_type == "youtube":
            youtube_url = config.get("youtube_url", job_row["source_name"])
            await _update_job(job_id, status="downloading", progress=0.05)

            result = await download_video(youtube_url, settings.upload_dir)
            source_path = str(result.path)

            await _update_job(
                job_id,
                progress=0.15,
                source_path=source_path,
                source_name=result.title or youtube_url,
            )

        # ---- Step 2: Probe video metadata ----
        await _update_job(job_id, status="processing", progress=0.20)
        video_path = Path(source_path)
        meta = await probe_video(video_path)

        await _update_job(job_id, progress=0.25, video_duration=meta.duration)

        # ---- Step 3: Detect scenes ----
        scene_boundaries = await detect_scenes(video_path, threshold=settings.scene_threshold)
        logger.info("Job %s: detected %d scenes.", job_id, len(scene_boundaries))

        await _update_job(job_id, progress=0.35)

        # ---- Step 4: Detect silence ----
        silence_regions = await detect_silence(
            video_path,
            threshold_db=settings.silence_threshold_db,
            min_duration=settings.silence_min_duration,
        )
        logger.info("Job %s: detected %d silence regions.", job_id, len(silence_regions))

        await _update_job(job_id, progress=0.45)

        # ---- Step 5: Generate scene thumbnails ----
        thumb_dir = settings.thumbnails_dir / job_id
        thumb_dir.mkdir(parents=True, exist_ok=True)

        scene_records: list[dict] = []
        for idx, sb in enumerate(scene_boundaries):
            scene_id = uuid.uuid4().hex
            midpoint = (sb.start_time + sb.end_time) / 2.0
            thumb_path = thumb_dir / f"{scene_id}.jpg"

            try:
                await extract_frame(video_path, midpoint, thumb_path)
            except Exception:
                logger.warning("Failed to extract thumbnail for scene %d.", idx)
                thumb_path = None

            # Determine silence overlap for this scene.
            is_silent = _scene_overlaps_silence(sb.start_time, sb.end_time, silence_regions)

            scene_records.append({
                "id": scene_id,
                "start_time": sb.start_time,
                "end_time": sb.end_time,
                "duration": sb.duration,
                "thumbnail_path": str(thumb_path) if thumb_path else None,
                "is_silent": is_silent,
            })

        await _update_job(job_id, progress=0.50)

        # ---- Step 6: AI analysis ----
        await _update_job(job_id, status="analyzing", progress=0.55)

        async with GemmaClient() as client:
            analysis: VideoAnalysis = await analyze_video(
                client,
                video_path,
                scenes=scene_records,
                total_duration=meta.duration,
            )

        await _update_job(job_id, progress=0.75)

        # ---- Step 7: Merge analysis results into scene records ----
        for rec, chunk in zip(scene_records, analysis.chunks):
            rec["description"] = chunk.description
            rec["interest_score"] = chunk.interest_score
            rec["tags"] = chunk.tags
            rec["has_speech"] = chunk.audio_type == "speech"
            rec["has_music"] = chunk.audio_type == "music"

        # ---- Step 8: Rank scenes ----
        ranked = rank_scenes(analysis.chunks)
        logger.info("Job %s: ranked %d scenes.", job_id, len(ranked))

        # ---- Step 9: Select best clips ----
        max_clips = config.get("max_clips", 10)
        min_dur = config.get("min_clip_duration", 5.0)
        max_dur = config.get("max_clip_duration", 60.0)
        selections = select_best_clips(ranked, max_clips=max_clips, min_duration=min_dur, max_duration=max_dur)

        await _update_job(job_id, progress=0.85)

        # ---- Step 10: Persist scenes and clips to DB ----
        db = await get_db()
        try:
            for rec in scene_records:
                await db.execute(
                    """INSERT INTO scenes
                       (id, job_id, start_time, end_time, duration, thumbnail_path,
                        description, interest_score, tags_json, has_speech, has_music, is_silent)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        rec["id"],
                        job_id,
                        rec["start_time"],
                        rec["end_time"],
                        rec["duration"],
                        rec.get("thumbnail_path"),
                        rec.get("description", ""),
                        rec.get("interest_score", 0.0),
                        json.dumps(rec.get("tags", [])),
                        int(rec.get("has_speech", False)),
                        int(rec.get("has_music", False)),
                        int(rec.get("is_silent", False)),
                    ),
                )

            for sel in selections:
                clip_id = uuid.uuid4().hex
                duration = round(sel.end_time - sel.start_time, 3)
                await db.execute(
                    """INSERT INTO clips
                       (id, job_id, start_time, end_time, duration,
                        source_scene_ids_json, reason, interest_score)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        clip_id,
                        job_id,
                        sel.start_time,
                        sel.end_time,
                        duration,
                        json.dumps(sel.source_scenes),
                        sel.reason,
                        sel.score,
                    ),
                )

            await db.commit()
        finally:
            await db.close()

        await _update_job(job_id, progress=0.95)

        # ---- Step 11: Mark complete ----
        await _update_job(
            job_id,
            status="complete",
            progress=1.0,
            scenes_found=len(scene_records),
            clips_generated=len(selections),
        )
        logger.info("Job %s complete: %d scenes, %d clips.", job_id, len(scene_records), len(selections))

    except Exception as exc:
        logger.exception("Job %s failed: %s", job_id, exc)
        await _update_job(job_id, status="failed", error=str(exc))


def _scene_overlaps_silence(
    start: float,
    end: float,
    silence_regions: list,
) -> bool:
    """Return True if the majority of the scene overlaps with silence."""
    scene_dur = end - start
    if scene_dur <= 0:
        return False

    total_overlap = 0.0
    for sr in silence_regions:
        ov_start = max(start, sr.start_time)
        ov_end = min(end, sr.end_time)
        if ov_end > ov_start:
            total_overlap += ov_end - ov_start

    return (total_overlap / scene_dur) > 0.5
