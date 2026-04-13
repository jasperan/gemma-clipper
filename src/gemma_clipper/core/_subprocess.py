"""Shared async subprocess runner for ffmpeg/ffprobe commands."""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


async def run_cmd(*cmd: str) -> tuple[bytes, bytes]:
    """Run a subprocess, return (stdout, stderr). Raises RuntimeError on failure."""
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(
            f"{cmd[0]} failed (exit {proc.returncode}): {stderr.decode(errors='replace')[:500]}"
        )
    return stdout, stderr
