"""Video chunk analysis pipeline using Gemma 4."""

from __future__ import annotations

import asyncio
import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from gemma_clipper.ai.gemma_client import GemmaClient, extract_json
from gemma_clipper.ai.prompts import (
    HIGHLIGHT_DETECTION_PROMPT,
    SCENE_ANALYSIS_PROMPT,
    format_prompt,
)
from gemma_clipper.core.video import extract_segment

logger = logging.getLogger(__name__)


@dataclass
class ChunkAnalysis:
    """Result of analyzing a single video chunk."""

    chunk_index: int
    start_time: float
    end_time: float
    description: str = ""
    objects: list[str] = field(default_factory=list)
    mood: str = ""
    energy_level: float = 0.0
    audio_type: str = "silent"
    interest_score: float = 0.0
    tags: list[str] = field(default_factory=list)
    suggested_clips: list[dict] = field(default_factory=list)


@dataclass
class VideoAnalysis:
    """Result of analyzing a full video."""

    chunks: list[ChunkAnalysis] = field(default_factory=list)
    summary: str = ""
    duration: float = 0.0


@dataclass
class AnalysisSettings:
    """Configuration for the analysis pipeline."""

    max_concurrent: int = 3
    include_highlights: bool = True


async def analyze_chunk(
    client: GemmaClient,
    chunk_path: Path,
    chunk_index: int,
    total_chunks: int,
    start_time: float = 0.0,
    end_time: float = 0.0,
    total_duration: float = 0.0,
    include_highlights: bool = True,
) -> ChunkAnalysis:
    """Send one chunk to Gemma for scene analysis and optional highlight detection."""
    video_bytes = chunk_path.read_bytes()

    highlight_prompt = format_prompt(
        HIGHLIGHT_DETECTION_PROMPT,
        total_duration=total_duration,
        chunk_index=chunk_index + 1,
        total_chunks=total_chunks,
        start_time=start_time,
        end_time=end_time,
    )

    # Run scene analysis and highlight detection in parallel.
    if include_highlights:
        scene_data, highlight_data = await asyncio.gather(
            _analyze_with_retry(client, video_bytes, SCENE_ANALYSIS_PROMPT, "scene analysis"),
            _analyze_with_retry(client, video_bytes, highlight_prompt, "highlight detection"),
        )
    else:
        scene_data = await _analyze_with_retry(client, video_bytes, SCENE_ANALYSIS_PROMPT, "scene analysis")
        highlight_data = {}

    result = ChunkAnalysis(
        chunk_index=chunk_index,
        start_time=start_time,
        end_time=end_time,
        description=scene_data.get("description", ""),
        objects=scene_data.get("objects", []),
        mood=scene_data.get("mood", ""),
        energy_level=_clamp(scene_data.get("energy_level", 0.0)),
        audio_type=scene_data.get("audio_type", "silent"),
        interest_score=_clamp(highlight_data.get("interest_score", 0.0)),
        tags=highlight_data.get("tags", []),
        suggested_clips=highlight_data.get("suggested_clip_boundaries", []),
    )

    return result


async def analyze_video(
    client: GemmaClient,
    video_path: Path,
    scenes: list[dict],
    settings: AnalysisSettings | None = None,
    total_duration: float = 0.0,
) -> VideoAnalysis:
    """Orchestrate full video analysis across all scenes.

    *scenes* is a list of dicts with at minimum "id", "start_time", "end_time".
    """
    cfg = settings or AnalysisSettings()
    semaphore = asyncio.Semaphore(cfg.max_concurrent)
    total_chunks = len(scenes)

    async def _process_scene(idx: int, scene: dict) -> ChunkAnalysis:
        async with semaphore:
            start = scene["start_time"]
            end = scene["end_time"]

            with tempfile.TemporaryDirectory() as tmp:
                chunk_path = Path(tmp) / f"chunk_{idx:04d}.mp4"
                await extract_segment(video_path, start, end, chunk_path)

                return await analyze_chunk(
                    client,
                    chunk_path,
                    chunk_index=idx,
                    total_chunks=total_chunks,
                    start_time=start,
                    end_time=end,
                    total_duration=total_duration,
                    include_highlights=cfg.include_highlights,
                )

    tasks = [_process_scene(i, scene) for i, scene in enumerate(scenes)]
    chunks = await asyncio.gather(*tasks, return_exceptions=True)

    results: list[ChunkAnalysis] = []
    for i, chunk in enumerate(chunks):
        if isinstance(chunk, Exception):
            logger.error("Failed to analyze chunk %d: %s", i, chunk)
            results.append(ChunkAnalysis(chunk_index=i, start_time=0.0, end_time=0.0))
        else:
            results.append(chunk)

    return VideoAnalysis(
        chunks=results,
        duration=total_duration,
    )


# -- internal helpers --


async def _analyze_with_retry(
    client: GemmaClient, video_bytes: bytes, prompt: str, label: str,
) -> dict:
    """Call Gemma with video bytes, retry once on JSON parse failure."""
    for attempt in range(2):
        try:
            raw = await client.analyze_video_chunk(video_bytes, prompt)
            data = extract_json(raw)
            if isinstance(data, dict):
                return data
        except Exception:
            logger.warning("Failed to parse %s response (attempt %d)", label, attempt + 1)
    return {}


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    """Clamp a numeric value to [low, high]."""
    try:
        return max(low, min(high, float(value)))
    except (TypeError, ValueError):
        return 0.0
