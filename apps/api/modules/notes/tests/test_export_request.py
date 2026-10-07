"""`POST documents/{id}/exports/`, `POST export/archive/`, `GET exports/{id}/`: the requests, their rules and their quota."""
# ruff: noqa: F811 - pytest fixtures imported from `ocr_export_support` are redefined as test arguments

import uuid

import pytest
from django.core.cache import cache
from django.utils import timezone

from core.models import Job
from modules.coverage.tests.conftest import USER
from modules.notes.models import Document, ExportJob, FileContent, MonthlyUsage
from modules.notes.services import quota

from .ocr_export_support import fake_storage, make_pdf_document  # noqa: F401
from .test_ocr_request import _this_month
from .worker.fixtures import make_pdfs as mk

pytestmark = pytest.mark.django_db


def post(api, document, *, throttled=False, **body):
    if not throttled:
        cache.clear()  # six requests an hour per student: only the throttle test wants to feel it
    payload = {"client_id": str(uuid.uuid4()), "options": {}, **body}
    return api.post(f"/notes/documents/{document.id}/exports/", payload)


def exports_used(user=USER) -> int:
    row = MonthlyUsage.objects.filter(user_id=user).first()
    return row.exports if row else 0


@pytest.fixture
def doc(fake_storage, tmp_path):
    return make_pdf_document(
        fake_storage, USER, mk.text_pdf(tmp_path / "t.pdf", pages=5), can_copy=True, can_modify=True
    )


def test_a_request_queues_the_job_charges_once_and_answers_202_with_the_contract_shape(api, doc):
    res = post(api, doc, options={"pages": "1-3", "include": ["highlight"], "appendix": True})
    assert res.status_code == 202, res.json_body
    job = res.json_body["export"]
    assert set(job) == {
        "id", "kind", "document_id", "status", "progress", "page_count", "error_code",
        "download_url", "expires_at", "options", "created_at", "details",
    }  # fmt: skip
    assert (job["kind"], job["document_id"], job["status"], job["progress"]) == ("pdf", str(doc.id), "queued", 0)
    assert job["options"] == {"pages": "1-3", "include": ["highlight"], "appendix": True}
    assert job["download_url"] is None and job["page_count"] is None and job["error_code"] is None
    assert exports_used() == 1
    queued = Job.objects.get(type="notes.export_pdf")
    assert queued.payload == {"export_id": job["id"]} and queued.dedupe_key == f"notes.export_pdf:{job['id']}"


def test_a_replayed_client_id_returns_the_same_job_with_200_and_charges_nothing(api, doc):
    client_id = str(uuid.uuid4())
    first = api.post(f"/notes/documents/{doc.id}/exports/", {"client_id": client_id, "options": {}})
    again = api.post(f"/notes/documents/{doc.id}/exports/", {"client_id": client_id, "options": {"pages": "1"}})
    assert (first.status_code, again.status_code) == (202, 200)
    assert again.json_body["export"]["id"] == first.json_body["export"]["id"]
    assert again.json_body["export"]["options"] == {}  # the stored job, not the new options
    assert exports_used() == 1 and ExportJob.objects.count() == 1 and Job.objects.count() == 1


def test_bad_bodies_and_options_are_422_or_400_and_cost_nothing(api, doc):
    assert api.post(f"/notes/documents/{doc.id}/exports/", {}).status_code == 400
    assert api.post(f"/notes/documents/{doc.id}/exports/", {"client_id": "nope"}).status_code == 400
    for options, field in (
        ({"pages": "9"}, "pages"),
        ({"include": ["bookmark"]}, "include"),
        ({"colors": ["red"]}, "colors"),
        ({"appendix": "yes"}, "appendix"),
        ({"surprise": 1}, "options"),
        ({"tags": [str(uuid.uuid4())]}, "tags"),  # not this student's tag
    ):
        res = post(api, doc, options=options)
        assert res.status_code == 422, options
        assert (
            res.json_body["error"]["code"] == "invalid_options" and res.json_body["error"]["details"]["field"] == field
        )
    cache.clear()
    bad_tag = api.post(
        f"/notes/documents/{doc.id}/exports/", {"client_id": str(uuid.uuid4()), "options": {"tags": ["x"]}}
    )
    assert bad_tag.status_code == 400
    assert exports_used() == 0 and not ExportJob.objects.exists()


def test_401_and_cross_user_404(api, other_api, doc, client):
    body = {"client_id": str(uuid.uuid4())}
    assert (
        client.post(f"/api/v1/notes/documents/{doc.id}/exports/", body, content_type="application/json").status_code
        == 401
    )
    assert other_api.post(f"/notes/documents/{doc.id}/exports/", body).status_code == 404
    assert api.post(f"/notes/documents/{uuid.uuid4()}/exports/", body).status_code == 404
    Document.objects.filter(pk=doc.pk).update(deleted_at=timezone.now())
    assert api.post(f"/notes/documents/{doc.id}/exports/", body).status_code == 404
    assert not ExportJob.objects.exists()


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"can_copy": False}, "restricted"),
        ({"can_modify": False}, "restricted"),
    ],
)
def test_a_copy_restricted_file_cannot_be_exported(api, doc, changes, reason):
    FileContent.objects.filter(pk=doc.content_id).update(**changes)
    res = post(api, doc)
    assert res.status_code == 422 and res.json_body["error"]["code"] == "export_not_allowed"
    assert res.json_body["error"]["details"] == {"reason": reason}
    assert exports_used() == 0


def test_a_locked_or_unprepared_file_cannot_be_exported(api, doc):
    Document.objects.filter(pk=doc.pk).update(status="needs_password")
    res = post(api, doc)
    assert res.status_code == 422 and res.json_body["error"]["details"] == {"reason": "locked"}
    Document.objects.filter(pk=doc.pk).update(status="inspecting")
    assert post(api, doc).json_body["error"]["details"] == {"reason": "not_ready"}
    assert exports_used() == 0


def test_the_monthly_export_limit_answers_429_and_changes_nothing(api, doc):
    limit = quota.exports_per_month(USER)
    MonthlyUsage.objects.create(user_id=USER, month=_this_month(), exports=limit)
    res = post(api, doc)
    assert res.status_code == 429
    err = res.json_body["error"]
    assert err["code"] == "quota_exceeded" and err["details"]["kind"] == "export"
    assert (err["details"]["used"], err["details"]["limit"], err["details"]["plan"]) == (limit, limit, "free")
    assert "resets_on" in err["details"]
    assert not ExportJob.objects.exists() and not Job.objects.exists()  # the job row rolled back with the charge
    assert exports_used() == limit


def test_the_throttle_is_six_an_hour(api, doc):
    codes = [post(api, doc, throttled=True).status_code for _ in range(7)]
    assert codes[:6] == [202] * 6 and codes[6] == 429


def test_get_returns_only_the_students_own_export(api, other_api, doc, client):
    job = post(api, doc).json_body["export"]
    res = api.get(f"/notes/exports/{job['id']}/")
    assert res.status_code == 200 and res.json_body["id"] == job["id"] and res.json_body["status"] == "queued"
    assert other_api.get(f"/notes/exports/{job['id']}/").status_code == 404
    assert api.get(f"/notes/exports/{uuid.uuid4()}/").status_code == 404
    assert client.get(f"/api/v1/notes/exports/{job['id']}/").status_code == 401


def test_the_archive_request_is_idempotent_and_only_one_runs_at_a_time(api, other_api):
    client_id = str(uuid.uuid4())
    first = api.post("/notes/export/archive/", {"client_id": client_id})
    assert first.status_code == 202 and first.json_body["export"]["kind"] == "archive"
    assert first.json_body["export"]["document_id"] is None and first.json_body["export"]["status"] == "queued"
    assert api.post("/notes/export/archive/", {"client_id": client_id}).status_code == 200
    busy = api.post("/notes/export/archive/", {"client_id": str(uuid.uuid4())})
    assert busy.status_code == 200 and busy.json_body["export"]["id"] == first.json_body["export"]["id"]
    assert ExportJob.objects.count() == 1 and Job.objects.filter(type="notes.export_archive").count() == 1
    assert exports_used() == 0  # the archive is not charged to the monthly exports
    assert api.post("/notes/export/archive/", {}).status_code == 400
    other = other_api.post("/notes/export/archive/", {"client_id": str(uuid.uuid4())})
    assert other.status_code == 202 and other.json_body["export"]["id"] != first.json_body["export"]["id"]
    assert other_api.get(f"/notes/exports/{first.json_body['export']['id']}/").status_code == 404


def test_the_flags_gate_each_route_as_documented(api, doc, monkeypatch):
    from core import feature_flags

    class Flags:
        def __init__(self, off):
            self.off = off

        def get_feature_flag(self, key, distinct_id, **kwargs):
            return False if key in self.off else None

    def with_off(*names):
        from django.conf import settings

        settings.POSTHOG_API_KEY = "phc_test"
        monkeypatch.setattr(feature_flags, "_client", Flags(set(names)))
        feature_flags.clear_flag_cache()

    job = post(api, doc).json_body["export"]
    archive = api.post("/notes/export/archive/", {"client_id": str(uuid.uuid4())}).json_body["export"]
    try:
        with_off("notes_pdf")
        assert post(api, doc).json_body["error"]["code"] == "feature_disabled"
        assert api.post(f"/notes/documents/{doc.id}/ocr/", {"mode": "tesseract"}).status_code == 403
        assert api.get(f"/notes/exports/{job['id']}/").status_code == 403
        assert api.get(f"/notes/exports/{archive['id']}/").status_code == 200  # the archive needs only `notes`
        assert api.post("/notes/export/archive/", {"client_id": str(uuid.uuid4())}).status_code == 200
        with_off("notes")
        for res in (
            api.post("/notes/export/archive/", {"client_id": str(uuid.uuid4())}),
            api.get(f"/notes/exports/{archive['id']}/"),
            post(api, doc),
        ):
            assert res.status_code == 403 and res.json_body["error"]["code"] == "feature_disabled"
    finally:
        feature_flags.clear_flag_cache()
