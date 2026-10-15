import uuid
from decimal import Decimal

import pytest

from modules.questionbank.selectors import (
    can_view,
    count_matching,
    facets,
    get_gradables,
    get_review_view,
    list_published,
    search_ids,
)
from modules.questionbank.services import (
    create_draft,
    create_share_link,
    publish_version,
    save_live,
)
from modules.questionbank.tests.conftest import EDITOR, USER

pytestmark = pytest.mark.django_db


def test_list_published_and_pagination():
    # Create 3 published questions
    for i in range(3):
        payload = {
            "kind": "mcq_single",
            "stem_md": f"Question {i + 1} text",
            "options": [
                {"body_md": "Opt A", "is_correct": True},
                {"body_md": "Opt B", "is_correct": False},
            ],
            "labels": {"difficulty": i + 1, "source_year": 2024},
        }
        q = create_draft(USER, payload)
        publish_version(EDITOR, q.current_version.id, visibility="public")

    page = list_published(None, {"scope": "public"}, limit=2)
    assert len(page.items) == 2
    assert page.next_cursor is not None

    page2 = list_published(None, {"scope": "public"}, cursor=page.next_cursor, limit=2)
    assert len(page2.items) == 1
    assert page2.next_cursor is None


def test_search_ids_order_and_seed():
    q_ids = []
    for i in range(5):
        payload = {
            "kind": "true_false",
            "stem_md": f"True or False Question {i + 1}",
            "options": [
                {"body_md": "True", "is_correct": True},
                {"body_md": "False", "is_correct": False},
            ],
        }
        q = create_draft(USER, payload)
        publish_version(EDITOR, q.current_version.id, visibility="public")
        q_ids.append(q.id)

    ids1 = search_ids(None, {"scope": "public"}, order="random", seed=42, limit=5)
    ids2 = search_ids(None, {"scope": "public"}, order="random", seed=42, limit=5)
    assert ids1 == ids2  # deterministic with same seed


def test_count_matching_and_facets():
    for diff in (1, 2, 2, 3):
        payload = {
            "kind": "true_false",
            "stem_md": f"Facet question diff {diff}",
            "options": [
                {"body_md": "True", "is_correct": True},
                {"body_md": "False", "is_correct": False},
            ],
            "labels": {"difficulty": diff, "source_year": 2024},
        }
        q = create_draft(USER, payload)
        publish_version(EDITOR, q.current_version.id, visibility="public")

    cnt = count_matching(None, {"scope": "public"}, cap=100)
    assert cnt == 4

    facet_res = facets(None, {"scope": "public"}, ["difficulty"])
    assert "difficulty" in facet_res
    diff_map = {fc.value: fc.count for fc in facet_res["difficulty"]}
    assert diff_map[2] == 2
    assert diff_map[1] == 1


def test_can_view_rules():
    payload = {
        "kind": "true_false",
        "stem_md": "Can view test stem",
        "options": [
            {"body_md": "True", "is_correct": True},
            {"body_md": "False", "is_correct": False},
        ],
    }
    q = create_draft(USER, payload)

    # 1. Private draft: owner can view, anonymous cannot, other user cannot
    assert can_view(USER, q.id) is True
    assert can_view(None, q.id) is False
    assert can_view(uuid.uuid4(), q.id) is False

    # 2. Saved as link: valid token allows viewing
    save_live(USER, q.id, "link")
    link = create_share_link(USER, question_id=q.id)
    assert can_view(None, q.id, token=link.token) is True
    assert can_view(None, q.id, token="invalid-token") is False

    # 3. Public active question: anyone can view
    publish_version(EDITOR, q.current_version.id, visibility="public")
    assert can_view(None, q.id) is True


def test_get_gradables_and_get_review_view():
    payload = {
        "kind": "mcq_single",
        "stem_md": "What is Section 16 of CGST Act?",
        "explanation_md": "Section 16 specifies the eligibility and conditions for taking input tax credit.",
        "options": [
            {"body_md": "Eligibility for ITC", "is_correct": True, "feedback_md": "Correct provision"},
            {"body_md": "Time of supply", "is_correct": False, "feedback_md": "Section 12/13"},
        ],
        "marks": Decimal("1.0"),
    }
    q = create_draft(USER, payload)
    ver = publish_version(EDITOR, q.current_version.id, visibility="public")

    # Gradables
    gradables = get_gradables([(q.id, ver.id)])
    assert q.id in gradables
    g = gradables[q.id]
    assert len(g.correct_option_ids) == 1
    assert g.marks == Decimal("1.0")

    # Review View
    review = get_review_view(q.id, ver.id)
    assert review.explanation_md == payload["explanation_md"]
    assert len(review.options) == 2
    assert any(opt["is_correct"] for opt in review.options)
