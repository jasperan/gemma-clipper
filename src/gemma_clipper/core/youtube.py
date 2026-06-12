"""yt-dlp integration for downloading and inspecting YouTube videos."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import yt_dlp

logger = logging.getLogger(__name__)


@dataclass
class DownloadResult:
    """Result of a successful video download."""

    path: Path
    title: str
    duration: float
    description: str
    thumbnail_url: str | None


_cached_cookie_opts: dict | None = None


def _cookie_opts() -> dict:
    """Build cookie options if a cookies file or browser is available."""
    global _cached_cookie_opts
    if _cached_cookie_opts is not None:
        return _cached_cookie_opts

    cookie_file = Path("cookies.txt")
    if cookie_file.exists():
        _cached_cookie_opts = {"cookiefile": str(cookie_file)}
        return _cached_cookie_opts
    # Try common browser cookie sources (works on desktop, not headless servers)
    for browser in ("chrome", "firefox", "brave", "edge"):
        try:
            yt_dlp.cookies.extract_cookies_from_browser(browser)
            _cached_cookie_opts = {"cookiesfrombrowser": (browser,)}
            return _cached_cookie_opts
        except Exception:
            continue
    _cached_cookie_opts = {}
    return _cached_cookie_opts


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
