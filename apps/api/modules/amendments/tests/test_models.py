import uuid
from datetime import date

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from modules.amendments.models import (
    Amendment,
    AmendmentAuditLog,
    CardState,
    Change,
    ChangeMap,
    ChangeVersion,
    Revision,
    RevisionSubject,
    RevisionTerm,
)
from modules.syllabus.tests.helpers import make_scheme


@pytest.fixture
def syllabus_setup(db):
    scheme = make_scheme()
    level = scheme.level
    course = level.course
    subject_tax = scheme.subjects.get(key="taxation")
    chapter_gst = subject_tax.chapters.get(key="gst-itc")
    topic_eligibility = chapter_gst.topics.get(key="eligibility")
    return {
        "scheme": scheme,
        "course": course,
        "level": level,
        "subject_tax": subject_tax,
        "chapter_gst": chapter_gst,
        "topic_eligibility": topic_eligibility,
    }


@pytest.mark.django_db
def test_create_amendment_with_revisions_and_cards(syllabus_setup):
    course = syllabus_setup["course"]
    level = syllabus_setup["level"]
    subject_tax = syllabus_setup["subject_tax"]
    chapter_gst = syllabus_setup["chapter_gst"]
    scheme = syllabus_setup["scheme"]

    # 1. Create Amendment stream
    amendment = Amendment.objects.create(
        slug="ca-inter-may2026-statutory-update-taxation",
        course=course,
        level=level,
        doc_key="statutory_update:taxation:2026-05:may-2026",
        kind=Amendment.Kind.STATUTORY_UPDATE,
        title="BOS Statutory Update for May 2026 Examination - Paper 3 Taxation",
        short_title="Statutory Update: Taxation (May 2026)",
        issuer_label="ICAI Board of Studies",
        landing_url="https://boslive.icai.org/announcement_details.php?id=522",
    )
    assert len(amendment.public_id) == 10
    assert amendment.status == Amendment.Status.ACTIVE

    # 2. Create Revision 1 (staged)
    rev1 = Revision.objects.create(
        amendment=amendment,
        revision_no=1,
        state=Revision.State.STAGED,
        revision_kind=Revision.Kind.INITIAL,
        issued_on=date(2025, 11, 15),
        official_url="https://boslive.icai.org/assets/statutory_update_may2026.pdf",
        doc_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        page_count=24,
    )

    # 3. Add paper scope and term applicability
    rev_subj = RevisionSubject.objects.create(
        revision=rev1,
        subject=subject_tax,
        subject_key=subject_tax.key,
        scheme=scheme,
        level=level,
    )
    rev_term = RevisionTerm.objects.create(
        revision=rev1,
        term_code="2026-05",
        applicability=RevisionTerm.Applicability.APPLIES,
        cutoff_date=date(2025, 10, 31),
        cutoff_note="Amendments issued up to 31 Oct 2025",
        source_page=1,
    )
    assert rev_subj.subject_key == "taxation"
    assert rev_term.term_code == "2026-05"

    # 4. Create Change and ChangeVersion
    change = Change.objects.create(
        amendment=amendment,
        card_key="cgst:17(5)(d):modification",
    )
    assert len(change.public_id) == 10

    cver = ChangeVersion.objects.create(
        change=change,
        revision=rev1,
        change_type=ChangeVersion.ChangeType.MODIFICATION,
        law_key="cgst_act_2017",
        provision_label="Section 17(5)(d)",
        provision_keys=["cgst:17(5)(d)"],
        title="Input tax credit on goods or services received for construction",
        summary_old="ITC was blocked on goods or services used for construction of immovable property.",
        summary_new="Plant and machinery exception clarified; works contract for factory shed allowed.",
        effective_from_term_code="2026-05",
        materiality=ChangeVersion.Materiality.HIGH,
        source_page=12,
        evidence_quote="Explanation to section 17(5)(d) amended by Finance Act...",
    )
    change.current_version = cver
    change.save()

    # 5. Map to syllabus
    cmap = ChangeMap.objects.create(
        change_version=cver,
        subject=subject_tax,
        chapter=chapter_gst,
        subject_key=subject_tax.key,
        chapter_key=chapter_gst.key,
        is_primary=True,
        status=ChangeMap.Status.CONFIRMED,
    )
    assert cmap.chapter_key == "gst-itc"

    # 6. Student card state
    user_id = uuid.uuid4()
    state = CardState.objects.create(
        user_id=user_id,
        change=change,
        reviewed_at=timezone.now(),
        reviewed_version=cver,
        saved=True,
    )
    assert state.saved is True
    assert state.reviewed_at is not None

    # 7. Audit log
    audit = AmendmentAuditLog.objects.create(
        amendment=amendment,
        revision=rev1,
        change=change,
        action="stage_card",
        metadata={"editor": "Meera", "action": "add_card"},
    )
    assert audit.action == "stage_card"


@pytest.mark.django_db
def test_revision_unique_constraints(syllabus_setup):
    course = syllabus_setup["course"]
    level = syllabus_setup["level"]

    amendment = Amendment.objects.create(
        slug="ca-inter-may2026-audit",
        course=course,
        level=level,
        doc_key="statutory_update:audit:2026-05",
        kind=Amendment.Kind.STATUTORY_UPDATE,
        title="Audit Update",
        issuer_label="ICAI",
    )

    # Create rev1
    Revision.objects.create(
        amendment=amendment,
        revision_no=1,
        state=Revision.State.LIVE,
        issued_on=date(2025, 11, 1),
    )

    # 1. Duplicate revision_no should fail
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Revision.objects.create(
                amendment=amendment,
                revision_no=1,
                state=Revision.State.STAGED,
                issued_on=date(2025, 11, 2),
            )

    # 2. Only ONE live revision can exist per amendment
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Revision.objects.create(
                amendment=amendment,
                revision_no=2,
                state=Revision.State.LIVE,
                issued_on=date(2025, 11, 3),
            )

    # 3. Only ONE open (staged / in_review) revision can exist per amendment
    Revision.objects.create(
        amendment=amendment,
        revision_no=2,
        state=Revision.State.STAGED,
        issued_on=date(2025, 11, 4),
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Revision.objects.create(
                amendment=amendment,
                revision_no=3,
                state=Revision.State.IN_REVIEW,
                issued_on=date(2025, 11, 5),
            )


@pytest.mark.django_db
def test_amendment_live_revision_status_check(syllabus_setup):
    course = syllabus_setup["course"]
    level = syllabus_setup["level"]

    amendment = Amendment.objects.create(
        slug="ca-inter-retracted-test",
        course=course,
        level=level,
        doc_key="corrigendum:tax:2026-05",
        kind=Amendment.Kind.CORRIGENDUM,
        title="Corrigendum Notice",
        issuer_label="ICAI",
    )

    rev = Revision.objects.create(
        amendment=amendment,
        revision_no=1,
        state=Revision.State.LIVE,
        issued_on=date(2025, 11, 1),
    )

    amendment.live_revision = rev
    amendment.status = Amendment.Status.ACTIVE
    amendment.save()

    # Setting status to RETRACTED while live_revision is not None violates the check constraint
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            amendment.status = Amendment.Status.RETRACTED
            amendment.save()
