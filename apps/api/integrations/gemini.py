"""Thin wrapper over Google AI Studio (Gemini). Business logic never imports google.genai directly."""

from functools import lru_cache

from django.conf import settings


class GeminiNotConfigured(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _client():
    if not settings.GEMINI_API_KEY:
        raise GeminiNotConfigured("GEMINI_API_KEY is not set.")
    from google import genai

    return genai.Client(api_key=settings.GEMINI_API_KEY)


def generate_text(prompt: str, *, system: str | None = None) -> str:
    from google.genai import types

    response = _client().models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=system) if system else None,
    )
    return response.text or ""
