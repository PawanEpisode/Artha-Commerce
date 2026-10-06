"""FR-N16: the queue signature and the cron secret. Wrong or missing means 401 and nothing happens."""

import base64
import hashlib
import time
import uuid

import jwt
import pytest

from modules.notifications.domain.enums import JobStatus
from modules.notifications.models import ScheduledJob
from modules.notifications.scheduling import queue

pytestmark = pytest.mark.django_db
BASE = "/api/v1/notifications/internal"
CURRENT, NEXT = "current-signing-key-0123456789", "next-signing-key-0123456789"
SECRET = "cron-secret-value-0123456789"


@pytest.fixture(autouse=True)
def _keys(settings):
    settings.QSTASH_CURRENT_SIGNING_KEY, settings.QSTASH_NEXT_SIGNING_KEY = CURRENT, NEXT
    settings.CRON_SECRET = SECRET


def sign(body: str, *, job_id, key=CURRENT, url=None, expires_in=300, subject=None) -> str:
    """The `Upstash-Signature` JWT QStash sends: HS256, issuer Upstash, subject = callback URL, body = sha256 of body."""
    digest = base64.urlsafe_b64encode(hashlib.sha256(body.encode()).digest()).decode().rstrip("=")
    now = int(time.time())
    claims = {
        "iss": "Upstash",
        "sub": subject or url or queue.fire_callback_url(job_id),
        "exp": now + expires_in,
        "nbf": now - 1,
        "iat": now,
        "jti": uuid.uuid4().hex,
        "body": digest,
    }
    return jwt.encode(claims, key, algorithm="HS256")


def fire(client, job_id, body='{"job_id": "x"}', **headers):
    return client.post(f"{BASE}/jobs/{job_id}/fire/", body, content_type="application/json", **headers)


def pending_job():
    return ScheduledJob.objects.create(
        user_id=uuid.uuid4(),
        kind="timer_end",
        subject_key=str(uuid.uuid4()),
        expected_version=1,
        fire_at="2026-10-05T04:55Z",
    )


def untouched(job):
    job.refresh_from_db()
    return job.status == JobStatus.PENDING and job.attempts == 0


def test_a_valid_signature_with_the_current_key_is_accepted(client):
    job = pending_job()
    body = f'{{"job_id": "{job.id}"}}'
    r = fire(client, job.id, body, HTTP_UPSTASH_SIGNATURE=sign(body, job_id=job.id))
    assert r.status_code == 200
    job.refresh_from_db()
    assert job.status != JobStatus.PENDING  # it was claimed and judged


def test_a_key_rotation_is_survived_the_next_key_is_accepted_too(client):
    job = pending_job()
    body = "{}"
    r = fire(client, job.id, body, HTTP_UPSTASH_SIGNATURE=sign(body, job_id=job.id, key=NEXT))
    assert r.status_code == 200


@pytest.mark.parametrize(
    "case",
    ["wrong_key", "expired", "other_url", "tampered_body", "garbage", "none_algorithm"],
)
def test_a_bad_signature_is_401_and_the_job_is_untouched(client, case):
    job = pending_job()
    body = '{"job_id": "x"}'
    signature = {
        "wrong_key": lambda: sign(body, job_id=job.id, key="someone-elses-key-0123456789"),
        "expired": lambda: sign(body, job_id=job.id, expires_in=-3600),
        "other_url": lambda: sign(body, job_id=job.id, url="https://evil.example.test/fire/"),
        "tampered_body": lambda: sign('{"job_id": "y"}', job_id=job.id),
        "garbage": lambda: "not-a-jwt",
        "none_algorithm": lambda: jwt.encode({"iss": "Upstash", "sub": "x"}, None, algorithm="none"),
    }[case]()
    r = fire(client, job.id, body, HTTP_UPSTASH_SIGNATURE=signature)
    assert r.status_code == 401 and r.json()["error"]["code"] == "unauthorized"
    assert untouched(job)


def test_a_signature_for_another_job_does_not_fire_this_one(client):
    job, other = pending_job(), pending_job()
    body = "{}"
    r = fire(client, job.id, body, HTTP_UPSTASH_SIGNATURE=sign(body, job_id=other.id))
    assert r.status_code == 401 and untouched(job) and untouched(other)


def test_a_missing_signature_is_401(client):
    job = pending_job()
    assert fire(client, job.id).status_code == 401 and untouched(job)


def test_without_signing_keys_nothing_can_be_verified_so_everything_is_refused(client, settings):
    settings.QSTASH_CURRENT_SIGNING_KEY = settings.QSTASH_NEXT_SIGNING_KEY = ""
    job = pending_job()
    body = "{}"
    assert fire(client, job.id, body, HTTP_UPSTASH_SIGNATURE=sign(body, job_id=job.id)).status_code == 401


def test_the_fire_endpoint_takes_no_student_credentials(client, make_token):
    job = pending_job()
    r = fire(client, job.id, HTTP_AUTHORIZATION=f"Bearer {make_token()}")  # a student token is not a queue signature
    assert r.status_code == 401 and untouched(job)


def test_the_fire_endpoint_is_post_only(client):
    assert client.get(f"{BASE}/jobs/{uuid.uuid4()}/fire/").status_code == 405


# --- the cron secret ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("method", ["get", "post"])
def test_the_sweep_accepts_the_cron_secret_on_get_and_post(client, method):
    r = getattr(client, method)(f"{BASE}/sweep/", HTTP_AUTHORIZATION=f"Bearer {SECRET}")
    assert r.status_code == 200 and r.json() == {"fired": 0, "skipped": 0, "failed": 0, "more": False}


@pytest.mark.parametrize(
    "header",
    [None, "", "Bearer ", f"Bearer {SECRET}x", f"Bearer {SECRET[:-1]}", "Bearer wrong", SECRET, f"Basic {SECRET}"],
)
def test_the_sweep_refuses_anything_else(client, header):
    extra = {} if header is None else {"HTTP_AUTHORIZATION": header}
    for method in ("get", "post"):
        r = getattr(client, method)(f"{BASE}/sweep/", **extra)
        assert r.status_code == 401 and r.json()["error"]["code"] == "unauthorized"


def test_the_sweep_is_closed_when_no_secret_is_configured(client, settings):
    settings.CRON_SECRET = ""
    assert client.post(f"{BASE}/sweep/", HTTP_AUTHORIZATION="Bearer ").status_code == 401
    assert client.post(f"{BASE}/sweep/").status_code == 401


def test_the_secret_is_compared_in_constant_time(monkeypatch):
    import hmac

    from modules.notifications.scheduling import auth

    seen = []
    real = hmac.compare_digest
    monkeypatch.setattr(hmac, "compare_digest", lambda a, b: seen.append((len(a), len(b))) or real(a, b))
    assert auth._same("short", SECRET) is False
    assert seen == [(32, 32)]  # digests of equal length, so neither the length nor the content shows in timing


def test_a_queue_signature_is_not_a_cron_secret_and_the_other_way_round(client):
    job = pending_job()
    body = "{}"
    sig = sign(body, job_id=job.id)
    assert client.post(f"{BASE}/sweep/", HTTP_AUTHORIZATION=f"Bearer {sig}").status_code == 401
    assert fire(client, job.id, body, HTTP_UPSTASH_SIGNATURE=SECRET).status_code == 401


# --- outside the student surface ----------------------------------------------------------------------------------


def test_internal_endpoints_ignore_the_ui_gate_and_the_kill_switches_still_apply_inside_the_job(
    client, settings, monkeypatch
):
    settings.NOTIFICATIONS_ENABLED = False  # the student endpoints would answer 403 here
    monkeypatch.setattr("modules.notifications.flags.flag_enabled", lambda *a, **k: False)
    job = pending_job()
    body = "{}"
    r = fire(client, job.id, body, HTTP_UPSTASH_SIGNATURE=sign(body, job_id=job.id))
    assert r.status_code == 200 and r.json()["status"] == "skipped" and r.json()["reason"] == "disabled"
    assert client.post(f"{BASE}/sweep/", HTTP_AUTHORIZATION=f"Bearer {SECRET}").status_code == 200


def test_internal_endpoints_are_outside_cors(client, settings):
    settings.CORS_ALLOWED_ORIGINS = ["https://app.example.test"]
    origin = {"HTTP_ORIGIN": "https://app.example.test"}
    control = client.get("/api/v1/notifications/settings/", **origin)  # a student endpoint does carry the CORS header
    assert control.headers["access-control-allow-origin"] == "https://app.example.test"
    internal = client.post(f"{BASE}/sweep/", HTTP_AUTHORIZATION=f"Bearer {SECRET}", **origin)
    assert "access-control-allow-origin" not in {h.lower() for h in internal.headers}
    preflight = client.options(f"{BASE}/sweep/", HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST", **origin)
    assert "access-control-allow-origin" not in {h.lower() for h in preflight.headers}


def test_the_cors_exclusion_is_only_for_the_internal_path():
    import re

    from django.conf import settings

    pattern = re.compile(settings.CORS_URLS_REGEX)
    assert not pattern.match("/api/v1/notifications/internal/sweep/")
    assert not pattern.match(f"/api/v1/notifications/internal/jobs/{uuid.uuid4()}/fire/")
    for path in ("/api/v1/notifications/settings/", "/api/v1/focus/timer/", "/api/v1/notifications/devices/"):
        assert pattern.match(path)
