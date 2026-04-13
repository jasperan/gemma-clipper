"""Scene detection via ffmpeg scene-change filter and keyframe analysis."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from gemma_clipper.core.video import get_keyframes, probe_video

logger = logging.getLogger(__name__)


@dataclass
class SceneBoundary:
    """A detected scene boundary."""

    start_time: float
    end_time: float
    duration: float
    score: float


async def detect_scenes(
    video_path: Path,
    threshold: float = 0.3,
) -> list[SceneBoundary]:
    """Detect scene changes using the ffmpeg ``select`` filter.

    Returns a sorted list of scene boundaries derived from timestamps where
    the scene-change score exceeds *threshold*.
    """
    cmd = [
        "ffmpeg",
        "-i", str(video_path),
        "-vf", f"select='gt(scene,{threshold})',showinfo",
        "-f", "null",
        "-",
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await proc.communicate()

    timestamps: list[tuple[float, float]] = []
    # showinfo lines contain pts_time and the scene score in the select filter metadata.
    pts_pattern = re.compile(r"pts_time:\s*([\d.]+)")
    # The scene score is emitted on lines like: "[Parsed_select...] select:1 ...  scene:0.45"
    score_pattern = re.compile(r"scene:([\d.]+)")

    for line in stderr.decode(errors="replace").splitlines():
        pts_match = pts_pattern.search(line)
        if pts_match:
            pts = float(pts_match.group(1))
            score_match = score_pattern.search(line)
            score = float(score_match.group(1)) if score_match else threshold
            timestamps.append((pts, score))

    return await _boundaries_from_timestamps(timestamps, video_path)


async def detect_scenes_with_keyframes(
    video_path: Path,
    threshold: float = 0.3,
) -> list[SceneBoundary]:
    """Combine scene-filter detection with keyframe analysis.

    Keyframe positions from the codec are merged with scene-change timestamps
    to produce more accurate boundaries (snapped to the nearest keyframe).
    """
    scene_boundaries, keyframe_ts = await asyncio.gather(
        detect_scenes(video_path, threshold),
        get_keyframes(video_path),
    )

    if not keyframe_ts or not scene_boundaries:
        return scene_boundaries

    # Snap each scene boundary start/end to the nearest keyframe.
    snapped: list[SceneBoundary] = []
    for sb in scene_boundaries:
        start = _nearest(keyframe_ts, sb.start_time)
        end = _nearest(keyframe_ts, sb.end_time)
        if end <= start:
            end = sb.end_time
        snapped.append(
            SceneBoundary(
                start_time=start,
                end_time=end,
                duration=round(end - start, 3),
                score=sb.score,
            )
        )
    return snapped


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _boundaries_from_timestamps(
    timestamps: list[tuple[float, float]],
    video_path: Path,
) -> list[SceneBoundary]:
    """Convert raw (pts, score) pairs into contiguous SceneBoundary objects."""
    if not timestamps:
        return []

    timestamps.sort(key=lambda t: t[0])
    meta = await probe_video(video_path)
    total_duration = meta.duration

    boundaries: list[SceneBoundary] = []
    for i, (pts, score) in enumerate(timestamps):
        start = 0.0 if i == 0 else timestamps[i - 1][0]
        end = pts
        if end <= start:
            continue
        boundaries.append(
            SceneBoundary(
                start_time=round(start, 3),
                end_time=round(end, 3),
                duration=round(end - start, 3),
                score=score,
            )
        )

    # Add the trailing segment (last scene-change to end of video).
    if timestamps:
        last_pts = timestamps[-1][0]
        if last_pts < total_duration:
            boundaries.append(
                SceneBoundary(
                    start_time=round(last_pts, 3),
                    end_time=round(total_duration, 3),
                    duration=round(total_duration - last_pts, 3),
                    score=0.0,
                )
            )

    return boundaries


def _nearest(sorted_values: list[float], target: float) -> float:
    """Return the value in *sorted_values* closest to *target* (linear scan)."""
    best = sorted_values[0]
    best_dist = abs(best - target)
    for v in sorted_values[1:]:
        d = abs(v - target)
        if d < best_dist:
            best, best_dist = v, d
        elif d > best_dist:
            break  # sorted, so distance only grows from here
    return best
