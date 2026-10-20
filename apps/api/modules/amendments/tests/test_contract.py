"""
Automated API contract and privacy leak test for F-14 Amendments (Wave 3).
Verifies that `docs/F-14-API-CONTRACT.md` and the actual Django routes, throttle scopes,
payload keys, error shapes, and privacy leak guards stay 100% in sync.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

import pytest
from django.utils import timezone

from core import feature_flags
from modules.amendments import urls
from modules.amendments.models import CardState
from modules.amendments.services import (
    create_amendment_draft,
    release_revision,
    set_revision_scope,
    stage_change_card,
)
from modules.coverage.services import create_enrollment
from modules.syllabus.tests.helpers import make_scheme

pytestmark = pytest.mark.django_db

DOC_PATH = Path(__file__).resolve().parents[5] / "docs" / "F-14-API-CONTRACT.md"
USER_ID = uuid.UUID("3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11")


@pytest.fixture(scope="module")
def doc() -> str:
    assert DOC_PATH.exists(), f"Contract documentation missing at {DOC_PATH}"
    return DOC_PATH.read_text()


def extract_section(doc: str, name: str) -> str:
    match = re.search(rf"<!-- contract:{name} -->\n(.*?)\n<!-- /contract:{name} -->", doc, re.S) or re.search(
        rf"<!-- contract:{name} -->\n(.*?)\n<!--", doc, re.S
    )
    assert match, f"Missing <!-- contract:{name} --> block in contract doc"
    return match.group(1).strip()


def extract_keys(doc: str, name: str) -> set[str]:
    section_name = name if (":" in name or "forbidden" in name) else f"keys:{name}"
    return {k.strip() for k in extract_section(doc, section_name).split(",") if k.strip()}


def extract_endpoint_rows(doc: str) -> list[list[str]]:
    return [
        [cell.strip().strip("`") for cell in line.strip("|").split("|")]
        for line in extract_section(doc, "endpoints").splitlines()
        if line.startswith("|") and not set(line) <= set("| -")
    ][1:]


def implemented_endpoints() -> dict[tuple[str, str], type]:
    found = {}
    for pattern in urls.urlpatterns:
        view = pattern.callback.view_class
        for method in ("get", "post", "put", "patch", "delete"):
            if hasattr(view, method):
                found[(method.upper(), str(pattern.pattern))] = view
    return found


# ---------------------------------------------------------------------------
# Route and Throttle Drift Tests
# ---------------------------------------------------------------------------


def test_the_endpoint_table_lists_exactly_the_implemented_endpoints(doc):
    documented = {(method, path) for method, path, *_ in extract_endpoint_rows(doc)}
    implemented = set(implemented_endpoints().keys())
    assert documented == implemented, f"Contract drift! Diff: {documented ^ implemented}"


def test_each_endpoint_documents_its_throttle_scope(doc):
    for method, path, _purpose, scope in extract_endpoint_rows(doc):
        view = implemented_endpoints()[(method, path)]
        actual_scope = getattr(view, "throttle_scope", "none") or "none"
        assert actual_scope == scope, f"{method} {path} expected scope '{scope}', got '{actual_scope}'"


def test_throttle_rates_exist_in_settings(doc, settings):
    rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    for _method, _path, _purpose, scope in extract_endpoint_rows(doc):
        if scope != "none":
            assert scope in rates, f"Throttle scope '{scope}' not configured in DEFAULT_THROTTLE_RATES"


# ---------------------------------------------------------------------------
# Fixture: Live Seeded Amendment and Enrolled Student
# ---------------------------------------------------------------------------


@pytest.fixture
def live_amendment_data(db):
    scheme = make_scheme()
    course = scheme.level.course
    level = scheme.level
    subject = scheme.subjects.get(key="taxation")
    chapter = subject.chapters.get(key="gst-itc")

    amendment, revision = create_amendment_draft(
        course_id=course.id,
        level_id=level.id,
        title="Statutory Update Taxation May 2027",
        doc_key="statutory_update:tax:2027-05",
        official_url="https://example.org/statutory_update.pdf",
    )

    set_revision_scope(
        revision_id=revision.id,
        subjects=[
            {
                "subject_id": subject.id,
                "subject_key": subject.key,
                "scheme_id": scheme.id,
                "level_id": level.id,
            }
        ],
        terms=[
            {
                "term_code": "2027-05",
                "applicability": "applies",
                "cutoff_date": timezone.now().date(),
                "cutoff_note": "Notifications issued up to 31 Oct",
                "source_page": 2,
            }
        ],
    )

    card = stage_change_card(
        revision_id=revision.id,
        title="Input Tax Credit on Motor Vehicles",
        provision_label="Section 17(5)(a)",
        change_type="modification",
        summary_new="ITC is blocked on motor vehicles with seating capacity up to 13 persons.",
        summary_old="ITC was generally allowed on commercial vehicles.",
        effective_text="Applicable from May 2027",
        law_key="cgst",
        provision_keys=["cgst:17(5)"],
        effective_from_term_code="2027-05",
        materiality="high",
        source_page=12,
        anchor={"page": 12, "precision": "quote"},
        evidence_quote="Section 17(5)(a) is modified to block input tax credit...",
        mappings=[
            {
                "subject_id": subject.id,
                "chapter_id": chapter.id,
                "scheme_id": scheme.id,
                "subject_key": subject.key,
                "chapter_key": chapter.key,
                "is_primary": True,
            }
        ],
    )

    release_revision(revision_id=revision.id)

    # Student enrollment
    create_enrollment(
        user_id=USER_ID,
        scheme_id=scheme.id,
        exam_date=timezone.now().date(),
        daily_minutes=120,
    )

    return {
        "scheme": scheme,
        "course": course,
        "level": level,
        "subject": subject,
        "chapter": chapter,
        "amendment": amendment,
        "revision": revision,
        "card": card,
    }


# ---------------------------------------------------------------------------
# Security & Feature Flag Tests
# ---------------------------------------------------------------------------


def test_student_endpoints_require_authentication(client):
    res = client.get("/api/v1/amendments/me/summary/")
    assert res.status_code == 401

    res = client.post("/api/v1/amendments/cards/somecard/reviewed/", data={})
    assert res.status_code == 401


def test_student_endpoints_fail_closed_when_feature_flag_disabled(auth_client, live_amendment_data, monkeypatch):
    monkeypatch.setattr(feature_flags, "flag_enabled", lambda *args, **kwargs: False)

    res = auth_client.get("/api/v1/amendments/me/summary/")
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "feature_disabled"

    res = auth_client.post(
        f"/api/v1/amendments/cards/{live_amendment_data['card'].change.public_id}/reviewed/",
        data={"reviewed": True},
        content_type="application/json",
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "feature_disabled"


def test_dpdp_export_and_delete_allowed_even_when_flag_disabled(auth_client, live_amendment_data, monkeypatch):
    monkeypatch.setattr(feature_flags, "flag_enabled", lambda *args, **kwargs: False)

    # Export
    res = auth_client.get("/api/v1/amendments/me/export/")
    assert res.status_code == 200
    assert "amendments_card_states" in res.json()

    # Delete
    res = auth_client.delete("/api/v1/amendments/me/data/")
    assert res.status_code == 200
    assert "card_states_deleted" in res.json()


def test_public_endpoints_accessible_without_auth_and_without_flag(client, live_amendment_data, monkeypatch):
    monkeypatch.setattr(feature_flags, "flag_enabled", lambda *args, **kwargs: False)

    res = client.get("/api/v1/amendments/public/hub/")
    assert res.status_code == 200
    assert "documents" in res.json()


# ---------------------------------------------------------------------------
# Payload Contract and Privacy Leak Assertion Tests
# ---------------------------------------------------------------------------


def test_my_summary_keys_match_contract(doc, auth_client, live_amendment_data):
    res = auth_client.get("/api/v1/amendments/me/summary/")
    assert res.status_code == 200
    data = res.json()
    expected_keys = extract_keys(doc, "my_summary")
    assert set(data.keys()) == expected_keys


def test_my_cards_keys_match_contract(doc, auth_client, live_amendment_data):
    res = auth_client.get("/api/v1/amendments/me/cards/")
    assert res.status_code == 200
    data = res.json()
    assert data["total_count"] >= 1
    card = data["cards"][0]
    expected_keys = extract_keys(doc, "my_card")
    assert set(card.keys()) == expected_keys


def test_public_card_keys_and_privacy_leak_assertion(doc, client, live_amendment_data):
    public_id = live_amendment_data["card"].change.public_id
    res = client.get(f"/api/v1/amendments/public/cards/{public_id}/")
    assert res.status_code == 200
    data = res.json()

    expected_keys = extract_keys(doc, "public_card")
    assert set(data.keys()) == expected_keys

    forbidden = extract_keys(doc, "forbidden_public_fields")
    # Verify recursively that NO forbidden field exists in the public card payload
    raw_text = res.content.decode("utf-8")
    for f in forbidden:
        assert f'"{f}"' not in raw_text, f"CRITICAL LEAK: forbidden field '{f}' leaked in public response!"


def test_public_document_keys_match_contract(doc, client, live_amendment_data):
    slug = live_amendment_data["amendment"].slug
    res = client.get(f"/api/v1/amendments/public/documents/{slug}/")
    assert res.status_code == 200
    data = res.json()

    expected_keys = extract_keys(doc, "public_document")
    assert set(data.keys()) == expected_keys

    forbidden = extract_keys(doc, "forbidden_public_fields")
    raw_text = res.content.decode("utf-8")
    for f in forbidden:
        assert f'"{f}"' not in raw_text, f"CRITICAL LEAK: forbidden field '{f}' leaked in public document response!"


def test_card_state_mutations_and_sync(auth_client, live_amendment_data):
    public_id = live_amendment_data["card"].change.public_id

    # Mark reviewed
    res = auth_client.post(
        f"/api/v1/amendments/cards/{public_id}/reviewed/",
        data={"reviewed": True},
        content_type="application/json",
    )
    assert res.status_code == 200
    assert res.json()["reviewed"] is True

    # Check state in database
    cs = CardState.objects.get(user_id=USER_ID, change__public_id=public_id)
    assert cs.reviewed_at is not None

    # Mark saved
    res = auth_client.post(
        f"/api/v1/amendments/cards/{public_id}/saved/",
        data={"saved": True},
        content_type="application/json",
    )
    assert res.status_code == 200
    assert res.json()["saved"] is True

    cs.refresh_from_db()
    assert cs.saved is True

    # Bulk reviewed
    res = auth_client.post(
        "/api/v1/amendments/cards/bulk-reviewed/",
        data={"public_ids": [public_id], "reviewed": False},
        content_type="application/json",
    )
    assert res.status_code == 200
    assert res.json()["updated"] == 1
    assert res.json()["reviewed"] is False

    cs.refresh_from_db()
    assert cs.reviewed_at is None
