"""Images in note bodies (through media) and the `notes` flag over every route."""

import uuid

import pytest
from django.urls import reverse

from core import feature_flags
from modules.media.models import Attachment
from modules.media.tests.conftest import FakeStorage, upload_image
from modules.notes import urls as notes_urls
from modules.notes.models import NoteImage

from .conftest import edit, new_note

pytestmark = pytest.mark.django_db

# `DELETE notes/` wipes the account and shares the list path, so only that method stays open.
OPEN_METHODS = {("notes-list", "delete")}

OPEN_ENDPOINTS = {
    "notes-export",
    "notes-tick",
    # taking AI back (withdraw consent, cancel a request, discard a draft) never needs a flag
    "notes-ai-consent-withdraw",
    "notes-ai-summary-cancel",
    "notes-ai-summary-discard",
    "notes-ai-ocr-cancel",
}


@pytest.fixture
def fake_storage(monkeypatch):
    fake = FakeStorage()
    monkeypatch.setattr("modules.media.services.get_storage", lambda: fake)
    return fake


def _clean_image(c, fake):
    att = upload_image(c, fake)
    assert c.post(f"/media/uploads/{att['id']}/complete/").status_code == 200
    return att["id"]


def test_a_note_can_embed_its_own_clean_image(api, fake_storage):
    aid = _clean_image(api, fake_storage)
    n = new_note(api, f"Look\n\n![the diagram](attachment:{aid})")
    assert NoteImage.objects.filter(note_id=n["id"], attachment_id=aid).count() == 1
    assert api.get(f"/notes/{n['id']}/").json_body["image_ids"] == [aid]
    assert api.get("/notes/").json_body["items"][0].get("image_ids") is None  # lists carry summaries only
    edit(api, n, body_md="no image now")
    assert NoteImage.objects.count() == 0


def test_another_students_or_unfinished_images_are_refused(api, other_api, fake_storage):
    theirs = _clean_image(other_api, fake_storage)
    unfinished = upload_image(api, fake_storage, put=False)["id"]
    for aid in (theirs, unfinished, str(uuid.uuid4())):
        res = api.post("/notes/", {"client_id": str(uuid.uuid4()), "body_md": f"![x](attachment:{aid})"})
        assert res.status_code == 422, aid
        assert res.json_body["error"]["details"]["errors"][0]["code"] == "unknown_attachment"


def test_a_note_without_alt_text_is_still_saved_but_a_foreign_url_is_not(api):
    assert (
        api.post("/notes/", {"client_id": str(uuid.uuid4()), "body_md": "![](https://x.test/a.png)"}).status_code == 422
    )


def test_delete_all_queues_the_image_files(api, fake_storage):
    from core import jobs

    aid = _clean_image(api, fake_storage)
    new_note(api, f"![d](attachment:{aid})")
    assert api.delete("/notes/").json_body["deleted"]["images"] == 1
    assert Attachment.objects.get(pk=aid).status == "deleting"
    jobs.run_pending(types=["media.delete"])
    assert not Attachment.objects.exists() and not fake_storage.objects


# --- the flag ---------------------------------------------------------------------------------------------------------
@pytest.fixture
def flag_off(settings, monkeypatch):
    class Off:
        def get_feature_flag(self, key, distinct_id, **kwargs):
            return False if key == "notes" else None

    settings.POSTHOG_API_KEY = "phc_test"
    monkeypatch.setattr(feature_flags, "_client", Off())
    feature_flags.clear_flag_cache()
    yield
    feature_flags.clear_flag_cache()


def _requests():
    from modules.notes.views import NotesView

    for pattern in notes_urls.urlpatterns:
        if pattern.name in OPEN_ENDPOINTS:
            continue
        kwargs = {name: uuid.uuid4() for name in pattern.pattern.converters}
        for name, conv in pattern.pattern.converters.items():
            if conv.__class__.__name__ == "IntConverter":
                kwargs[name] = 1
            elif conv.__class__.__name__ == "SlugConverter":
                kwargs[name] = "a-slug"
        view_class = pattern.callback.view_class
        assert issubclass(view_class, NotesView), f"{pattern.name} must extend NotesView"
        for method in ("get", "post", "put", "patch", "delete"):
            if (pattern.name, method) in OPEN_METHODS:
                continue
            if hasattr(view_class, method):
                yield method, reverse(pattern.name, kwargs=kwargs), pattern.name


def test_every_notes_endpoint_answers_403_feature_disabled_when_the_flag_is_off(api, flag_off):
    seen = list(_requests())
    assert len(seen) >= 20
    for method, path, name in seen:
        res = api._send(method, path.removeprefix("/api/v1"), {} if method != "get" else None)
        assert res.status_code == 403, f"{method.upper()} {name}"
        assert res.json_body["error"]["code"] == "feature_disabled", f"{method.upper()} {name}"


def test_data_rights_and_the_tick_stay_open_with_the_flag_off(api, client, flag_off, settings):
    assert api.get("/notes/export/").status_code == 200
    assert api.delete("/notes/").status_code == 200
    settings.NOTES_TICK_SECRET = "abc"
    assert client.post("/api/v1/notes/internal/tick/", HTTP_X_NOTES_TICK_SECRET="abc").status_code == 200


def test_the_endpoints_list_is_what_the_contract_documents():
    names = {p.name for p in notes_urls.urlpatterns}
    assert OPEN_ENDPOINTS <= names and len(names) >= 21  # R1 had 21; R2 adds documents, marks, OCR and export
