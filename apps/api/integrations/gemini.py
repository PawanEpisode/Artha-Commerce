"""
Thin wrapper over Google AI Studio (Gemini). Business logic never imports google.genai directly, and nothing in the browser
ever calls it: only the API and the worker hold the key.

`generate_text` is the original plain call. `generate_structured` is what F-03 R3 uses: one request, JSON out against a schema,
token counts back, a hard timeout, and errors that say what happened without ever carrying the prompt (a student's notes).
"""

from dataclasses import dataclass
from functools import lru_cache

from django.conf import settings


class GeminiNotConfigured(RuntimeError):
    pass


class GeminiError(RuntimeError):
    """The call failed (network, quota, server error, timeout). Safe to retry. The message never contains the prompt."""


class GeminiBlocked(GeminiError):
    """Google refused the content or returned nothing usable (safety block, empty answer). Retrying will not help."""


@dataclass(frozen=True)
class GeminiResult:
    text: str
    input_tokens: int
    output_tokens: int
    model: str


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


def generate_structured(
    prompt: str,
    *,
    system: str,
    schema: dict,
    max_output_tokens: int = 2500,
    timeout_seconds: int | None = None,
    image: tuple[bytes, str] | None = None,
) -> GeminiResult:
    """
    One call that must answer with JSON matching `schema` (a JSON Schema dict). `image` is `(bytes, mime)` for page OCR.
    Raises `GeminiNotConfigured` (no key), `GeminiBlocked` (refused or empty: do not retry) or `GeminiError` (retry later).
    Temperature is low: summaries and transcriptions should not wander.
    """
    from google.genai import types

    contents: list = [prompt]
    if image is not None:
        contents = [types.Part.from_bytes(data=image[0], mime_type=image[1]), prompt]
    timeout_ms = int((timeout_seconds or settings.GEMINI_TIMEOUT_SECONDS) * 1000)
    config = types.GenerateContentConfig(
        system_instruction=system,
        temperature=0.2,
        max_output_tokens=max_output_tokens,
        response_mime_type="application/json",
        response_json_schema=schema,
        http_options=types.HttpOptions(timeout=timeout_ms),
    )
    try:
        response = _client().models.generate_content(model=settings.GEMINI_MODEL, contents=contents, config=config)
    except GeminiNotConfigured:
        raise
    except Exception as exc:  # noqa: BLE001 - the SDK has many error types; none may leak the prompt
        raise GeminiError(f"Gemini call failed ({type(exc).__name__}).") from None
    feedback = getattr(response, "prompt_feedback", None)
    if feedback is not None and getattr(feedback, "block_reason", None):
        raise GeminiBlocked("Gemini blocked the request.")
    text = (response.text or "").strip()
    if not text:
        raise GeminiBlocked("Gemini returned no text.")
    usage = getattr(response, "usage_metadata", None)
    return GeminiResult(
        text=text,
        input_tokens=int(getattr(usage, "prompt_token_count", 0) or 0),
        output_tokens=int(getattr(usage, "response_token_count", 0) or 0)
        + int(getattr(usage, "thoughts_token_count", 0) or 0),
        model=settings.GEMINI_MODEL,
    )
