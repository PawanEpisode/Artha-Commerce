import pytest

from modules.questionbank.services import create_draft, publish_version
from modules.questionbank.tests.conftest import EDITOR, USER

pytestmark = pytest.mark.django_db


def test_public_questions_endpoint(client, qb_flag, db):
    payload = {
        "kind": "mcq_single",
        "stem_md": "Public question stem",
        "options": [
            {"body_md": "A", "is_correct": True},
            {"body_md": "B", "is_correct": False},
        ],
    }
    q = create_draft(USER, payload)
    publish_version(EDITOR, q.current_version.id, visibility="public")

    res = client.get("/api/v1/questionbank/public/questions/")
    assert res.status_code == 200
    assert "public, s-maxage=300" in res.headers["Cache-Control"]
    assert "ETag" in res.headers

    body = res.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == str(q.id)


def test_public_question_detail(client, qb_flag, db):
    payload = {
        "kind": "mcq_single",
        "stem_md": "Detail question stem",
        "options": [
            {"body_md": "A", "is_correct": True},
            {"body_md": "B", "is_correct": False},
        ],
    }
    q = create_draft(USER, payload)
    publish_version(EDITOR, q.current_version.id, visibility="public")

    res = client.get(f"/api/v1/questionbank/public/questions/{q.id}/")
    assert res.status_code == 200
    data = res.json()
    assert data["question_id"] == str(q.id)
    # Never leaks answers
    for opt in data["options"]:
        assert "is_correct" not in opt


def test_public_facets_endpoint(client, qb_flag, db):
    payload = {
        "kind": "true_false",
        "stem_md": "True or false facet test",
        "options": [
            {"body_md": "True", "is_correct": True},
            {"body_md": "False", "is_correct": False},
        ],
        "labels": {"difficulty": 3},
    }
    q = create_draft(USER, payload)
    publish_version(EDITOR, q.current_version.id, visibility="public")

    res = client.get("/api/v1/questionbank/public/facets/?dims=kind,difficulty")
    assert res.status_code == 200
    data = res.json()
    assert "kind" in data
    assert "difficulty" in data


def test_create_draft_view(api):
    body = {
        "kind": "mcq_single",
        "stem_md": "What is Section 7 of CGST Act?",
        "options": [
            {"body_md": "Scope of supply", "is_correct": True},
            {"body_md": "Levy", "is_correct": False},
        ],
        "marks": "1.0",
    }
    res = api.post("/questionbank/questions/", body)
    assert res.status_code == 201
    assert "question_id" in res.json_body
    assert res.json_body["status"] == "active"
    assert res.json_body["visibility"] == "private"


def test_save_live_view(api):
    payload = {
        "kind": "mcq_single",
        "stem_md": "What is Section 8 of CGST Act?",
        "options": [
            {"body_md": "Composite and mixed supply", "is_correct": True},
            {"body_md": "Exemption", "is_correct": False},
        ],
    }
    q = create_draft(USER, payload)

    res = api.put(f"/questionbank/questions/{q.id}/live/", {"visibility": "link"})
    assert res.status_code == 200
    assert res.json_body["state"] == "live"


def test_playable_and_review_views(api):
    payload = {
        "kind": "mcq_single",
        "stem_md": "Test playable and review stem",
        "explanation_md": "Detailed explanation that exceeds sixty characters for compliance with public MCQ rules.",
        "options": [
            {"body_md": "Option 1", "is_correct": True, "feedback_md": "Great!"},
            {"body_md": "Option 2", "is_correct": False, "feedback_md": "Wrong"},
        ],
    }
    q = create_draft(USER, payload)
    publish_version(EDITOR, q.current_version.id, visibility="public")

    # Playable: No keys
    play_res = api.get(f"/questionbank/questions/{q.id}/playable/")
    assert play_res.status_code == 200
    for opt in play_res.json_body["options"]:
        assert "is_correct" not in opt
        assert "feedback_md" not in opt

    # Review: Has keys and explanations
    rev_res = api.get(f"/questionbank/questions/{q.id}/review/")
    assert rev_res.status_code == 200
    assert "correct_option_ids" in rev_res.json_body
    assert rev_res.json_body["explanation_md"] == payload["explanation_md"]


def test_submit_review_view(api):
    payload = {
        "kind": "mcq_single",
        "stem_md": "Submit review stem",
        "explanation_md": "Detailed explanation that is definitely longer than sixty characters for public MCQs.",
        "options": [
            {"body_md": "Option 1", "is_correct": True},
            {"body_md": "Option 2", "is_correct": False},
        ],
    }
    q = create_draft(USER, payload)

    res = api.post(f"/questionbank/questions/{q.id}/review/")
    assert res.status_code == 200
    assert res.json_body["status"] == "pending"


def test_report_error_view(api):
    payload = {
        "kind": "true_false",
        "stem_md": "True or false for report view",
        "options": [
            {"body_md": "True", "is_correct": True},
            {"body_md": "False", "is_correct": False},
        ],
    }
    q = create_draft(USER, payload)
    ver = publish_version(EDITOR, q.current_version.id, visibility="public")

    res = api.post(
        f"/questionbank/questions/{q.id}/report/",
        {"version_id": str(ver.id), "kind": "typo", "message": "Typo in stem"},
    )
    assert res.status_code == 200
    assert "report_id" in res.json_body


def test_editor_endpoints(editor_api):
    payload = {
        "kind": "true_false",
        "stem_md": "True or false for editor endpoints",
        "options": [
            {"body_md": "True", "is_correct": True},
            {"body_md": "False", "is_correct": False},
        ],
    }
    q1 = create_draft(USER, payload)
    q2 = create_draft(USER, payload)
    ver1 = q1.current_version

    # Verify
    v_res = editor_api.post(
        "/questionbank/editor/verify/",
        {
            "version_id": str(ver1.id),
            "level": "editor",
            "source_label": "ICAI Module 2024",
            "source_url": "https://icai.org",
        },
    )
    assert v_res.status_code == 200

    # Publish
    p_res = editor_api.post(
        f"/questionbank/editor/versions/{ver1.id}/publish/",
        {"visibility": "public"},
    )
    assert p_res.status_code == 200

    # Merge duplicate
    m_res = editor_api.post(
        "/questionbank/editor/merge/",
        {"loser_id": str(q2.id), "canonical_id": str(q1.id)},
    )
    assert m_res.status_code == 200
    assert m_res.json_body["status"] == "merged"


def test_feature_flag_fail_closed(api, qb_flag):
    qb_flag(False)  # Turn flag off
    res = api.get("/questionbank/public/questions/")
    assert res.status_code == 404
