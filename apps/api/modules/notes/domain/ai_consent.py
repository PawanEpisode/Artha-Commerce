"""
The AI consent a student gives before any of their text goes to Google (PRD FR-F03-57, Q-F03-9). One versioned text:
changing the wording means a new `VERSION`, which asks every student again. Served by the API so the version and the words
can never drift apart, and recorded with the version the student actually saw.

**[VERIFY] The wording below is a DRAFT for the owner to confirm; it must not go live unreviewed.** It rests on Google's
Gemini API Additional Terms of Service (https://ai.google.dev/gemini-api/terms, read 2026-10-08): content sent through a
*Paid Service* (an API key whose Google Cloud project has an active billing account) is not used to improve Google's products
and is logged for a limited time only to detect abuse; content sent through the unpaid tier may be used to improve products
and read by human reviewers. A consumer Gemini or Google AI Pro subscription is NOT the paid API. The API therefore refuses
every AI call unless `GEMINI_DATA_TIER=paid` and `NOTES_AI_CONSENT_APPROVED` equals `VERSION` (see `services.ai_gate`).

If you change the text, bump VERSION (for example 2026-10-v2) so students are asked again.
Set NOTES_AI_CONSENT_APPROVED to exactly the current VERSION (now 2026-10-v1) on Vercel and Fly.io.
"""

from __future__ import annotations

VERSION = "2026-10-v1"

TITLE = "Use AI help with your notes"

# (heading, text): rendered by the web as a short list. Plain strings, no Markdown.
POINTS: tuple[tuple[str, str], ...] = (
    (
        "What is sent",
        "For an exam summary: the text of your notes and highlights for one chapter, with page numbers. For "
        '"Improve this page": a picture of that one page, only when you press the button. Your PDF file as a whole is never sent.',
    ),
    (
        "Who receives it",
        "Google, through its paid Gemini API. Google says it does not use content sent this way to improve its products. "
        "It may keep a request for a limited time only to detect misuse, and may process it in other countries.",
    ),
    (
        "What we keep",
        "A summary draft stays in your account for up to 14 days, until you accept or discard it. The text read from a page "
        "becomes that page's text in your document. We keep only the size and cost of each request, not what Google received.",
    ),
    (
        "AI can be wrong",
        "Every summary is a draft and every page reading can contain mistakes. Check them against your material before you rely on them.",
    ),
    (
        "Your choice",
        "You can withdraw at any time in Settings, Notes. Withdrawing stops new requests and deletes drafts you have not "
        "accepted. Summaries you accepted stay yours. We cannot recall text that was already sent.",
    ),
)

CHECKBOX = "I understand and agree that the text and page pictures I choose are sent to Google."


def text() -> dict:
    return {
        "version": VERSION,
        "title": TITLE,
        "points": [{"heading": h, "text": t} for h, t in POINTS],
        "checkbox": CHECKBOX,
    }
