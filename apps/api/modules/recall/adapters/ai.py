"""
The one place recall talks to the model (ERD 6.5). It goes through `integrations.gemini` only; services call this adapter, views
never do, and tests replace `generate` so no test ever reaches Google. Errors carry no prompt text.
"""

from __future__ import annotations

from collections.abc import Sequence

from integrations import gemini

from ..domain import suggestions as sdomain

GeminiError = gemini.GeminiError
GeminiBlocked = gemini.GeminiBlocked
GeminiNotConfigured = gemini.GeminiNotConfigured
Result = gemini.GeminiResult


def generate(sources: Sequence[sdomain.SourceText], kinds: Sequence[str], count: int) -> Result:
    """One structured call: the cards (JSON) and the token counts. Raises the Gemini errors above."""
    return gemini.generate_structured(
        sdomain.build_prompt(sources, kinds, count),
        system=sdomain.SYSTEM,
        schema=sdomain.response_schema(kinds),
        max_output_tokens=sdomain.MODEL_OUTPUT_TOKENS,
    )
