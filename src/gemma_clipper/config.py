"""Configuration for gemma-clipper."""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings, configurable via environment variables."""

    # vLLM / Gemma
    vllm_base_url: str = "http://localhost:8000/v1"
    gemma_model: str = "google/gemma-4-E4B-it"
    max_model_len: int = 8192

    # Video processing
    max_upload_size_mb: int = 2048
    chunk_duration_seconds: int = 30
    max_chunks: int = 20
    scene_threshold: float = 0.3
    silence_threshold_db: float = -30.0
    silence_min_duration: float = 0.5

    # Export defaults
    default_output_format: str = "mp4"
    default_video_codec: str = "libx264"
    default_audio_codec: str = "aac"
    default_crf: int = 23
    max_resolution_width: int = 1920
    short_form_width: int = 1080
    short_form_height: int = 1920

    # Whisper (captions)
    whisper_model: str = "base"
    whisper_device: str = "auto"

    # Storage
    upload_dir: Path = Path("uploads")
    output_dir: Path = Path("output")
    thumbnails_dir: Path = Path("thumbnails")
    db_path: Path = Path("jobs.db")

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    model_config = {"env_prefix": "GCLIPPER_"}

    def ensure_dirs(self) -> None:
        """Create required directories if they don't exist."""
        for d in [self.upload_dir, self.output_dir, self.thumbnails_dir]:
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()
