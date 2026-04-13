FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir .

RUN mkdir -p uploads output thumbnails

EXPOSE 8080
CMD ["uvicorn", "gemma_clipper.api.app:app", "--host", "0.0.0.0", "--port", "8080"]
