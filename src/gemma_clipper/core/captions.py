"""Whisper transcription and caption generation/burning."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class TranscriptSegment:
    """A single transcribed segment."""

    start: float
    end: float
    text: str
    confidence: float


@dataclass
class Transcript:
    """Full transcription result."""

    segments: list[TranscriptSegment] = field(default_factory=list)
    language: str = ""
    full_text: str = ""


# ---------------------------------------------------------------------------
# Caption style presets (ffmpeg subtitles filter force_style)
# ---------------------------------------------------------------------------

_STYLES: dict[str, str] = {
    "default": (
        "FontName=Arial,FontSize=22,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,BorderStyle=1,Outline=2"
    ),
    "bold": (
        "FontName=Arial,FontSize=32,PrimaryColour=&H0000FFFF,"
        "OutlineColour=&H00000000,BorderStyle=1,Outline=3,Bold=1"
    ),
    "minimal": (
        "FontName=Arial,FontSize=16,PrimaryColour=&H00AAAAAA,"
        "OutlineColour=&H00000000,BorderStyle=1,Outline=1"
    ),
}


async def transcribe(
    video_path: Path,
    model_name: str = "base",
    device: str = "auto",
) -> Transcript:
    """Transcribe audio using faster-whisper."""
    from faster_whisper import WhisperModel  # lazy import to avoid startup cost

    compute_type = "float16" if device in ("cuda", "auto") else "int8"
    actual_device = "cuda" if device == "auto" else device

    try:
        model = WhisperModel(model_name, device=actual_device, compute_type=compute_type)
    except Exception:
        # Fall back to CPU if CUDA isn't available.
        logger.info("CUDA unavailable, falling back to CPU for Whisper.")
        model = WhisperModel(model_name, device="cpu", compute_type="int8")

    segments_iter, info = model.transcribe(str(video_path), beam_size=5)

    segments: list[TranscriptSegment] = []
    texts: list[str] = []
    for seg in segments_iter:
        segments.append(
            TranscriptSegment(
                start=round(seg.start, 3),
                end=round(seg.end, 3),
                text=seg.text.strip(),
                confidence=round(seg.avg_log_prob, 4),
            )
        )
        texts.append(seg.text.strip())

    return Transcript(
        segments=segments,
        language=info.language,
        full_text=" ".join(texts),
    )


# ---------------------------------------------------------------------------
# SRT / VTT generation
# ---------------------------------------------------------------------------


def _format_ts_srt(seconds: float) -> str:
    """Format *seconds* as ``HH:MM:SS,mmm`` for SRT."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _format_ts_vtt(seconds: float) -> str:
    """Format *seconds* as ``HH:MM:SS.mmm`` for VTT."""
    return _format_ts_srt(seconds).replace(",", ".")


async def generate_srt(transcript: Transcript, output: Path) -> Path:
    """Write an SRT subtitle file from *transcript*."""
    lines: list[str] = []
    for idx, seg in enumerate(transcript.segments, start=1):
        lines.append(str(idx))
        lines.append(f"{_format_ts_srt(seg.start)} --> {_format_ts_srt(seg.end)}")
        lines.append(seg.text)
        lines.append("")
    output.write_text("\n".join(lines), encoding="utf-8")
    return output


async def generate_vtt(transcript: Transcript, output: Path) -> Path:
    """Write a WebVTT subtitle file from *transcript*."""
    lines: list[str] = ["WEBVTT", ""]
    for idx, seg in enumerate(transcript.segments, start=1):
        lines.append(str(idx))
        lines.append(f"{_format_ts_vtt(seg.start)} --> {_format_ts_vtt(seg.end)}")
        lines.append(seg.text)
        lines.append("")
    output.write_text("\n".join(lines), encoding="utf-8")
    return output


# ---------------------------------------------------------------------------
# Burn captions into video
# ---------------------------------------------------------------------------


async def burn_captions(
    video_path: Path,
    srt_path: Path,
    output: Path,
    style: str = "default",
) -> Path:
    """Burn SRT captions into the video using ffmpeg subtitles filter."""
    force_style = _STYLES.get(style, _STYLES["default"])
    # Escape colons and backslashes in the path for the subtitles filter.
    escaped_srt = str(srt_path).replace("\\", "\\\\").replace(":", "\\:")

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vf", f"subtitles={escaped_srt}:force_style='{force_style}'",
        "-c:v", "libx264",
        "-preset", "fast",
        "-c:a", "copy",
        str(output),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg caption burn failed ({proc.returncode}):\n"
            f"{stderr.decode(errors='replace')}"
        )
    return output
