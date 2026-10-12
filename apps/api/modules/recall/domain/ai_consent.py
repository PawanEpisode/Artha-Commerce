"""
The consent a student gives before any of her notes or pasted text goes to Google for card suggestions (FR-F15-18, the same
posture as F-03 R3). One versioned text: changing the words means a new `VERSION`, which asks every student again. Served by the
API so the version and the words never drift, and recorded with the version the student saw.

**[VERIFY] The wording is a DRAFT for the owner to confirm; it must not go live unreviewed.** The API refuses every suggestion
request unless `GEMINI_DATA_TIER=paid` and `RECALL_AI_CONSENT_APPROVED` equals `VERSION` (see `services/ai_gate.py`).
"""

from __future__ import annotations

VERSION = "2026-10-v1"

TITLE = "Let AI draft cards from your material"

POINTS: tuple[tuple[str, str], ...] = (
    (
        "What is sent",
        "Only what you choose for one request: the text of your notes and highlights for one chapter, wrong-answer "
        "explanations, or text you paste. Nothing is sent until you press Suggest cards.",
    ),
    (
        "Who receives it",
        "Google, through its paid Gemini API. Google says it does not use content sent this way to improve its products. "
        "It may keep a request for a limited time only to detect misuse, and may process it in other countries.",
    ),
    (
        "What we keep",
        "The drafts stay in your account for up to 30 days, until you accept or reject them. A rejected draft is remembered "
        "as a fingerprint for 90 days so it is not suggested again. We keep only the size and cost of each request, "
        "not what Google received.",
    ),
    (
        "Drafts can be wrong",
        "Every draft shows the exact line it came from. Check it against your source. Nothing becomes a card unless you "
        "accept it.",
    ),
    (
        "Taking it back",
        "You can withdraw at any time in Recall settings. Withdrawing deletes all drafts that are waiting.",
    ),
)


def text() -> dict:
    return {"version": VERSION, "title": TITLE, "points": [{"heading": h, "text": t} for h, t in POINTS]}
