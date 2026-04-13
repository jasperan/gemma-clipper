"""vLLM client for Gemma 4 multimodal inference."""

from __future__ import annotations

import base64
import json
import logging
import re

import httpx

from gemma_clipper.config import settings

logger = logging.getLogger(__name__)

_VIDEO_TIMEOUT = 120.0
_TEXT_TIMEOUT = 30.0
_MAX_RETRIES = 2


class GemmaClient:
    """Async client wrapping vLLM's OpenAI-compatible chat endpoint."""

    def __init__(
        self,
        base_url: str = "",
        model: str = "",
    ) -> None:
        self.base_url = (base_url or settings.vllm_base_url).rstrip("/")
        self.model = model or settings.gemma_model
        self._http = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(_VIDEO_TIMEOUT, connect=10.0),
        )

    async def close(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> GemmaClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    # -- public API --

    async def analyze_video_chunk(self, video_bytes: bytes, prompt: str) -> str:
        """Send a base64-encoded MP4 chunk as a multimodal message and return the response text."""
        b64 = base64.b64encode(video_bytes).decode()
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "video_url",
                        "video_url": {"url": f"data:video/mp4;base64,{b64}"},
                    },
                    {"type": "text", "text": prompt},
                ],
            },
        ]
        return await self._chat_completion(messages, timeout=_VIDEO_TIMEOUT)

    async def analyze_image(self, image_bytes: bytes, prompt: str) -> str:
        """Send a base64-encoded image and return the response text."""
        b64 = base64.b64encode(image_bytes).decode()
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                    },
                    {"type": "text", "text": prompt},
                ],
            },
        ]
        return await self._chat_completion(messages, timeout=_VIDEO_TIMEOUT)

    async def chat(self, messages: list[dict]) -> str:
        """Plain text chat completion."""
        return await self._chat_completion(messages, timeout=_TEXT_TIMEOUT)

    async def health_check(self) -> bool:
        """Return True if vLLM is responding."""
        try:
            resp = await self._http.get("/models", timeout=5.0)
            return resp.status_code == 200
        except (httpx.HTTPError, OSError):
            return False

    # -- internals --

    async def _chat_completion(
        self,
        messages: list[dict],
        timeout: float = _TEXT_TIMEOUT,
    ) -> str:
        """Send a chat completion request with retry on JSON parse failures."""
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 4096,
        }

        last_error: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                resp = await self._http.post(
                    "/chat/completions",
                    json=payload,
                    timeout=timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return content.strip()
            except (httpx.HTTPStatusError, KeyError, json.JSONDecodeError) as exc:
                last_error = exc
                logger.warning(
                    "vLLM request failed (attempt %d/%d): %s",
                    attempt + 1,
                    _MAX_RETRIES + 1,
                    exc,
                )
                if attempt < _MAX_RETRIES:
                    continue

        raise RuntimeError(f"vLLM request failed after {_MAX_RETRIES + 1} attempts: {last_error}")


def extract_json(text: str) -> dict | list:
    """Try to parse JSON from a response that may contain markdown fences or extra text."""
    # Try direct parse first.
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strip markdown code fences.
    fenced = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Find the first { ... } or [ ... ] block.
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start = text.find(start_char)
        if start == -1:
            continue
        end = text.rfind(end_char)
        if end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue

    raise ValueError(f"Could not extract JSON from response: {text[:200]}")
