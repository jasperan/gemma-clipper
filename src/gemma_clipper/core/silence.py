"""Silence and speech-region detection via ffmpeg silencedetect filter."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from gemma_clipper.core._subprocess import run_cmd
from gemma_clipper.core.video import probe_video

logger = logging.getLogger(__name__)


@dataclass
class SilenceRegion:
    """A contiguous region of silence."""

    start_time: float
    end_time: float
    duration: float


@dataclass
class SpeechRegion:
    """A contiguous region containing speech (non-silent audio)."""

    start_time: float
    end_time: float
    duration: float


async def detect_silence(
    video_path: Path,
    threshold_db: float = -30.0,
    min_duration: float = 0.5,
) -> list[SilenceRegion]:
    """Detect silent regions using the ffmpeg ``silencedetect`` filter."""
    cmd = [
        "ffmpeg",
        "-i", str(video_path),
        "-af", f"silencedetect=noise={threshold_db}dB:d={min_duration}",
        "-f", "null",
        "-",
    ]
    # silencedetect always exits 0; stderr contains the detection output.
    _, stderr = await run_cmd(*cmd)

    return _parse_silence_output(stderr.decode(errors="replace"))


async def detect_speech_regions(
    video_path: Path,
    threshold_db: float = -30.0,
    min_duration: float = 0.5,
) -> list[SpeechRegion]:
    """Return regions that are *not* silent (the inverse of detect_silence)."""
    silence = await detect_silence(video_path, threshold_db, min_duration)
    meta = await probe_video(video_path)
    total = meta.duration

    regions: list[SpeechRegion] = []
    cursor = 0.0

    for sr in silence:
        if sr.start_time > cursor:
            regions.append(
                SpeechRegion(
                    start_time=round(cursor, 3),
                    end_time=round(sr.start_time, 3),
                    duration=round(sr.start_time - cursor, 3),
                )
            )
        cursor = sr.end_time

    if cursor < total:
        regions.append(
            SpeechRegion(
                start_time=round(cursor, 3),
                end_time=round(total, 3),
                duration=round(total - cursor, 3),
            )
        )

    return regions


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

_START_RE = re.compile(r"silence_start:\s*([\d.]+)")
_END_RE = re.compile(r"silence_end:\s*([\d.]+)\s*\|\s*silence_duration:\s*([\d.]+)")


def _parse_silence_output(text: str) -> list[SilenceRegion]:
    """Parse ffmpeg silencedetect output into SilenceRegion objects."""
    regions: list[SilenceRegion] = []
    pending_start: float | None = None

    for line in text.splitlines():
        start_match = _START_RE.search(line)
        if start_match:
            pending_start = float(start_match.group(1))
            continue

        end_match = _END_RE.search(line)
        if end_match and pending_start is not None:
            end_time = float(end_match.group(1))
            duration = float(end_match.group(2))
            regions.append(
                SilenceRegion(
                    start_time=round(pending_start, 3),
                    end_time=round(end_time, 3),
                    duration=round(duration, 3),
                )
            )
            pending_start = None

    return regions
