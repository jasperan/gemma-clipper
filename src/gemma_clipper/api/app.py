"""FastAPI application with lifespan, CORS, static files, and health check."""

from __future__ import annotations

import asyncio
import functools
import logging
import shutil
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from gemma_clipper import __version__
from gemma_clipper.ai.gemma_client import GemmaClient
from gemma_clipper.api.models import HealthResponse
from gemma_clipper.api.routes.clips import router as clips_router
from gemma_clipper.api.routes.videos import router as videos_router
from gemma_clipper.config import settings
from gemma_clipper.db import init_db
from gemma_clipper.workers.pipeline import start_worker

logger = logging.getLogger(__name__)


@functools.cache
def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown lifecycle for the application."""
    # Ensure storage directories exist.
    settings.ensure_dirs()

    # Initialize database schema.
    await init_db()

    # Start background worker that processes pending jobs.
    worker_task = asyncio.create_task(start_worker())
    logger.info("Background worker started.")

    yield

    # Shutdown: cancel worker and give it a moment to clean up.
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass
    logger.info("Background worker stopped.")


app = FastAPI(
    title="gemma-clipper",
    version=__version__,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(videos_router)
app.include_router(clips_router)

# Static file serving for thumbnails and exported clips.
# Directories are created by lifespan, so mount after startup is safe
# because FastAPI mounts are lazy-checked.
app.mount(
    "/thumbnails",
    StaticFiles(directory=str(settings.thumbnails_dir), check_dir=False),
    name="thumbnails",
)
app.mount(
    "/output",
    StaticFiles(directory=str(settings.output_dir), check_dir=False),
    name="output",
)


@app.get("/", response_model=HealthResponse, tags=["health"])
async def health() -> HealthResponse:
    """Root health endpoint: checks vLLM connectivity and ffmpeg availability."""
    # Check vLLM
    client = GemmaClient()
    try:
        vllm_ok = await client.health_check()
    finally:
        await client.close()

    # Check ffmpeg
    ffmpeg_ok = _ffmpeg_available()

    return HealthResponse(
        status="ok" if (vllm_ok and ffmpeg_ok) else "degraded",
        version=__version__,
        vllm_connected=vllm_ok,
        ffmpeg_available=ffmpeg_ok,
    )
