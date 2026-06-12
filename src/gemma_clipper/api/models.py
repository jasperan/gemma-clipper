"""Pydantic models for API requests/responses and database schemas."""

from __future__ import annotations

import enum
from datetime import datetime

from pydantic import BaseModel, Field


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    ANALYZING = "analyzing"
    COMPLETE = "complete"
    FAILED = "failed"


class ExportFormat(str, enum.Enum):
    MP4 = "mp4"
    WEBM = "webm"
    GIF = "gif"


class AspectRatio(str, enum.Enum):
    ORIGINAL = "original"
    LANDSCAPE = "16:9"
    PORTRAIT = "9:16"
    SQUARE = "1:1"


class SourceType(str, enum.Enum):
    UPLOAD = "upload"
    YOUTUBE = "youtube"


# --- Requests ---


class YouTubeRequest(BaseModel):
    url: str
    auto_clip: bool = True
    max_clips: int = Field(default=10, ge=1, le=50)
    min_clip_duration: float = Field(default=5.0, ge=1.0)
    max_clip_duration: float = Field(default=60.0, le=300.0)


class ExportRequest(BaseModel):
    clip_ids: list[str] = Field(default_factory=list, description="Empty = export all clips")
    format: ExportFormat = ExportFormat.MP4
    aspect_ratio: AspectRatio = AspectRatio.ORIGINAL
    add_captions: bool = False
    caption_style: str = "default"
    crf: int = Field(default=23, ge=0, le=51)
    max_width: int | None = None


# --- Responses ---


class Scene(BaseModel):
    """A detected scene boundary with AI analysis."""
    id: str
    start_time: float
    end_time: float
    duration: float
    thumbnail_path: str | None = None
    description: str = ""
    interest_score: float = Field(default=0.0, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)
    has_speech: bool = False
    has_music: bool = False
    is_silent: bool = False


class Clip(BaseModel):
    """A selected clip (auto or manual) ready for export."""
    id: str
    job_id: str
    start_time: float
    end_time: float
    duration: float
    source_scene_ids: list[str] = Field(default_factory=list)
    reason: str = ""
    interest_score: float = 0.0
    exported_path: str | None = None
    thumbnail_path: str | None = None


class JobResponse(BaseModel):
    id: str
    status: JobStatus
    source_type: SourceType
    source_name: str
    video_duration: float | None = None
    scenes_found: int = 0
    clips_generated: int = 0
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class JobDetailResponse(JobResponse):
    scenes: list[Scene] = Field(default_factory=list)
    clips: list[Clip] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    vllm_connected: bool
    ffmpeg_available: bool
