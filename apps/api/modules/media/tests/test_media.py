"""Attachments: reserve, upload, complete, serve, delete. Exercised with the `note_image` kind, the one R1 registers."""

from datetime import timedelta

import pytest
from django.utils import timezone

from core import jobs
from modules.media import registry, services
from modules.media.models import Attachment
from modules.notes.models import QuotaUsage

from .conftest import new_id, upload_image

pytestmark = pytest.mark.django_db


def test_every_endpoint_needs_a_token(client):
    assert client.post("/api/v1/media/uploads/", data={}, content_type="application/json").status_code == 401
    assert client.get(f"/api/v1/media/attachments/{new_id()}/url/").status_code == 401


def test_the_note_image_kind_is_registered_with_its_rules():
    spec = registry.get_kind("note_image")
    assert spec.bucket == "notes-private" and spec.scan == "none" and spec.flag == "notes"
    assert spec.mimes == {"image/png", "image/jpeg", "image/webp"} and "note_image" in registry.kind_names()
    with pytest.raises(registry.UnknownKind):
        registry.get_kind("nope")


def test_registering_a_different_spec_under_one_name_is_refused():
    spec = registry.get_kind("note_image")
    registry.register_kind(spec)  # the same spec twice is fine (ready() may run twice)
    other = registry.KindSpec(**{**spec.__dict__, "bucket": "elsewhere"})
    with pytest.raises(ValueError):
        registry.register_kind(other)


def test_reserve_complete_and_read(api, fake_storage):
    att = upload_image(api, fake_storage, put=False)
    assert att["status"] == "reserved" and QuotaUsage.objects.get().bytes_used == 1000
    path = Attachment.objects.get().path
    assert path.startswith("3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11/notes/images/") and path.endswith(".png")
    not_yet = api.post(f"/media/uploads/{att['id']}/complete/")
    assert not_yet.status_code == 409 and not_yet.json_body["error"]["code"] == "upload_missing"
    fake_storage.upload("notes-private", path, b"x", content_type="image/png", cache_control="")
    done = api.post(f"/media/uploads/{att['id']}/complete/")
    assert done.status_code == 200 and done.json_body["attachment"]["status"] == "clean"
    assert api.post(f"/media/uploads/{att['id']}/complete/").json_body["attachment"]["status"] == "clean"  # idempotent
    url = api.get(f"/media/attachments/{att['id']}/url/").json_body["url"]
    assert "object/sign/notes-private" in url


def test_type_size_and_unknown_kind_are_refused(api, fake_storage):
    assert (
        api.post("/media/uploads/", {"kind": "note_image", "mime": "application/pdf", "bytes": 10}).status_code == 415
    )
    big = api.post("/media/uploads/", {"kind": "note_image", "mime": "image/png", "bytes": 6 * 1024 * 1024})
    assert big.status_code == 413 and big.json_body["error"]["details"]["max_bytes"] == 5 * 1024 * 1024
    assert api.post("/media/uploads/", {"kind": "nope", "mime": "image/png", "bytes": 10}).status_code == 400
    assert api.post("/media/uploads/", {"kind": "note_image", "mime": "image/png", "bytes": 0}).status_code == 400
    assert not Attachment.objects.exists() and not QuotaUsage.objects.filter(bytes_used__gt=0).exists()


def test_storage_quota_is_enforced_atomically(api, fake_storage):
    upload_image(api, fake_storage, put=False)
    QuotaUsage.objects.update(bytes_used=500 * 1024 * 1024)
    res = api.post("/media/uploads/", {"kind": "note_image", "mime": "image/png", "bytes": 10})
    assert res.status_code == 429 and res.json_body["error"]["details"]["kind"] == "storage"
    assert Attachment.objects.count() == 1


def test_a_failed_signing_call_gives_the_quota_back(api, fake_storage):
    fake_storage.fail_signing = True
    res = api.post("/media/uploads/", {"kind": "note_image", "mime": "image/png", "bytes": 1000})
    assert res.status_code == 503 and res.json_body["error"]["code"] == "storage_unavailable"
    assert not Attachment.objects.exists()
    assert QuotaUsage.objects.filter(bytes_used__gt=0).count() == 0


def test_other_students_attachments_are_404(api, other_api, fake_storage):
    att = upload_image(api, fake_storage)
    api.post(f"/media/uploads/{att['id']}/complete/")
    assert other_api.post(f"/media/uploads/{att['id']}/complete/").status_code == 404
    assert other_api.get(f"/media/attachments/{att['id']}/url/").status_code == 404


def test_an_unfinished_upload_has_no_read_url(api, fake_storage):
    att = upload_image(api, fake_storage, put=False)
    res = api.get(f"/media/attachments/{att['id']}/url/")
    assert res.status_code == 409 and res.json_body["error"]["code"] == "attachment_not_ready"


def test_a_lapsed_reservation_cannot_be_completed(api, fake_storage):
    att = upload_image(api, fake_storage)
    Attachment.objects.update(expires_at=timezone.now() - timedelta(minutes=1))
    assert api.post(f"/media/uploads/{att['id']}/complete/").status_code == 409


def test_expiry_releases_quota_through_the_job_queue(api, fake_storage):
    upload_image(api, fake_storage, size=4000, put=False)
    Attachment.objects.update(expires_at=timezone.now() - timedelta(minutes=1))
    assert services.expire_reservations() == 1
    assert Attachment.objects.get().status == "deleting"
    assert jobs.run_pending(types=[services.JOB_DELETE]) == 1
    assert not Attachment.objects.exists() and QuotaUsage.objects.get().bytes_used == 0


def test_delete_job_is_idempotent_and_never_releases_twice(api, fake_storage):
    att = upload_image(api, fake_storage, size=4000)
    api.post(f"/media/uploads/{att['id']}/complete/")
    services.queue_delete([att["id"]])
    services.queue_delete([att["id"]])  # a second call queues no twin
    assert jobs.run_pending(types=[services.JOB_DELETE]) == 1
    assert services.run_delete_job({"attachment_id": att["id"]}) == {"deleted": False}
    assert QuotaUsage.objects.get().bytes_used == 0 and not fake_storage.objects


def test_a_storage_failure_retries_and_keeps_the_row(api, fake_storage):
    att = upload_image(api, fake_storage, size=100)
    api.post(f"/media/uploads/{att['id']}/complete/")
    services.queue_delete([att["id"]])
    fake_storage.fail_delete = True
    job = jobs.claim_next()
    assert jobs.run_job(job) == "queued" and Attachment.objects.count() == 1
    assert QuotaUsage.objects.get().bytes_used == 100
    fake_storage.fail_delete = False
    jobs.run_job(jobs.claim_next(now=timezone.now() + timedelta(hours=2)))
    assert not Attachment.objects.exists() and QuotaUsage.objects.get().bytes_used == 0


def test_a_deleting_attachment_is_not_served(api, fake_storage):
    att = upload_image(api, fake_storage)
    api.post(f"/media/uploads/{att['id']}/complete/")
    services.queue_delete([att["id"]])
    assert api.get(f"/media/attachments/{att['id']}/url/").status_code == 404


def test_delete_all_for_user_queues_everything(api, other_api, fake_storage):
    mine, theirs = upload_image(api, fake_storage), upload_image(other_api, fake_storage)
    out = services.delete_all_for_user(Attachment.objects.get(pk=mine["id"]).user_id)
    assert out == {"attachments": 1}
    assert Attachment.objects.get(pk=theirs["id"]).status == "reserved"


def test_the_notes_flag_gates_uploads(api, fake_storage, settings, monkeypatch):
    from core import feature_flags

    class Off:
        def get_feature_flag(self, key, distinct_id, **kwargs):
            return False if key == "notes" else None

    settings.POSTHOG_API_KEY = "phc_test"
    monkeypatch.setattr(feature_flags, "_client", Off())
    feature_flags.clear_flag_cache()
    res = api.post("/media/uploads/", {"kind": "note_image", "mime": "image/png", "bytes": 10})
    feature_flags.clear_flag_cache()
    assert res.status_code == 403 and res.json_body["error"]["code"] == "feature_disabled"


def test_the_export_lists_metadata_without_storage_paths(api, other_api, fake_storage):
    mine = upload_image(api, fake_storage)
    upload_image(other_api, fake_storage)
    out = services.export_for_user(Attachment.objects.get(pk=mine["id"]).user_id)
    assert [a["id"] for a in out["attachments"]] == [mine["id"]]
    assert not {"path", "bucket", "user_id"} & set(out["attachments"][0])
