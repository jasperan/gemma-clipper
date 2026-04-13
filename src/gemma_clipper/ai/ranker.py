"""Scene scoring and ranking for clip selection."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from gemma_clipper.ai.analyzer import ChunkAnalysis

logger = logging.getLogger(__name__)

# Scoring weights
_W_ENERGY = 0.3
_W_INTEREST = 0.4
_W_SPEECH = 0.15
_W_VARIETY = 0.15


@dataclass
class RankedScene:
    """A scene with its final composite score and ranking breakdown."""

    scene_id: str
    start_time: float
    end_time: float
    final_score: float
    rank: int = 0
    breakdown: dict[str, float] = field(default_factory=dict)
    description: str = ""


@dataclass
class ClipSelection:
    """A selected clip ready for export."""

    start_time: float
    end_time: float
    score: float
    reason: str
    source_scenes: list[str] = field(default_factory=list)


def rank_scenes(analyses: list[ChunkAnalysis]) -> list[RankedScene]:
    """Combine multiple signals into a final ranking sorted by score descending."""
    ranked: list[RankedScene] = []

    for analysis in analyses:
        energy_score = analysis.energy_level
        interest_score = analysis.interest_score
        speech_score = 1.0 if analysis.audio_type == "speech" else 0.0
        variety_score = _visual_variety_score(analysis)

        final = (
            _W_ENERGY * energy_score
            + _W_INTEREST * interest_score
            + _W_SPEECH * speech_score
            + _W_VARIETY * variety_score
        )

        ranked.append(
            RankedScene(
                scene_id=str(analysis.chunk_index),
                start_time=analysis.start_time,
                end_time=analysis.end_time,
                final_score=round(final, 4),
                breakdown={
                    "energy": round(energy_score, 4),
                    "interest": round(interest_score, 4),
                    "speech": round(speech_score, 4),
                    "variety": round(variety_score, 4),
                },
                description=analysis.description,
            )
        )

    ranked.sort(key=lambda s: s.final_score, reverse=True)
    for i, scene in enumerate(ranked):
        scene.rank = i + 1

    return ranked


def select_best_clips(
    ranked: list[RankedScene],
    max_clips: int = 10,
    min_duration: float = 5.0,
    max_duration: float = 60.0,
) -> list[ClipSelection]:
    """Greedy clip selection avoiding overlap and respecting duration constraints."""
    selected: list[ClipSelection] = []
    used_intervals: list[tuple[float, float]] = []

    for scene in ranked:
        if len(selected) >= max_clips:
            break

        duration = scene.end_time - scene.start_time
        if duration < min_duration or duration > max_duration:
            continue

        if _overlaps_any(scene.start_time, scene.end_time, used_intervals):
            # Check if we should merge with an existing clip
            merged = _try_merge(scene, selected, max_duration)
            if merged:
                continue
            # Skip this scene, too much overlap with already-selected clips
            continue

        selected.append(
            ClipSelection(
                start_time=scene.start_time,
                end_time=scene.end_time,
                score=scene.final_score,
                reason=f"Rank #{scene.rank}: {scene.description[:80]}" if scene.description else f"Rank #{scene.rank}",
                source_scenes=[scene.scene_id],
            )
        )
        used_intervals.append((scene.start_time, scene.end_time))

    return selected


def _visual_variety_score(analysis: ChunkAnalysis) -> float:
    """Score visual variety based on object count and tag diversity."""
    obj_count = len(analysis.objects)
    tag_count = len(analysis.tags)
    # Normalize: 5+ objects or tags gives max score
    obj_score = min(obj_count / 5.0, 1.0)
    tag_score = min(tag_count / 5.0, 1.0)
    return (obj_score + tag_score) / 2.0


def _overlaps_any(
    start: float,
    end: float,
    intervals: list[tuple[float, float]],
    threshold: float = 0.5,
) -> bool:
    """Return True if (start, end) overlaps with any existing interval by more than threshold fraction."""
    duration = end - start
    if duration <= 0:
        return False

    for iv_start, iv_end in intervals:
        overlap_start = max(start, iv_start)
        overlap_end = min(end, iv_end)
        overlap = max(0.0, overlap_end - overlap_start)
        if overlap / duration > threshold:
            return True

    return False


def _try_merge(
    scene: RankedScene,
    selected: list[ClipSelection],
    max_duration: float,
) -> bool:
    """Try to merge a scene into an overlapping clip. Returns True if merged."""
    for clip in selected:
        overlap_start = max(scene.start_time, clip.start_time)
        overlap_end = min(scene.end_time, clip.end_time)
        overlap = max(0.0, overlap_end - overlap_start)
        scene_dur = scene.end_time - scene.start_time

        if scene_dur > 0 and overlap / scene_dur > 0.5:
            # Expand the clip to cover both
            new_start = min(clip.start_time, scene.start_time)
            new_end = max(clip.end_time, scene.end_time)
            if new_end - new_start <= max_duration:
                clip.start_time = new_start
                clip.end_time = new_end
                clip.score = max(clip.score, scene.final_score)
                clip.source_scenes.append(scene.scene_id)
                return True

    return False
