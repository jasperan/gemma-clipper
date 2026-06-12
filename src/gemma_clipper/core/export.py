"""Clip export with format, aspect ratio, and compilation support."""

from __future__ import annotations

import asyncio
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path

from gemma_clipper.core._subprocess import run_cmd

logger = logging.getLogger(__name__)


@dataclass
class ExportOptions:
    """Options controlling clip export quality and format."""

    format: str = "mp4"  # "mp4", "webm", "gif"
    codec: str = ""  # empty = auto-select based on format
    crf: int = 23
    max_width: int = 1920
    aspect_ratio: str = "original"  # "original", "16:9", "9:16", "1:1"
    add_fade: bool = False
    fade_duration: float = 0.5


@dataclass
class ClipSpec:
    """Describes a clip to extract."""

    start_time: float
    end_time: float
    label: str = ""


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _codec_for_format(fmt: str, explicit: str) -> str:
    """Pick a sane default codec when none is provided."""
    if explicit:
        return explicit
    return {"mp4": "libx264", "webm": "libvpx-vp9", "gif": "gif"}.get(fmt, "libx264")


def _aspect_filter(aspect: str) -> str:
    """Return an ffmpeg video-filter snippet that enforces *aspect* ratio.

    For ``9:16`` (portrait / short-form): center-crop to 9:16.
    For ``1:1``: center-crop to square.
    For ``16:9``: pad to 16:9 with black bars.
    """
    if aspect == "9:16":
        return "crop=ih*9/16:ih,scale=-2:ih"
    if aspect == "1:1":
        return "crop=min(iw\\,ih):min(iw\\,ih)"
    if aspect == "16:9":
        return "pad=iw:iw*9/16:(ow-iw)/2:(oh-ih)/2:black"
    return ""


def _build_vf(opts: ExportOptions, duration: float) -> str:
    """Assemble the ``-vf`` filter chain."""
    filters: list[str] = []

    aspect_f = _aspect_filter(opts.aspect_ratio)
    if aspect_f:
        filters.append(aspect_f)

    filters.append(f"scale='min({opts.max_width},iw)':-2")

    if opts.add_fade and duration > opts.fade_duration * 2:
        filters.append(f"fade=t=in:st=0:d={opts.fade_duration}")
        fade_out_start = duration - opts.fade_duration
        filters.append(f"fade=t=out:st={fade_out_start}:d={opts.fade_duration}")

    return ",".join(filters)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def export_clip(
    source: Path,
    start: float,
    end: float,
    output: Path,
    options: ExportOptions | None = None,
) -> Path:
    """Export a single clip from *source* between *start* and *end*."""
    opts = options or ExportOptions()
    duration = end - start
    codec = _codec_for_format(opts.format, opts.codec)
    vf = _build_vf(opts, duration)

    if opts.format == "gif":
        return await _export_gif(source, start, duration, output, vf)

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start),
        "-i", str(source),
        "-t", str(duration),
        "-vf", vf,
        "-c:v", codec,
        "-crf", str(opts.crf),
        "-preset", "fast",
    ]
    if opts.format == "webm":
        cmd += ["-c:a", "libopus"]
    else:
        cmd += ["-c:a", "aac"]
    cmd.append(str(output))

    await run_cmd(*cmd)
    return output


async def export_batch(
    source: Path,
    clips: list[ClipSpec],
    output_dir: Path,
    options: ExportOptions | None = None,
) -> list[Path]:
    """Export multiple clips concurrently (up to 4 at a time), returning their paths."""
    opts = options or ExportOptions()
    output_dir.mkdir(parents=True, exist_ok=True)
    ext = opts.format if opts.format != "gif" else "gif"

    sem = asyncio.Semaphore(4)

    async def _limited_export(clip_source: Path, start: float, end: float, out: Path, clip_opts: ExportOptions) -> Path:
        async with sem:
            return await export_clip(clip_source, start, end, out, clip_opts)

    results = await asyncio.gather(*[
        _limited_export(
            source,
            clip.start_time,
            clip.end_time,
            output_dir / f"{clip.label or f'clip_{idx:04d}'}.{ext}",
            opts,
        )
        for idx, clip in enumerate(clips)
    ])
    return list(results)


# ---------------------------------------------------------------------------
# GIF export (palette-based for quality)
# ---------------------------------------------------------------------------


async def _export_gif(
    source: Path,
    start: float,
    duration: float,
    output: Path,
    vf: str,
) -> Path:
    """Two-pass GIF export using palettegen + paletteuse for quality."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False, prefix="gclipper_pal_") as f:
        palette = Path(f.name)

    try:
        # Pass 1: generate palette.
        cmd_palette = [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-i", str(source),
            "-t", str(duration),
            "-vf", f"{vf},palettegen=stats_mode=diff",
            str(palette),
        ]
        await run_cmd(*cmd_palette)

        # Pass 2: render GIF using palette.
        cmd_gif = [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-i", str(source),
            "-i", str(palette),
            "-t", str(duration),
            "-lavfi", f"{vf}[v];[v][1:v]paletteuse=dither=bayer:bayer_scale=5",
            str(output),
        ]
        await run_cmd(*cmd_gif)
    finally:
        palette.unlink(missing_ok=True)

    return output
