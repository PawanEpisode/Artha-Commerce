"""Reserving, completing and aborting a PDF upload: limits before bytes move, idempotency, quota, ownership, the flag."""

import uuid

import pytest

from modules.media.models import Attachment
from modules.notes.models import Document, QuotaUsage

from .documents_support import MB, body, put_bytes, reserve
from .factories import ALICE

pytestmark = pytest.mark.django_db

D = uuid.uuid4()
ROUTES = [
    ("get", "/notes/documents/"),
    ("post", "/notes/documents/"),
    ("get", f"/notes/documents/{D}/"),
    ("patch", f"/notes/documents/{D}/"),
    ("delete", f"/notes/documents/{D}/"),
    ("post", f"/notes/documents/{D}/complete/"),
    ("post", f"/notes/documents/{D}/abort/"),
    ("post", f"/notes/documents/{D}/restore/"),
    ("put", f"/notes/documents/{D}/chapters/"),
    ("put", f"/notes/documents/{D}/progress/"),
    ("get", f"/notes/documents/{D}/processing/"),
    ("get", f"/notes/documents/{D}/pages/text/"),
    ("get", f"/notes/documents/{D}/search/?q=gst"),
]


@pytest.mark.parametrize(("method", "path"), ROUTES)
def test_every_document_route_needs_a_signed_in_student(client, method, path):
    res = getattr(client, method)(f"/api/v1{path}", content_type="application/json")
    assert res.status_code == 401


@pytest.mark.parametrize(("method", "path"), ROUTES)
def test_every_document_route_is_closed_when_the_pdf_flag_is_off(api, pdf_flag_off, method, path):
    res = getattr(api, method)(path, {}) if method in ("post", "put", "patch") else getattr(api, method)(path)
    assert res.status_code == 403 and res.json_body["error"]["code"] == "feature_disabled"


def test_reserving_returns_a_reserved_document_and_a_signed_upload(api, fake_storage):
    res = reserve(api, 5 * MB, source_kind="own_notes", page_count_hint=40)
    assert res.status_code == 201
    doc, upload = res.json_body["document"], res.json_body["upload"]
    assert doc["status"] == "reserved" and doc["title"] == "GST notes" and doc["original_filename"] == "GST notes.pdf"
    assert doc["bytes"] == 5 * MB and doc["page_count"] == 40 and doc["source_kind"] == "own_notes"
    assert doc["file_url"] is None and doc["can_open"] is False and doc["origin"] == "upload"
    assert upload["method"] == "PUT" and upload["url"].startswith("https://") and upload["expires_at"]
    usage = QuotaUsage.objects.get(pk=ALICE)
    assert (usage.bytes_used, usage.docs_active) == (5 * MB, 1)
    attachment = Attachment.objects.get(pk=Document.objects.get().attachment_id)
    assert attachment.kind == "note_pdf" and "GST" not in attachment.path  # ids only, never the file name


def test_a_replayed_client_id_returns_the_same_document_with_200_and_takes_no_quota(api, fake_storage):
    payload = body(2 * MB)
    first = api.post("/notes/documents/", payload)
    again = api.post("/notes/documents/", payload)
    assert (first.status_code, again.status_code) == (201, 200)
    assert again.json_body["document"]["id"] == first.json_body["document"]["id"]
    assert again.json_body["upload"]["url"]  # still expected: a fresh signed URL comes back
    assert Document.objects.count() == 1 and QuotaUsage.objects.get(pk=ALICE).docs_active == 1


@pytest.mark.parametrize(
    ("patch", "status", "code"),
    [
        ({"bytes": 51 * MB}, 413, "file_too_large"),
        ({"mime": "image/png"}, 415, "unsupported_type"),
        ({"page_count_hint": 1001}, 422, "too_many_pages"),
        ({"bytes": 0}, 400, None),
        ({"filename": ""}, 400, None),
        ({"client_id": "nope"}, 400, None),
        ({"source_kind": "weird"}, 400, None),
    ],
)
def test_limits_and_validation_fail_before_any_quota_moves(api, fake_storage, patch, status, code):
    res = api.post("/notes/documents/", {**body(), **patch})
    assert res.status_code == status
    if code:
        assert res.json_body["error"]["code"] == code
    assert not Document.objects.exists() and not QuotaUsage.objects.filter(pk=ALICE, bytes_used__gt=0).exists()


def test_the_limit_details_say_what_the_plan_allows(api, fake_storage):
    big = api.post("/notes/documents/", body(51 * MB))
    pages = api.post("/notes/documents/", {**body(), "page_count_hint": 5000})
    assert big.json_body["error"]["details"] == {"limit_mb": 50}
    assert pages.json_body["error"]["details"] == {"limit": 1000}


def test_a_full_library_answers_429_with_the_largest_documents(api, fake_storage):
    small = api.post("/notes/documents/", body(1 * MB)).json_body["document"]
    QuotaUsage.objects.filter(pk=ALICE).update(docs_active=100)
    res = api.post("/notes/documents/", body(MB))
    err = res.json_body["error"]
    assert res.status_code == 429 and err["code"] == "quota_exceeded"
    assert err["details"]["kind"] == "documents" and err["details"]["limit"] == 100 and err["details"]["plan"] == "free"
    assert err["details"]["largest_documents"] == [{"id": small["id"], "title": "GST notes", "bytes": MB}]
    assert Document.objects.count() == 1


def test_storage_that_does_not_fit_is_refused_as_storage(api, fake_storage):
    QuotaUsage.objects.create(user_id=ALICE, bytes_used=480 * MB)
    res = api.post("/notes/documents/", body(30 * MB))
    assert res.status_code == 429 and res.json_body["error"]["details"]["kind"] == "storage"
    assert QuotaUsage.objects.get(pk=ALICE).bytes_used == 480 * MB


def test_a_chapter_that_is_not_in_the_syllabus_is_refused(api, fake_storage, scheme):
    res = api.post("/notes/documents/", {**body(), "chapter_id": str(uuid.uuid4())})
    assert res.status_code == 422 and res.json_body["error"]["code"] == "unknown_chapter"
    assert not Document.objects.exists()


def test_a_document_filed_under_a_chapter_carries_its_link(api, fake_storage, scheme):
    from modules.syllabus.models import Chapter

    gst = Chapter.objects.get(key="gst-itc")
    doc = api.post("/notes/documents/", {**body(), "chapter_id": str(gst.id)}).json_body["document"]
    assert doc["link"]["chapter_key"] == "gst-itc" and doc["link"]["chapter_id"] == str(gst.id)


def test_complete_before_the_file_arrives_is_409_not_uploaded_and_after_it_moves_on(
    api, fake_storage, django_capture_on_commit_callbacks
):
    doc = reserve(api).json_body["document"]
    early = api.post(f"/notes/documents/{doc['id']}/complete/")
    assert early.status_code == 409 and early.json_body["error"]["code"] == "not_uploaded"
    put_bytes(fake_storage, doc["id"], b"%PDF-1.4\n%fake\n")
    with django_capture_on_commit_callbacks(execute=True):
        done = api.post(f"/notes/documents/{doc['id']}/complete/")
    assert done.status_code == 200 and done.json_body["status"] == "inspecting"
    assert done.json_body["file_url"] and done.json_body["can_open"] is True  # a clean file opens while it is inspected
    assert api.post(f"/notes/documents/{doc['id']}/complete/").json_body["status"] == "inspecting"  # idempotent


def test_a_file_that_is_not_a_pdf_is_rejected_at_completion_and_gives_the_quota_back(
    api, fake_storage, django_capture_on_commit_callbacks
):
    doc = reserve(api, 3 * MB).json_body["document"]
    put_bytes(fake_storage, doc["id"], b"MZ this is an executable " * 100)
    with django_capture_on_commit_callbacks(execute=True):
        done = api.post(f"/notes/documents/{doc['id']}/complete/")
    assert done.json_body["status"] == "rejected" and done.json_body["status_reason"] == "type_mismatch"
    assert done.json_body["file_url"] is None
    usage = QuotaUsage.objects.get(pk=ALICE)
    assert (usage.bytes_used, usage.docs_active) == (0, 0)
    assert not fake_storage.objects  # the object is gone too


def test_abort_releases_the_reservation_and_is_idempotent(api, fake_storage):
    doc = reserve(api, 4 * MB).json_body["document"]
    res = api.post(f"/notes/documents/{doc['id']}/abort/")
    assert res.status_code == 200 and res.json_body == {"id": doc["id"], "status": "expired"}
    assert api.post(f"/notes/documents/{doc['id']}/abort/").status_code == 200
    assert (QuotaUsage.objects.get(pk=ALICE).bytes_used, QuotaUsage.objects.get(pk=ALICE).docs_active) == (0, 0)
    late = api.post(f"/notes/documents/{doc['id']}/complete/")
    assert late.status_code == 409 and late.json_body["error"]["code"] == "not_uploaded"
    assert api.get("/notes/documents/").json_body["items"] == []  # an abandoned upload is not a library entry


def test_a_confirmed_upload_cannot_be_aborted(api, fake_storage, django_capture_on_commit_callbacks):
    doc = reserve(api).json_body["document"]
    put_bytes(fake_storage, doc["id"], b"%PDF-1.4\n")
    with django_capture_on_commit_callbacks(execute=True):
        api.post(f"/notes/documents/{doc['id']}/complete/")
    res = api.post(f"/notes/documents/{doc['id']}/abort/")
    assert res.status_code == 409 and res.json_body["error"]["code"] == "not_abortable"


def test_other_students_documents_are_404_on_every_detail_route(api, other_api, fake_storage):
    doc = reserve(api).json_body["document"]["id"]
    base = f"/notes/documents/{doc}"
    checks = [
        other_api.get(f"{base}/"),
        other_api.patch(f"{base}/", {"title": "mine now"}),
        other_api.delete(f"{base}/"),
        other_api.delete(f"{base}/?permanent=1"),
        other_api.post(f"{base}/complete/"),
        other_api.post(f"{base}/abort/"),
        other_api.post(f"{base}/restore/"),
        other_api.put(f"{base}/chapters/", {"ranges": []}),
        other_api.put(f"{base}/progress/", {"last_page": 2, "last_zoom": "fit"}),
        other_api.get(f"{base}/processing/"),
        other_api.get(f"{base}/pages/text/"),
        other_api.get(f"{base}/search/?q=gst"),
    ]
    assert [r.status_code for r in checks] == [404] * len(checks)
    assert api.get(f"{base}/").json_body["status"] == "reserved"
    assert other_api.get("/notes/documents/").json_body["items"] == []


def test_reserving_is_throttled_to_thirty_an_hour_but_reading_the_library_is_not(api, fake_storage):
    codes = [reserve(api, 100).status_code for _ in range(31)]
    assert codes[:30] == [201] * 30 and codes[30] == 429
    assert api.get("/notes/documents/").status_code == 200
