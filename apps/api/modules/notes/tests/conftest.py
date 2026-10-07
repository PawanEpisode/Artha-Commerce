import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from modules.notes.services import notes as note_services
from modules.syllabus.models import Chapter
from modules.tracking.tests.conftest import (  # noqa: F401 - shared two-student JSON clients and a seeded scheme
    NOW,
    Clock,
    _fresh_throttle_counters,
    api,
    ids,
    other_api,
    scheme,
)


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    c = Clock(timezone.now())  # row timestamps come from the database clock, so the fake one starts at the real now
    monkeypatch.setattr(note_services, "_now", c)
    return c


@pytest.fixture
def chapter(scheme):  # noqa: F811
    return Chapter.objects.get(key="gst-itc")


@pytest.fixture
def level_id(scheme):  # noqa: F811
    return str(scheme.level_id)


def new_note(c, body="", title="", **extra):
    payload = {"client_id": str(uuid.uuid4()), "title": title, "body_md": body, **extra}
    res = c.post("/notes/notes/", payload)
    assert res.status_code == 201, res.json_body
    return res.json_body


def edit(c, note, **fields):
    """PATCH against the note's current revision."""
    body = {"base_rev": note["rev"], **fields}
    return c.patch(f"/notes/notes/{note['id']}/", body)


def later(clock, **kwargs):
    clock.advance(**kwargs)


def age_versions(note_id, **delta):
    """Moves a note's version rows into the past, as if that much time had gone by (row timestamps are auto)."""
    from modules.notes.models import NoteVersion

    for v in NoteVersion.objects.filter(note_id=note_id):
        NoteVersion.objects.filter(pk=v.pk).update(
            created_at=v.created_at - timedelta(**delta), updated_at=v.updated_at - timedelta(**delta)
        )


from .documents_support import (  # noqa: E402, F401 - fixtures of the R2 document tests
    capture_events,
    fake_storage,
    pdf_flag_off,
)
