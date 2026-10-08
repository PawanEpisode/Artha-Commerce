"""Fixtures and builders for the R3 AI tests: every gate open, a scripted Gemini, a chapter with enough of the student's material."""

from __future__ import annotations

import json
import uuid

import pytest

from core import feature_flags
from integrations import gemini
from modules.notes.domain import ai_consent
from modules.notes.models import Annotation, Note
from modules.notes.services import links

from .conftest import new_note  # noqa: F401
from .factories import make_annotation, make_document

LONG = (
    "Input tax credit can be claimed only when the goods or services are used in the course or furtherance of business, "
    "the supplier has filed the return and the tax has actually been paid to the government account. "
)


class FakeGemini:
    """Replaces `integrations.gemini.generate_structured`. `reply` is JSON text or an exception to raise."""

    def __init__(self):
        self.calls: list[dict] = []
        self.reply: object = None
        self.on_call = None

    def __call__(self, prompt, *, system, schema, max_output_tokens=2500, timeout_seconds=None, image=None):
        self.calls.append({"prompt": prompt, "system": system, "image": image})
        if self.on_call:
            self.on_call()
        if isinstance(self.reply, Exception):
            raise self.reply
        text = self.reply if self.reply is not None else good_reply(sources=[1, 2, 3])
        return gemini.GeminiResult(text=text, input_tokens=2000, output_tokens=400, model="gemini-test")


def good_reply(sources=(1, 2, 3)) -> str:
    refs = list(sources)
    return json.dumps(
        {
            "title": "GST: input tax credit",
            "sections": [
                {
                    "heading": "When ITC is allowed",
                    "points": [
                        {"text": "Claim only for business use.", "sources": refs[:1]},
                        {"text": "The supplier must have filed the return.", "sources": refs[1:2] or refs[:1]},
                        {"text": "Tax must be paid to the government.", "sources": refs[2:3] or refs[:1]},
                    ],
                }
            ],
        }
    )


@pytest.fixture
def gemini_fake(monkeypatch):
    fake = FakeGemini()
    monkeypatch.setattr(gemini, "generate_structured", fake)
    return fake


@pytest.fixture
def ai_on(settings, monkeypatch):
    """Key, paid tier, approved wording and a budget are set, and PostHog says `notes_ai` is on."""
    settings.GEMINI_API_KEY = "test-key"
    settings.GEMINI_DATA_TIER = "paid"
    settings.GEMINI_MODEL = "gemini-test"
    settings.NOTES_AI_CONSENT_APPROVED = ai_consent.VERSION
    settings.NOTES_AI_SUMMARY_ENABLED = True
    settings.NOTES_AI_OCR_ENABLED = True
    settings.NOTES_AI_DAILY_BUDGET_PAISE = 100_000

    class On:
        def get_feature_flag(self, key, distinct_id, **kwargs):
            return True if key == "notes_ai" else None

    settings.POSTHOG_API_KEY = "phc_test"
    monkeypatch.setattr(feature_flags, "_client", On())
    feature_flags.clear_flag_cache()
    yield
    feature_flags.clear_flag_cache()


def seed_chapter(api, chapter, user_id, *, notes=2, marks=2):
    """Two long notes and two highlights on one chapter of the student. Returns `(note_ids, mark_ids)`."""
    note_ids = [
        new_note(api, f"{LONG * 2} Point {i}.", title=f"ITC note {i}", chapter_id=str(chapter.id))["id"]
        for i in range(notes)
    ]
    link = links.link_columns(chapter.id)
    document = make_document(user_id, title="Study PDF")
    mark_ids = [
        str(
            make_annotation(
                document,
                page=3 + i,
                quote_exact=f"Credit is blocked for motor vehicles, case {i}.",
                chapter_source="explicit",
                seq=i + 1,
                **link,
            ).id
        )
        for i in range(marks)
    ]
    return note_ids, mark_ids


def post_summary(api, chapter, **extra):
    return api.post("/notes/ai/summary/", {"client_id": str(uuid.uuid4()), "chapter_id": str(chapter.id), **extra})


def agree(api):
    return api.put("/notes/ai/consent/", {"version": ai_consent.VERSION})


def marks_of(user_id):
    return Annotation.objects.filter(user_id=user_id)


def notes_of(user_id):
    return Note.objects.filter(user_id=user_id)
