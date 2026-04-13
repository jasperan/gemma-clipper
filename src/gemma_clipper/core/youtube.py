"""yt-dlp integration for downloading and inspecting YouTube videos."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import yt_dlp

logger = logging.getLogger(__name__)


@dataclass
class Chapter:
    """A single chapter inside a YouTube video."""

    title: str
    start_time: float
    end_time: float


@dataclass
class YouTubeInfo:
    """Metadata about a YouTube video (no download)."""

    title: str
    duration: float
    description: str
    thumbnail_url: str | None
    channel: str
    upload_date: str
    chapters: list[Chapter] = field(default_factory=list)


@dataclass
class DownloadResult:
    """Result of a successful video download."""

    path: Path
    title: str
    duration: float
    description: str
    thumbnail_url: str | None


def _parse_chapters(info: dict) -> list[Chapter]:
    """Extract chapter list from yt-dlp info dict."""
    chapters: list[Chapter] = []
    for ch in info.get("chapters") or []:
        chapters.append(
            Chapter(
                title=ch.get("title", ""),
                start_time=float(ch.get("start_time", 0)),
                end_time=float(ch.get("end_time", 0)),
            )
        )
    return chapters


def _cookie_opts() -> dict:
    """Build cookie options if a cookies file or browser is available."""
    cookie_file = Path("cookies.txt")
    if cookie_file.exists():
        return {"cookiefile": str(cookie_file)}
    # Try common browser cookie sources (works on desktop, not headless servers)
    for browser in ("chrome", "firefox", "brave", "edge"):
        try:
            yt_dlp.cookies.extract_cookies_from_browser(browser)
            return {"cookiesfrombrowser": (browser,)}
        except Exception:
            continue
    return {}


async def get_video_info(url: str) -> YouTubeInfo:
    """Fetch video metadata without downloading."""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        **_cookie_opts(),
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info: dict = ydl.extract_info(url, download=False)  # type: ignore[assignment]

    return YouTubeInfo(
        title=info.get("title", ""),
        duration=float(info.get("duration", 0)),
        description=info.get("description", ""),
        thumbnail_url=info.get("thumbnail"),
        channel=info.get("channel", info.get("uploader", "")),
        upload_date=info.get("upload_date", ""),
        chapters=_parse_chapters(info),
    )


async def download_video(
    url: str,
    output_dir: Path,
    max_resolution: int = 1080,
) -> DownloadResult:
    """Download a video via yt-dlp and return the result."""
    output_dir.mkdir(parents=True, exist_ok=True)
    template = str(output_dir / "%(title)s.%(ext)s")

    opts = {
        "format": f"bestvideo[height<={max_resolution}]+bestaudio/best[height<={max_resolution}]",
        "merge_output_format": "mp4",
        "outtmpl": template,
        "quiet": True,
        "no_warnings": True,
        **_cookie_opts(),
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info: dict = ydl.extract_info(url, download=True)  # type: ignore[assignment]

    filename = ydl.prepare_filename(info)
    # yt-dlp may change the extension after merge.
    downloaded = Path(filename).with_suffix(".mp4")
    if not downloaded.exists():
        downloaded = Path(filename)

    return DownloadResult(
        path=downloaded,
        title=info.get("title", ""),
        duration=float(info.get("duration", 0)),
        description=info.get("description", ""),
        thumbnail_url=info.get("thumbnail"),
    )
