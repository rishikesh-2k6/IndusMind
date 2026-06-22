"""Gemini text-generation client.

When no API key is configured the client runs in a deterministic "mock" mode so
the rest of the system (RAG, summarization) remains exercisable in local dev and
tests without network access.
"""
from __future__ import annotations

import asyncio
import json
import re

from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.exceptions import LLMError
from app.core.logging import get_logger

logger = get_logger(__name__)

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _parse_json(text: str) -> dict | list:
    """Parse a JSON string, tolerating code fences. Returns {} on failure."""
    if not text:
        return {}
    cleaned = _FENCE.sub("", text).strip()
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        # Best-effort: grab the outermost JSON object/array.
        match = re.search(r"[\[{].*[\]}]", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except (json.JSONDecodeError, ValueError):
                return {}
        return {}


class GeminiClient:
    def __init__(self) -> None:
        self._enabled = settings.has_gemini
        self._model = None
        if self._enabled:
            import google.generativeai as genai

            genai.configure(api_key=settings.gemini_api_key)
            self._model = genai.GenerativeModel(settings.gemini_model)
            logger.info("GeminiClient initialised with model '%s'", settings.gemini_model)
        else:
            logger.warning("GEMINI_API_KEY not set; GeminiClient running in mock mode")

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def generate(self, prompt: str, *, system: str | None = None) -> str:
        """Generate text for the given prompt. Returns a string answer."""
        if not self._enabled:
            return self._mock(prompt)
        try:
            return await self._generate_with_retry(prompt, system)
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"Gemini generation failed: {exc}") from exc

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
    )
    async def _generate_with_retry(self, prompt: str, system: str | None) -> str:
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        response = await asyncio.to_thread(self._model.generate_content, full_prompt)
        text = getattr(response, "text", None)
        if not text:
            raise LLMError("Gemini returned an empty response")
        return text.strip()

    async def generate_json(self, prompt: str, *, system: str | None = None) -> dict | list:
        """Generate a JSON response and parse it. Returns {} on failure / mock mode."""
        if not self._enabled:
            return {}
        try:
            text = await self._generate_json_with_retry(prompt, system)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Gemini JSON generation failed: %s", exc)
            return {}
        return _parse_json(text)

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
    )
    async def _generate_json_with_retry(self, prompt: str, system: str | None) -> str:
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        response = await asyncio.to_thread(
            self._model.generate_content,
            full_prompt,
            generation_config={"response_mime_type": "application/json"},
        )
        return getattr(response, "text", "") or ""

    @staticmethod
    def _mock(prompt: str) -> str:
        snippet = prompt.strip().replace("\n", " ")[:240]
        return (
            "[MOCK ANSWER — set GEMINI_API_KEY for real generation]\n"
            f"Based on the retrieved context, here is a summary of the relevant "
            f"information: {snippet}"
        )
