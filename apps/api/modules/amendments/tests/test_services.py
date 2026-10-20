import uuid
from io import StringIO

import pytest
from django.core.management import call_command

from core.events import subscribe, unsubscribe
from modules.amendments.errors import (
    OpenRevisionExistsError,
    ReleaseChecklistFailedError,
    RevisionNotLiveError,
)
from modules.amendments.models import (
    Amendment,
    CardState,
    Change,
    ChangeVersion,
    Revision,
)
from modules.amendments.services import (
    create_amendment_draft,
    delete_all_for_user,
    export_for_user,
    reissue_document,
    release_revision,
    retract_revision,
    set_revision_scope,
    stage_change_card,
)
from modules.syllabus.tests.helpers import make_scheme


@pytest.fixture
def setup_syllabus(db):
    scheme = make_scheme()
    level = scheme.level
    course = level.course
    subject_tax = scheme.subjects.get(key="taxation")
    chapter_gst = subject_tax.chapters.get(key="gst-itc")
    return {
        "scheme": scheme,
        "course": course,
        "level": level,
        "subject_tax": subject_tax,
        "chapter_gst": chapter_gst,
    }


@pytest.mark.django_db
def test_create_draft_and_stage_card(setup_syllabus):
    course = setup_syllabus["course"]
    level = setup_syllabus["level"]
    subject = setup_syllabus["subject_tax"]
    chapter = setup_syllabus["chapter_gst"]
    scheme = setup_syllabus["scheme"]

    amendment, revision = create_amendment_draft(
        course_id=course.id,
        level_id=level.id,
        title="Test Update",
        doc_key="test_update:taxation:2026-05",
        official_url="https://example.com/update.pdf",
    )
    assert revision.state == Revision.State.STAGED
    assert amendment.current_revision == revision
    assert amendment.live_revision is None

    # Set scope
    set_revision_scope(
        revision_id=revision.id,
        subjects=[{"subject_id": subject.id, "subject_key": subject.key, "scheme_id": scheme.id, "level_id": level.id}],
        terms=[{"term_code": "2026-05", "applicability": "applies"}],
    )
    assert revision.subjects.count() == 1
    assert revision.terms.count() == 1

    # Stage card
    cver = stage_change_card(
        revision_id=revision.id,
        title="ITC Section 17(5) clarification",
        provision_label="Section 17(5)(d)",
        change_type=ChangeVersion.ChangeType.MODIFICATION,
        summary_new="New rule allows plant and machinery credit.",
        law_key="cgst_act_2017",
        chapter_mappings=[
            {"subject_id": subject.id, "subject_key": subject.key, "chapter_id": chapter.id, "chapter_key": chapter.key}
        ],
    )
    assert cver.change.card_key.startswith("cgst-act-2017:section-175d:modification:itc-section-175")
    assert cver.maps.count() == 1


@pytest.mark.django_db
def test_release_revision_checklist_failure_and_success(setup_syllabus):
    course = setup_syllabus["course"]
    level = setup_syllabus["level"]
    subject = setup_syllabus["subject_tax"]
    chapter = setup_syllabus["chapter_gst"]
    scheme = setup_syllabus["scheme"]

    amendment, revision = create_amendment_draft(
        course_id=course.id,
        level_id=level.id,
        title="Release Test",
        doc_key="test:release",
        official_url="https://example.com/test.pdf",
    )

    # Releasing without scope must raise ReleaseChecklistFailedError
    with pytest.raises(ReleaseChecklistFailedError):
        release_revision(revision_id=revision.id)

    # Set scope
    set_revision_scope(
        revision_id=revision.id,
        subjects=[{"subject_id": subject.id, "subject_key": subject.key, "scheme_id": scheme.id, "level_id": level.id}],
        terms=[{"term_code": "2026-05", "applicability": "applies"}],
    )

    # Stage an unmapped modification card -> release must fail
    stage_change_card(
        revision_id=revision.id,
        title="Unmapped Card",
        provision_label="Section 1",
        change_type=ChangeVersion.ChangeType.MODIFICATION,
        summary_new="Summary",
        chapter_mappings=[],
    )
    with pytest.raises(ReleaseChecklistFailedError):
        release_revision(revision_id=revision.id)

    # Now add chapter mapping
    stage_change_card(
        revision_id=revision.id,
        title="Unmapped Card",
        provision_label="Section 1",
        change_type=ChangeVersion.ChangeType.MODIFICATION,
        summary_new="Summary",
        chapter_mappings=[
            {"subject_id": subject.id, "subject_key": subject.key, "chapter_id": chapter.id, "chapter_key": chapter.key}
        ],
    )

    # Capture emitted events
    received_events = []

    def handler(**kwargs):
        received_events.append(kwargs)

    subscribe("amendment_published", handler)

    try:
        rel_rev = release_revision(revision_id=revision.id)
        assert rel_rev.state == Revision.State.LIVE
        assert rel_rev.released_at is not None
        amendment.refresh_from_db()
        assert amendment.live_revision == rel_rev
        assert amendment.status == Amendment.Status.ACTIVE

        # Verify event emitted
        assert len(received_events) == 1
        ev = received_events[0]
        assert ev["payload"]["amendment_id"] == str(amendment.id)
        assert ev["payload"]["counts"]["cards"] == 1
    finally:
        unsubscribe("amendment_published", handler)


@pytest.mark.django_db
def test_reissue_document_flow(setup_syllabus):
    course = setup_syllabus["course"]
    level = setup_syllabus["level"]
    subject = setup_syllabus["subject_tax"]
    chapter = setup_syllabus["chapter_gst"]
    scheme = setup_syllabus["scheme"]

    amendment, rev1 = create_amendment_draft(
        course_id=course.id,
        level_id=level.id,
        title="Reissue Test",
        doc_key="test:reissue",
        official_url="https://example.com/rev1.pdf",
    )
    set_revision_scope(
        revision_id=rev1.id,
        subjects=[{"subject_id": subject.id, "subject_key": subject.key, "scheme_id": scheme.id, "level_id": level.id}],
        terms=[{"term_code": "2026-05", "applicability": "applies"}],
    )
    stage_change_card(
        revision_id=rev1.id,
        title="Card 1",
        provision_label="Section 10",
        change_type=ChangeVersion.ChangeType.MODIFICATION,
        summary_new="Summary 1",
        chapter_mappings=[
            {"subject_id": subject.id, "subject_key": subject.key, "chapter_id": chapter.id, "chapter_key": chapter.key}
        ],
    )
    release_revision(revision_id=rev1.id)

    # Reissue creates Revision 2
    rev2 = reissue_document(
        amendment_id=amendment.id,
        new_official_url="https://example.com/rev2.pdf",
    )
    assert rev2.revision_no == 2
    assert rev2.state == Revision.State.STAGED
    assert rev2.revision_kind == Revision.Kind.REISSUE
    assert rev2.change_versions.count() == 1
    cv2 = rev2.change_versions.first()
    assert cv2.revision_effect == ChangeVersion.RevisionEffect.UNCHANGED
    assert cv2.maps.count() == 1

    # Attempting to reissue again while rev2 is open raises error
    with pytest.raises(OpenRevisionExistsError):
        reissue_document(amendment_id=amendment.id, new_official_url="https://example.com/rev3.pdf")


@pytest.mark.django_db
def test_retract_revision(setup_syllabus):
    course = setup_syllabus["course"]
    level = setup_syllabus["level"]
    subject = setup_syllabus["subject_tax"]
    chapter = setup_syllabus["chapter_gst"]
    scheme = setup_syllabus["scheme"]

    amendment, rev1 = create_amendment_draft(
        course_id=course.id,
        level_id=level.id,
        title="Retract Test",
        doc_key="test:retract",
        official_url="https://example.com/retract.pdf",
    )
    set_revision_scope(
        revision_id=rev1.id,
        subjects=[{"subject_id": subject.id, "subject_key": subject.key, "scheme_id": scheme.id, "level_id": level.id}],
        terms=[{"term_code": "2026-05", "applicability": "applies"}],
    )
    stage_change_card(
        revision_id=rev1.id,
        title="Card To Retract",
        provision_label="Section 99",
        change_type=ChangeVersion.ChangeType.MODIFICATION,
        summary_new="Summary",
        chapter_mappings=[
            {"subject_id": subject.id, "subject_key": subject.key, "chapter_id": chapter.id, "chapter_key": chapter.key}
        ],
    )

    # Cannot retract revision before it is live
    with pytest.raises(RevisionNotLiveError):
        retract_revision(revision_id=rev1.id)

    release_revision(revision_id=rev1.id)

    retracted_events = []

    def handler(**kwargs):
        retracted_events.append(kwargs)

    subscribe("amendment_retracted", handler)

    try:
        ret_rev = retract_revision(revision_id=rev1.id, reason="institute_withdrew")
        assert ret_rev.state == Revision.State.RETRACTED
        amendment.refresh_from_db()
        assert amendment.live_revision is None
        assert amendment.status == Amendment.Status.RETRACTED

        assert len(retracted_events) == 1
        assert retracted_events[0]["payload"]["reason"] == "institute_withdrew"
    finally:
        unsubscribe("amendment_retracted", handler)


@pytest.mark.django_db
def test_user_erasure_and_export(setup_syllabus):
    user_id = uuid.uuid4()
    course = setup_syllabus["course"]
    level = setup_syllabus["level"]

    amendment, _ = create_amendment_draft(
        course_id=course.id,
        level_id=level.id,
        title="Erasure Test",
        doc_key="test:erasure",
    )
    change = Change.objects.create(amendment=amendment, card_key="test:card")
    CardState.objects.create(user_id=user_id, change=change, saved=True)

    # Test export
    exp = export_for_user(user_id=user_id)
    assert len(exp["amendments_card_states"]) == 1
    assert exp["amendments_card_states"][0]["change__card_key"] == "test:card"

    # Test delete
    res = delete_all_for_user(user_id=user_id)
    assert res["card_states_deleted"] == 1
    assert CardState.objects.filter(user_id=user_id).count() == 0


@pytest.mark.django_db
def test_seed_amendments_command():
    out = StringIO()
    call_command("seed_amendments", stdout=out)
    output = out.getvalue()
    assert "Successfully seeded and released" in output

    # Check database
    amendment = Amendment.objects.filter(doc_key="statutory_update:taxation:2026-05:may-2026").first()
    assert amendment is not None
    assert amendment.live_revision is not None
    assert amendment.live_revision.change_versions.count() == 4

    # Idempotent second call
    out2 = StringIO()
    call_command("seed_amendments", stdout=out2)
    assert "already seeded" in out2.getvalue()
