import pytest
from django.test import Client

from modules.syllabus.models import Chapter, Course, Level, Subject
from modules.syllabus.tests.helpers import make_scheme

pytestmark = pytest.mark.django_db
BASE = "/api/v1/syllabus"


def test_courses_are_seeded_by_migration_and_public(client):
    res = client.get(f"{BASE}/courses/")
    assert res.status_code == 200
    body = res.json()
    assert [c["code"] for c in body] == ["ca", "cma", "cs"]
    ca = next(c for c in body if c["code"] == "ca")
    assert [lv["code"] for lv in ca["levels"]] == ["foundation", "intermediate", "final"]
    assert res["Cache-Control"] == "public, s-maxage=300, stale-while-revalidate=3600"


def test_public_endpoints_ignore_a_bad_bearer_token(client):
    res = client.get(f"{BASE}/courses/", HTTP_AUTHORIZATION="Bearer nonsense")
    assert res.status_code == 200


def test_level_without_published_scheme_is_empty_not_missing(client):
    res = client.get(f"{BASE}/courses/ca/levels/intermediate/")
    assert res.status_code == 200
    body = res.json()
    assert body["scheme"] is None and body["subjects"] == [] and body["groups"] == []
    assert body["course"]["institute_name"] == "ICAI"


def test_unknown_level_is_404(client):
    res = client.get(f"{BASE}/courses/ca/levels/nope/")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "not_found"


def test_draft_scheme_is_invisible_until_published(client):
    make_scheme(publish=False)
    assert client.get(f"{BASE}/courses/ca/levels/intermediate/").json()["scheme"] is None
    assert client.get(f"{BASE}/courses/ca/levels/intermediate/subjects/taxation/").status_code == 404


def test_published_level_lists_groups_and_subjects_in_order(client):
    make_scheme()
    body = client.get(f"{BASE}/courses/ca/levels/intermediate/").json()
    assert body["scheme"]["code"] == "2023"
    assert [g["key"] for g in body["groups"]] == ["group-1", "group-2"]
    assert [s["key"] for s in body["subjects"]] == ["taxation", "corporate-laws"]
    taxation = body["subjects"][0]
    assert taxation["group_key"] == "group-1" and taxation["chapter_count"] == 3


def test_subject_and_chapter_resolve_by_keys_and_ids(client):
    make_scheme()
    subject = client.get(f"{BASE}/courses/ca/levels/intermediate/subjects/taxation/").json()
    assert [c["key"] for c in subject["chapters"]] == ["gst-itc", "residential-status", "heads-of-income"]
    assert subject["chapters"][0]["marks_weight"] == 15.0  # (10 + 20) / 2
    assert subject["chapters"][1]["marks_weight"] == 5.0
    assert subject["chapters"][2]["marks_weight"] == 1.0  # no marks: weight 1

    by_id = client.get(f"{BASE}/subjects/{subject['id']}/").json()
    assert by_id["key"] == "taxation"

    chapter = client.get(f"{BASE}/courses/ca/levels/intermediate/subjects/taxation/chapters/gst-itc/").json()
    assert [t["key"] for t in chapter["topics"]] == ["eligibility", "blocked-credit", "reversal", "apportionment"]
    assert chapter["subject"]["key"] == "taxation" and chapter["course"] == "ca"
    assert client.get(f"{BASE}/chapters/{chapter['id']}/").json()["key"] == "gst-itc"


def test_unknown_subject_and_chapter_are_404(client):
    make_scheme()
    assert client.get(f"{BASE}/courses/ca/levels/intermediate/subjects/nope/").status_code == 404
    assert client.get(f"{BASE}/courses/ca/levels/intermediate/subjects/taxation/chapters/nope/").status_code == 404
    assert client.get(f"{BASE}/chapters/3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c99/").status_code == 404


def test_terms_are_filterable_by_course(client):
    body = client.get(f"{BASE}/terms/?course=cs").json()
    assert {t["course"] for t in body} == {"cs"}
    assert "2027-06" in [t["code"] for t in body]


def test_sitemap_paths_list_published_subjects_and_chapters(client):
    make_scheme()
    paths = client.get(f"{BASE}/sitemap/").json()["paths"]
    assert "/courses/ca/intermediate/taxation" in paths
    assert "/courses/ca/intermediate/taxation/gst-itc" in paths
    make_scheme(publish=False, code="draft-only")
    assert not any("draft-only" in p for p in client.get(f"{BASE}/sitemap/").json()["paths"])


def test_reports_accept_anonymous_and_signed_in(auth_client):
    make_scheme()
    chapter = Chapter.objects.get(key="gst-itc")
    body = {"node_type": "chapter", "node_id": str(chapter.id), "message": "Weightage looks wrong"}
    assert Client().post(f"{BASE}/reports/", data=body, content_type="application/json").status_code == 201
    res = auth_client.post(f"{BASE}/reports/", data=body, content_type="application/json")
    assert res.status_code == 201


def test_reports_validate_input(client):
    bad_node = {"node_type": "chapter", "node_id": "3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c99", "message": "does not exist"}
    res = client.post(f"{BASE}/reports/", data=bad_node, content_type="application/json")
    assert res.status_code == 400 and "node_id" in res.json()["error"]["details"]
    res = client.post(
        f"{BASE}/reports/", data={"node_type": "x", "node_id": "nope", "message": "hi"}, content_type="application/json"
    )
    assert res.status_code == 400


def test_models_use_expected_table_names():
    assert Course._meta.db_table == "syllabus_course"
    assert Level._meta.db_table == "syllabus_level"
    assert Subject._meta.db_table == "syllabus_subject"
    assert Chapter._meta.db_table == "syllabus_chapter"
