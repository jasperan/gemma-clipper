"""FFmpeg/FFprobe wrapper for video probing and segment extraction."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from gemma_clipper.core._subprocess import run_cmd

logger = logging.getLogger(__name__)


@dataclass
class VideoMetadata:
    """Metadata extracted from a video file via ffprobe."""

    path: Path
    duration: float
    width: int
    height: int
    fps: float
    codec: str
    audio_codec: str | None
    audio_tracks: int
    filesize_mb: float


async def probe_video(path: Path) -> VideoMetadata:
    """Run ffprobe on *path* and return structured metadata."""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    stdout, _ = await run_cmd(*cmd)
    info = json.loads(stdout)

    video_stream: dict | None = None
    audio_tracks = 0
    audio_codec: str | None = None

    for stream in info.get("streams", []):
        if stream.get("codec_type") == "video" and video_stream is None:
            video_stream = stream
        elif stream.get("codec_type") == "audio":
            audio_tracks += 1
            if audio_codec is None:
                audio_codec = stream.get("codec_name")

    if video_stream is None:
        raise ValueError(f"No video stream found in {path}")

    # Parse frame rate from "30/1" or "30000/1001" style strings.
    fps_str = video_stream.get("r_frame_rate", "0/1")
    num, den = fps_str.split("/")
    fps = float(num) / float(den) if float(den) else 0.0

    fmt = info.get("format", {})
    duration = float(fmt.get("duration", video_stream.get("duration", 0)))
    filesize_bytes = int(fmt.get("size", 0))

    return VideoMetadata(
        path=path,
        duration=duration,
        width=int(video_stream.get("width", 0)),
        height=int(video_stream.get("height", 0)),
        fps=fps,
        codec=video_stream.get("codec_name", "unknown"),
        audio_codec=audio_codec,
        audio_tracks=audio_tracks,
        filesize_mb=round(filesize_bytes / (1024 * 1024), 2),
    )


async def extract_segment(
    source: Path,
    start: float,
    end: float,
    output: Path,
    max_width: int = 480,
    crf: int = 30,
) -> Path:
    """Cut a segment from *source* and scale it down for analysis."""
    duration = end - start
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start),
        "-i", str(source),
        "-t", str(duration),
        "-vf", f"scale='min({max_width},iw)':-2",
        "-c:v", "libx264",
        "-crf", str(crf),
        "-preset", "fast",
        "-c:a", "aac",
        "-ac", "1",
        str(output),
    ]
    await run_cmd(*cmd)
    return output


async def extract_frame(source: Path, timestamp: float, output: Path) -> Path:
    """Extract a single frame as JPEG at *timestamp*."""
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(timestamp),
        "-i", str(source),
        "-frames:v", "1",
        "-q:v", "2",
        str(output),
    ]
    await run_cmd(*cmd)
    return output


async def get_keyframes(source: Path) -> list[float]:
    """Return timestamps (seconds) of all keyframes in the video."""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-select_streams", "v:0",
        "-skip_frame", "nokey",
        "-show_entries", "frame=pts_time",
        "-of", "csv=p=0",
        str(source),
    ]
    stdout, _ = await run_cmd(*cmd)
    timestamps: list[float] = []
    for line in stdout.decode().strip().splitlines():
        line = line.strip()
        if line:
            timestamps.append(float(line))
    return sorted(timestamps)
