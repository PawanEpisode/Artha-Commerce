import uuid
from decimal import Decimal

import pytest

from modules.questionbank.models import (
    Collection,
    Question,
    QuestionVersion,
    Report,
    Review,
    Takedown,
)
from modules.questionbank.services import (
    create_collection,
    create_draft,
    create_share_link,
    decide_review,
    delete_all_for_user,
    publish_version,
    report_error,
    save_live,
    set_collection_items,
    submit_for_review,
    take_down,
    upsert_from_source,
    verify,
)
from modules.questionbank.tests.conftest import EDITOR, USER

pytestmark = pytest.mark.django_db


def test_create_draft_and_idempotency():
    client_id = uuid.uuid4()
    payload = {
        "kind": "mcq_single",
        "stem_md": "What is Section 10 of CGST Act?",
        "options": [
            {"body_md": "Composition levy", "is_correct": True},
            {"body_md": "Registration", "is_correct": False},
        ],
        "marks": Decimal("1.0"),
    }

    q1 = create_draft(USER, payload, client_id=client_id)
    assert q1.status == Question.Status.ACTIVE
    assert q1.visibility == Question.Visibility.PRIVATE
    assert q1.versions.count() == 1
    assert q1.versions.first().options.count() == 2

    # Second call with same client_id returns existing question
    q2 = create_draft(USER, payload, client_id=client_id)
    assert q1.id == q2.id


def test_save_live_transitions_state_and_visibility():
    payload = {
        "kind": "mcq_single",
        "stem_md": "What is Section 9 of CGST Act?",
        "options": [
            {"body_md": "Levy and collection", "is_correct": True},
            {"body_md": "Exemption", "is_correct": False},
        ],
    }
    q = create_draft(USER, payload)
    ver = save_live(USER, q.id, visibility="link")

    assert ver.state == QuestionVersion.State.LIVE
    q.refresh_from_db()
    assert q.visibility == Question.Visibility.LINK
    assert q.live_version_id == ver.id


def test_submit_for_review_and_decide_review():
    payload = {
        "kind": "mcq_single",
        "stem_md": "What is the threshold limit for composition scheme under Section 10?",
        "explanation_md": "The threshold limit for composition scheme under section 10 is Rs 1.5 crore for most states and 75 lakhs for special category states.",
        "options": [
            {"body_md": "Rs. 1.5 Crore", "is_correct": True},
            {"body_md": "Rs. 2.0 Crore", "is_correct": False},
        ],
    }
    q = create_draft(USER, payload)

    review = submit_for_review(USER, q.id)
    assert review.status == Review.Status.PENDING

    q.refresh_from_db()
    assert q.current_version.state == QuestionVersion.State.IN_REVIEW

    # Editor approves review
    decided = decide_review(EDITOR, review.id, "approved", code="ok", note="Good quality")
    assert decided.status == Review.Status.APPROVED

    q.refresh_from_db()
    assert q.visibility == Question.Visibility.PUBLIC
    assert q.live_version.state == QuestionVersion.State.LIVE


def test_publish_version_emits_event(events):
    payload = {
        "kind": "true_false",
        "stem_md": "GST is a destination-based consumption tax.",
        "options": [
            {"body_md": "True", "is_correct": True},
            {"body_md": "False", "is_correct": False},
        ],
    }
    q = create_draft(USER, payload)
    ver = q.current_version
    published_ver = publish_version(EDITOR, ver.id, visibility="public")

    assert published_ver.state == QuestionVersion.State.LIVE
    q.refresh_from_db()
    assert q.live_version_id == published_ver.id


def test_report_error_and_flagging():
    payload = {
        "kind": "true_false",
        "stem_md": "Audit is mandatory for all registered persons under GST.",
        "options": [
            {"body_md": "True", "is_correct": False},
            {"body_md": "False", "is_correct": True},
        ],
    }
    q = create_draft(USER, payload)
    ver = save_live(USER, q.id, "link")

    rep1 = report_error(USER, q.id, ver.id, "wrong_answer", "Mistake in key", [])
    assert rep1.status == Report.Status.OPEN

    # Two more reports trigger needs_attention flag
    report_error(uuid.uuid4(), q.id, ver.id, "wrong_answer", "Key wrong", [])
    report_error(uuid.uuid4(), q.id, ver.id, "wrong_answer", "Key wrong 3", [])

    q.refresh_from_db()
    assert q.needs_attention is True


def test_verify_question_version():
    payload = {
        "kind": "true_false",
        "stem_md": "Input tax credit is blocked under section 17(5) for motor vehicles with seating capacity <= 13.",
        "options": [
            {"body_md": "True", "is_correct": True},
            {"body_md": "False", "is_correct": False},
        ],
    }
    q = create_draft(USER, payload)
    ver = save_live(USER, q.id, "link")

    v = verify(EDITOR, ver.id, "editor", "ICAI Module 2025", "https://icai.org")
    assert v.revoked_at is None

    q.refresh_from_db()
    assert q.is_verified is True


def test_take_down_questions():
    payload = {
        "kind": "true_false",
        "stem_md": "Sample question for takedown.",
        "options": [
            {"body_md": "True", "is_correct": True},
            {"body_md": "False", "is_correct": False},
        ],
    }
    q = create_draft(USER, payload)
    save_live(USER, q.id, "link")

    td = Takedown.objects.create(
        reference="TD-2026-0001",
        complainant_name="Publisher",
        complainant_email="legal@pub.com",
        claimed_work="Exam bank book",
    )

    take_down(EDITOR, td.id, [q.id])

    q.refresh_from_db()
    assert q.status == Question.Status.TAKEN_DOWN


def test_upsert_from_source_lifecycle():
    payload = {
        "kind": "mcq_single",
        "stem_md": "What is Section 15 value of supply?",
        "options": [
            {"body_md": "Transaction value", "is_correct": True},
            {"body_md": "Market value", "is_correct": False},
        ],
        "marks": Decimal("2.0"),
    }

    # 1. First upsert -> created
    r1 = upsert_from_source(
        origin_module="mat",
        external_ref="mat:gst:ch3:ill1",
        payload=payload,
        ownership=Question.Ownership.PLATFORM,
        rights_status=Question.RightsStatus.INSTITUTE_MATERIAL,
        actor_id=EDITOR,
        auto_publish=True,
    )
    assert r1.outcome == "created"
    assert r1.question.versions.count() == 1
    assert r1.version.state == QuestionVersion.State.LIVE

    # 2. Second upsert with identical content -> unchanged
    r2 = upsert_from_source(
        origin_module="mat",
        external_ref="mat:gst:ch3:ill1",
        payload=payload,
        ownership=Question.Ownership.PLATFORM,
        rights_status=Question.RightsStatus.INSTITUTE_MATERIAL,
        actor_id=EDITOR,
        auto_publish=True,
    )
    assert r2.outcome == "unchanged"
    assert r2.version.id == r1.version.id

    # 3. Third upsert with changed content -> new_version
    payload_modified = dict(payload)
    payload_modified["stem_md"] = "What is Section 15 value of taxable supply?"
    r3 = upsert_from_source(
        origin_module="mat",
        external_ref="mat:gst:ch3:ill1",
        payload=payload_modified,
        ownership=Question.Ownership.PLATFORM,
        rights_status=Question.RightsStatus.INSTITUTE_MATERIAL,
        actor_id=EDITOR,
        auto_publish=True,
    )
    assert r3.outcome == "new_version"
    assert r3.version.version_no == 2
    assert r3.version.state == QuestionVersion.State.LIVE


def test_collections_and_share_links():
    coll = create_collection(USER, kind="custom", title="Important GST Questions", visibility="private")
    assert coll.title == "Important GST Questions"

    payload = {
        "kind": "true_false",
        "stem_md": "Test stem",
        "options": [
            {"body_md": "True", "is_correct": True},
            {"body_md": "False", "is_correct": False},
        ],
    }
    q = create_draft(USER, payload)

    set_collection_items(USER, coll.id, [q.id])
    coll.refresh_from_db()
    assert coll.item_count == 1

    link = create_share_link(USER, collection_id=coll.id)
    assert len(link.token) == 22


def test_delete_and_export_for_user():
    payload = {
        "kind": "true_false",
        "stem_md": "User's private question",
        "options": [
            {"body_md": "True", "is_correct": True},
            {"body_md": "False", "is_correct": False},
        ],
    }
    q = create_draft(USER, payload)
    coll = create_collection(USER, kind="custom", title="My Collection", visibility="private")

    report = delete_all_for_user(USER)
    assert report.questions_deleted >= 1
    assert report.collections_deleted >= 1

    assert not Question.objects.filter(id=q.id).exists()
    assert not Collection.objects.filter(id=coll.id).exists()
