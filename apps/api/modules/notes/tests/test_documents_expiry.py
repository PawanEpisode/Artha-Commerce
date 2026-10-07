"""Reservation expiry through the tick, next to the media sweep, and the concurrency of two simultaneous reservations."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from django.db import close_old_connections, connection
from django.utils import timezone

from core import jobs
from modules.media.models import Attachment
from modules.notes import jobs as notes_jobs
from modules.notes.models import Document, QuotaUsage

from .documents_support import MB, body, put_bytes, reserve
from .factories import ALICE

pytestmark = pytest.mark.django_db


def usage():
    row = QuotaUsage.objects.get(pk=ALICE)
    return row.bytes_used, row.docs_active


def age(document_id, minutes=40):
    """As if the upload had been reserved `minutes` ago."""
    past = timezone.now() - timedelta(minutes=minutes)
    Document.objects.filter(pk=document_id).update(reservation_expires_at=past + timedelta(minutes=29))
    Attachment.objects.filter(pk=Document.objects.get(pk=document_id).attachment_id).update(
        expires_at=past + timedelta(minutes=30)
    )


def test_the_tick_expires_an_unconfirmed_upload_and_releases_its_quota(api, fake_storage):
    stale = reserve(api, 3 * MB).json_body["document"]["id"]
    fresh = reserve(api, 2 * MB).json_body["document"]["id"]
    age(stale)
    assert usage() == (5 * MB, 2)
    notes_jobs.tick()
    assert Document.objects.get(pk=stale).status == "expired" and Document.objects.get(pk=fresh).status == "reserved"
    assert usage() == (2 * MB, 1)
    assert api.get(f"/notes/documents/{stale}/").json_body["status"] == "expired"  # still readable by id for the client
    assert [d["id"] for d in api.get("/notes/documents/").json_body["items"]] == [fresh]
    late = api.post(f"/notes/documents/{stale}/complete/")
    assert late.status_code == 409 and late.json_body["error"]["code"] == "not_uploaded"
    notes_jobs.tick()  # re-entrant: nothing is released twice
    assert usage() == (2 * MB, 1)


def test_the_media_sweep_running_first_does_not_double_release(api, fake_storage):
    stale = reserve(api, 3 * MB).json_body["document"]["id"]
    age(stale)
    from modules.media import services as media

    media.expire_reservations()  # the generic sweep got there before notes' job
    from modules.notes.services import document_trash

    assert document_trash.expire_reservations() == 0  # the attachment is `deleting`: media owns the release
    jobs.run_pending(types=["media.delete"])
    assert usage() == (0, 0) and not Document.objects.exists()  # the empty reserved document went with its attachment


def test_an_expired_row_and_its_object_are_removed_a_day_later(api, fake_storage):
    stale = reserve(api, 3 * MB).json_body["document"]["id"]
    put_bytes(fake_storage, stale, b"%PDF-1.4 never completed")  # uploaded, never confirmed
    age(stale)
    notes_jobs.tick()
    assert Document.objects.filter(pk=stale, status="expired").exists() and fake_storage.objects
    Document.objects.filter(pk=stale).update(updated_at=timezone.now() - timedelta(days=2))
    notes_jobs.tick()
    jobs.run_pending(types=["media.delete"])
    assert not Document.objects.exists() and not Attachment.objects.exists() and not fake_storage.objects
    assert usage() == (0, 0)


def test_a_reserved_document_that_is_confirmed_in_time_is_not_expired(
    api, fake_storage, django_capture_on_commit_callbacks
):
    doc = reserve(api).json_body["document"]["id"]
    put_bytes(fake_storage, doc, b"%PDF-1.4\n")
    with django_capture_on_commit_callbacks(execute=True):
        api.post(f"/notes/documents/{doc}/complete/")
    assert Document.objects.get(pk=doc).reservation_expires_at is None
    age(doc, minutes=120)
    notes_jobs.tick()
    assert Document.objects.get(pk=doc).status == "inspecting"


# --- concurrency (PostgreSQL) ----------------------------------------------------------------------------------------------------
@pytest.mark.django_db(transaction=True, serialized_rollback=True)
@pytest.mark.skipif(connection.vendor != "postgresql", reason="concurrency semantics need PostgreSQL")
def test_two_simultaneous_reservations_for_the_last_slot_only_one_wins(make_token, fake_storage):
    from modules.coverage.tests.conftest import Api

    QuotaUsage.objects.create(user_id=ALICE, docs_active=99)
    token = make_token(sub=str(ALICE))

    def run(_):
        close_old_connections()
        try:
            return Api(token).post("/notes/documents/", body(MB)).status_code
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = sorted(pool.map(run, range(2)))
    assert codes == [201, 429]
    assert Document.objects.filter(user_id=ALICE).count() == 1 and usage() == (MB, 100)


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
@pytest.mark.skipif(connection.vendor != "postgresql", reason="concurrency semantics need PostgreSQL")
def test_the_same_client_id_sent_twice_at_once_creates_one_document(make_token, fake_storage):
    from modules.coverage.tests.conftest import Api

    token = make_token(sub=str(ALICE))
    payload = body(MB, client_id=str(uuid.uuid4()))

    def run(_):
        close_old_connections()
        try:
            return Api(token).post("/notes/documents/", payload).status_code
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=4) as pool:
        codes = list(pool.map(run, range(4)))
    assert codes.count(201) == 1 and set(codes) <= {200, 201}
    assert Document.objects.count() == 1 and usage() == (MB, 1)
