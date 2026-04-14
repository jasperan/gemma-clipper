# CLAUDE.md

AI-powered video clipping tool using Gemma 4 multimodal (4B) served locally via vLLM. No cloud APIs required.

## Tech Stack

- **Python 3.11+** — FastAPI backend, Typer CLI, aiosqlite, pydantic-settings
- **vLLM** — serves `google/gemma-4-E4B-it` on OpenAI-compatible `/v1` endpoint
- **ffmpeg** — scene detection, silence removal, export (system install required)
- **faster-whisper** — auto-captions/transcription
- **yt-dlp** — YouTube download
- **Frontend** — React 18 + Vite + TypeScript + Tailwind CSS
- **Build** — hatchling, ruff, pytest-asyncio

## Environment Setup

```bash
conda create -n gemma-clipper python=3.12
conda activate gemma-clipper
pip install -e ".[dev]"
```

System dependency: `ffmpeg` must be installed and on PATH.

HuggingFace token needed for model download: `export HF_TOKEN=your_token_here`

## Build / Run / Test

```bash
# Run tests
pytest tests/ -v

# Lint
ruff check src/

# Start vLLM (separate terminal, ~6GB VRAM)
vllm serve google/gemma-4-E4B-it \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.90 \
  --limit-mm-per-prompt '{"image":2,"video":1,"audio":1}' \
  --trust-remote-code

# Start API server (port 8080)
gemma-clipper serve

# Full Docker stack (vLLM + API + frontend)
docker compose up
```

Frontend dev server (port 5173):
```bash
cd frontend && npm install && npm run dev
```

## CLI Commands

```bash
gemma-clipper analyze "https://youtube.com/..." --max-clips 5   # full pipeline
gemma-clipper scenes my_video.mp4                                # scene detect only (no GPU)
gemma-clipper export my_video.mp4 --aspect-ratio 9:16 --captions --caption-style bold
gemma-clipper download "https://youtube.com/..."
gemma-clipper captions my_video.mp4
gemma-clipper clips <job-id>
gemma-clipper serve
```

## Architecture

```
src/gemma_clipper/
  config.py       # pydantic-settings, all env vars via GCLIPPER_ prefix
  db.py           # aiosqlite — jobs, scenes, clips tables
  cli.py          # Typer app, 7 commands
  core/
    scenes.py     # ffmpeg scene detection + keyframe analysis
    # also: silence detection, captions, export wrappers
  ai/
    gemma_client.py  # httpx client → vLLM /v1/chat/completions
    analyzer.py      # segments video, calls Gemma per chunk
    ranker.py        # weighted scoring (interest 0.4, energy 0.3, speech 0.15, variety 0.15)
    prompts.py       # prompt templates
  api/
    app.py           # FastAPI app + lifespan
    models.py        # Pydantic request/response models
    routes/
      videos.py      # upload, YouTube ingest, list, delete
      clips.py       # export, ranked scenes, custom clip, download
  workers/
    pipeline.py      # async job processor

frontend/            # React 18 + Vite + TypeScript + Tailwind
```

## Configuration (env vars)

All settings use `GCLIPPER_` prefix. Key ones:

```bash
GCLIPPER_VLLM_BASE_URL=http://localhost:8000/v1   # vLLM endpoint
GCLIPPER_GEMMA_MODEL=google/gemma-4-E4B-it
GCLIPPER_CHUNK_DURATION_SECONDS=30                 # seconds per analyzed segment
GCLIPPER_SCENE_THRESHOLD=0.3                       # ffmpeg scene sensitivity (0-1)
GCLIPPER_WHISPER_MODEL=base                        # tiny/base/small/medium/large
GCLIPPER_DEFAULT_OUTPUT_FORMAT=mp4
GCLIPPER_DEFAULT_CRF=23                            # video quality (lower = better)
GCLIPPER_API_PORT=8080
```

Storage defaults: `uploads/`, `output/`, `thumbnails/`, `jobs.db` — all relative to CWD. Override with `GCLIPPER_UPLOAD_DIR` etc.

## Gotchas

- vLLM must be running before `analyze` or the API server starts processing jobs. `scenes` command works without GPU.
- `--limit-mm-per-prompt '{"image":2,"video":1,"audio":1}'` is required for Gemma 4 multimodal — omitting it causes vLLM to reject requests.
- `asyncio_mode = "auto"` is set in pytest config; all test coroutines run automatically.
- Only one test file: `tests/test_e2e_real.py` — it hits a real vLLM instance, so tests fail without the model running.
- Docker Compose mounts `./uploads`, `./output`, `./thumbnails` from CWD — run `docker compose` from the project root.
- CORS is preconfigured for `localhost:5173` and `localhost:3000`; add origins via `GCLIPPER_CORS_ORIGINS`.
