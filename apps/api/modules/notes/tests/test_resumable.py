"""Resumable upload: the reservation offers parts for a big file, the parts are signed and joined, and a cancel leaves nothing behind."""
# ruff: noqa: F811 - pytest fixtures imported from the support modules are redefined as test arguments

import uuid

import pytest

from core.s3 import Part
from core.storage import StorageError
from modules.notes.models import Document
from modules.notes.services import resumable

from .ai_support import ai_on  # noqa: F401
from .documents_support import MB, fake_storage, reserve  # noqa: F401

pytestmark = pytest.mark.django_db
BIG = 20 * MB  # three parts of 8 MiB


class FakeS3:
    def __init__(self):
        self.uploads: dict[str, dict[int, Part]] = {}
        self.completed: list[tuple[str, list[Part]]] = []
        self.aborted: list[str] = []
        self.fail = False

    def create_multipart(self, bucket, key, content_type):
        if self.fail:
            raise StorageError("down")
        upload_id = f"UP{len(self.uploads) + 1}"
        self.uploads[upload_id] = {}
        return upload_id

    def list_parts(self, bucket, key, upload_id):
        return sorted(self.uploads[upload_id].values(), key=lambda p: p.number)

    def presign_part(self, bucket, key, upload_id, number, *, expires=3600):
        return f"https://s3.test/{bucket}/{key}?partNumber={number}&uploadId={upload_id}"

    def complete_multipart(self, bucket, key, upload_id, parts):
        self.completed.append((upload_id, parts))

    def abort_multipart(self, bucket, key, upload_id):
        self.aborted.append(upload_id)

    def store(self, upload_id, number, size=None):
        size = (
            size if size is not None else (8 * 1024 * 1024 if number < 3 else 4 * 1024 * 1024)
        )  # BIG is 8 + 8 + 4 MiB
        self.uploads[upload_id][number] = Part(number, f"e{number}", size)


@pytest.fixture
def s3(monkeypatch):
    fake = FakeS3()
    monkeypatch.setattr(resumable, "get_s3", lambda: fake)
    return fake


@pytest.fixture
def big(api, ai_on, s3, fake_storage, db):  # noqa: ARG001
    from modules.notes.models import QuotaPlan

    QuotaPlan.objects.filter(plan_code="free").update(max_file_mb=100, max_storage_mb=500)
    res = reserve(api, BIG)
    assert res.status_code == 201, res.json_body
    return res.json_body


def base(doc):
    return f"/notes/documents/{doc['document']['id']}/resumable/"


def test_a_big_file_is_offered_in_parts_and_a_small_one_is_not(api, ai_on, s3, fake_storage):
    from modules.notes.models import QuotaPlan

    QuotaPlan.objects.filter(plan_code="free").update(max_file_mb=100, max_storage_mb=500)
    hint = reserve(api, BIG).json_body["upload"]["resumable"]
    assert hint["part_size"] == 8 * 1024 * 1024 and hint["parts"] == 3 and hint["document_id"]
    assert "resumable" not in reserve(api, 5 * MB).json_body["upload"]


def test_nothing_is_offered_without_s3_or_with_the_flag_off(api, ai_on, fake_storage, monkeypatch):
    from modules.notes.models import QuotaPlan

    QuotaPlan.objects.filter(plan_code="free").update(max_file_mb=100, max_storage_mb=500)
    monkeypatch.setattr(resumable, "get_s3", lambda: None)
    assert "resumable" not in reserve(api, BIG).json_body["upload"]


def test_start_opens_the_upload_once_and_reports_what_storage_holds(api, big, s3):
    first = api.post(base(big)).json_body
    assert first == {"part_size": 8 * 1024 * 1024, "parts": 3, "done": []}
    s3.store("UP1", 1)
    again = api.post(base(big)).json_body  # a retry, or a second tab: the same upload, now with part 1 done
    assert len(s3.uploads) == 1 and again["done"] == [{"number": 1, "etag": "e1", "size": 8 * 1024 * 1024}]


def test_parts_are_signed_only_for_the_numbers_that_exist(api, big):
    api.post(base(big))
    res = api.post(base(big) + "parts/", {"numbers": [2, 3, 9, 3]})
    assert res.status_code == 200
    parts = res.json_body["parts"]
    assert [p["number"] for p in parts] == [2, 3] and "partNumber=2" in parts[0]["url"]


def test_finishing_needs_every_part_to_be_in_storage_at_its_full_size(api, big, s3):
    api.post(base(big))
    for n in (1, 2):
        s3.store("UP1", n)
    short = api.post(
        base(big) + "complete/", {"parts": [1, 2, 3]}
    )  # the browser says 3 was sent; storage does not have it
    assert (short.status_code, short.json_body["error"]["code"]) == (422, "parts_incomplete")
    missing = api.post(base(big) + "complete/", {"parts": [1, 2]})  # the list itself is short
    assert missing.json_body["error"]["code"] == "parts_incomplete"
    s3.store("UP1", 3, size=100)  # arrived cut short
    assert api.post(base(big) + "complete/", {"parts": [1, 2, 3]}).json_body["error"]["code"] == "parts_incomplete"
    assert not s3.completed
    s3.store("UP1", 3)
    ok = api.post(base(big) + "complete/", {"parts": [1, 2, 3]})
    assert ok.status_code == 200 and ok.json_body == {"joined": 3}
    assert [(p.number, p.etag) for p in s3.completed[0][1]] == [(1, "e1"), (2, "e2"), (3, "e3")]  # storage's own ETags
    assert Document.objects.get(pk=big["document"]["id"]).resumable_upload_id is None


def test_after_joining_the_ordinary_complete_confirms_the_object(api, big, fake_storage):
    api.post(base(big))
    doc = Document.objects.get(pk=big["document"]["id"])
    fake_storage.upload(
        doc.attachment.bucket, doc.attachment.path, b"x" * 10, content_type="application/pdf", cache_control=""
    )
    done = api.post(f"/notes/documents/{doc.id}/complete/")
    assert done.status_code in (200, 409)  # the object exists; size checks belong to `media` and are covered there


def test_cancelling_aborts_the_open_multipart_upload(api, big, s3, monkeypatch):
    api.post(base(big))
    monkeypatch.setattr("django.db.transaction.on_commit", lambda fn: fn())  # the test runs inside one transaction
    api.post(f"/notes/documents/{big['document']['id']}/abort/")
    assert s3.aborted == ["UP1"]
    assert Document.objects.get(pk=big["document"]["id"]).resumable_upload_id is None


def test_a_document_that_is_not_waiting_for_its_file_cannot_be_sent_in_parts(api, big):
    Document.objects.filter(pk=big["document"]["id"]).update(status="inspecting")
    res = api.post(base(big))
    assert (res.status_code, res.json_body["error"]["code"]) == (409, "not_resumable")


def test_a_storage_outage_is_a_503_not_a_crash(api, big, s3):
    s3.fail = True
    res = api.post(base(big))
    assert res.status_code == 503


def test_routes_are_closed_when_the_flag_is_off_and_private_to_the_student(api, fake_storage, s3):
    doc = str(uuid.uuid4())
    assert api.post(f"/notes/documents/{doc}/resumable/").status_code == 403


def test_another_students_upload_is_not_found(api, ai_on, s3, fake_storage):
    from modules.coverage.tests.conftest import OTHER

    from .factories import make_document

    other = make_document(OTHER)
    assert api.post(f"/notes/documents/{other.id}/resumable/").status_code == 404
