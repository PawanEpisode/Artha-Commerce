"""
Tests for CMA Syllabus 2022 amendments seed and course/level/attempt isolation.
Verifies that:
1. `seed_cma_amendments` successfully ingests statutory updates for CMA Inter & Final.
2. Ingestion is idempotent.
3. CMA Final students NEVER see Intermediate cards.
4. CMA Intermediate students NEVER see Final cards.
5. June 2026 attempt students do NOT see December 2026 exclusive cards.
6. December 2026 attempt students see both June 2026 and December 2026 applicable cards.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from django.core.management import call_command

from modules.amendments.models import Amendment, ChangeVersion, Revision
from modules.amendments.selectors import get_viewer_context, my_changes, my_summary
from modules.coverage.services import create_enrollment
from modules.syllabus.models import Course, ExamTerm, Level, Scheme

pytestmark = pytest.mark.django_db


@pytest.fixture
def cma_syllabus_and_terms(db):
    # Ensure syllabus is loaded and published
    call_command("load_syllabus_seed", "--publish")

    cma = Course.objects.get(code="cma")
    lvl_inter = Level.objects.get(course=cma, code="intermediate")
    lvl_final = Level.objects.get(course=cma, code="final")

    scheme_inter = Scheme.objects.get(level=lvl_inter, code="2022", status=Scheme.Status.PUBLISHED)
    scheme_final = Scheme.objects.get(level=lvl_final, code="2022", status=Scheme.Status.PUBLISHED)

    # Ensure exam terms exist
    term_inter_j26, _ = ExamTerm.objects.get_or_create(
        level=lvl_inter,
        code="2026-06",
        defaults={"name": "June 2026", "exam_start": date(2026, 6, 11), "is_open": True},
    )
    term_inter_d26, _ = ExamTerm.objects.get_or_create(
        level=lvl_inter,
        code="2026-12",
        defaults={"name": "December 2026", "exam_start": date(2026, 12, 10), "is_open": True},
    )
    term_final_j26, _ = ExamTerm.objects.get_or_create(
        level=lvl_final,
        code="2026-06",
        defaults={"name": "June 2026", "exam_start": date(2026, 6, 11), "is_open": True},
    )
    term_final_d26, _ = ExamTerm.objects.get_or_create(
        level=lvl_final,
        code="2026-12",
        defaults={"name": "December 2026", "exam_start": date(2026, 12, 10), "is_open": True},
    )

    return {
        "cma": cma,
        "lvl_inter": lvl_inter,
        "lvl_final": lvl_final,
        "scheme_inter": scheme_inter,
        "scheme_final": scheme_final,
        "term_inter_j26": term_inter_j26,
        "term_inter_d26": term_inter_d26,
        "term_final_j26": term_final_j26,
        "term_final_d26": term_final_d26,
    }


def test_seed_cma_amendments_command_execution(cma_syllabus_and_terms):
    """Verifies that seed_cma_amendments runs cleanly and is idempotent."""
    call_command("seed_cma_amendments")

    cma = cma_syllabus_and_terms["cma"]
    lvl_inter = cma_syllabus_and_terms["lvl_inter"]
    lvl_final = cma_syllabus_and_terms["lvl_final"]

    # Verify amendments created (8 Intermediate booklets + 9 Final booklets = 17 total)
    inter_amds = Amendment.objects.filter(level=lvl_inter)
    final_amds = Amendment.objects.filter(level=lvl_final)

    assert inter_amds.count() == 8
    assert final_amds.count() == 9
    assert (inter_amds.count() + final_amds.count()) == 17

    # Verify all revisions are released (state=live) and have valid Supabase CDN URLs
    revisions = Revision.objects.filter(amendment__course=cma)
    assert revisions.count() == 17
    for rev in revisions:
        assert rev.state == Revision.State.LIVE
        assert rev.terms.count() >= 1
        assert rev.subjects.count() >= 1
        assert rev.official_url.startswith("https://")
        assert "/storage/v1/object/public/amendments/cma/" in rev.official_url
        assert rev.official_url.endswith(".pdf")

    # Verify change cards exist and are marked live
    cards = ChangeVersion.objects.filter(revision__amendment__course=cma)
    assert cards.count() >= 18
    for card in cards:
        assert card.is_live is True
        assert card.effective_from_term_code in ("2026-06", "2026-12")

    # Re-run for idempotency
    call_command("seed_cma_amendments")


def test_cma_course_and_attempt_isolation(cma_syllabus_and_terms):
    """
    Verifies strict level isolation and attempt-wise filtering:
    - Intermediate students never see Final cards.
    - Final students never see Intermediate cards.
    - June 2026 students do not see Dec 2026-only cards.
    - Dec 2026 students see both June 2026 and Dec 2026 cards.
    """
    call_command("seed_cma_amendments")

    scheme_inter = cma_syllabus_and_terms["scheme_inter"]
    scheme_final = cma_syllabus_and_terms["scheme_final"]
    term_inter_j26 = cma_syllabus_and_terms["term_inter_j26"]
    term_inter_d26 = cma_syllabus_and_terms["term_inter_d26"]
    term_final_j26 = cma_syllabus_and_terms["term_final_j26"]
    term_final_d26 = cma_syllabus_and_terms["term_final_d26"]

    # 1. CMA Intermediate June 2026 Student
    user_inter_j26 = uuid.uuid4()
    create_enrollment(
        user_id=user_inter_j26,
        scheme_id=scheme_inter.id,
        target_term_id=term_inter_j26.id,
        daily_minutes=120,
    )
    ctx_inter_j26 = get_viewer_context(user_inter_j26)
    assert ctx_inter_j26 is not None
    assert ctx_inter_j26["term_code"] == "2026-06"

    changes_inter_j26 = my_changes(ctx_inter_j26, flt={})
    inter_j26_titles = [c["title"] for c in changes_inter_j26["cards"]]

    # Intermediate J26 cards must be present
    assert any("Corporate Social Responsibility Policy" in t for t in inter_j26_titles)
    assert any("Discontinuation of TCS u/s 206C(1H)" in t for t in inter_j26_titles)
    assert any("Section 22(1)" in t for t in inter_j26_titles)

    # Intermediate D26-only cards MUST NOT be present
    assert not any("Small Company" in t for t in inter_j26_titles)
    assert not any("Zero Coupon Zero Principal" in t for t in inter_j26_titles)
    assert not any("Rule 31D" in t for t in inter_j26_titles)

    # Final cards MUST NOT be present in Intermediate
    assert not any("Form ADT-4" in t for t in inter_j26_titles)
    assert not any("Pillar Two" in t for t in inter_j26_titles)
    assert not any("CRA-1" in t for t in inter_j26_titles)

    # 2. CMA Intermediate Dec 2026 Student
    user_inter_d26 = uuid.uuid4()
    create_enrollment(
        user_id=user_inter_d26,
        scheme_id=scheme_inter.id,
        target_term_id=term_inter_d26.id,
        daily_minutes=120,
    )
    ctx_inter_d26 = get_viewer_context(user_inter_d26)
    assert ctx_inter_d26 is not None
    assert ctx_inter_d26["term_code"] == "2026-12"

    changes_inter_d26 = my_changes(ctx_inter_d26, flt={})
    inter_d26_titles = [c["title"] for c in changes_inter_d26["cards"]]

    # Both J26 and D26 intermediate cards apply to Dec 2026
    assert any("Corporate Social Responsibility Policy" in t for t in inter_d26_titles)
    assert any("Small Company" in t for t in inter_d26_titles)
    assert any("Zero Coupon Zero Principal" in t for t in inter_d26_titles)
    assert any("Rule 31D" in t for t in inter_d26_titles)

    # Final cards still MUST NOT be present
    assert not any("Form ADT-4" in t for t in inter_d26_titles)
    assert not any("Pillar Two" in t for t in inter_d26_titles)

    # 3. CMA Final June 2026 Student
    user_final_j26 = uuid.uuid4()
    create_enrollment(
        user_id=user_final_j26,
        scheme_id=scheme_final.id,
        target_term_id=term_final_j26.id,
        daily_minutes=120,
    )
    ctx_final_j26 = get_viewer_context(user_final_j26)
    assert ctx_final_j26 is not None
    assert ctx_final_j26["term_code"] == "2026-06"

    changes_final_j26 = my_changes(ctx_final_j26, flt={})
    final_j26_titles = [c["title"] for c in changes_final_j26["cards"]]

    # Final June 2026 cards must be present
    assert any("Form ADT-4" in t for t in final_j26_titles)
    assert any("Pillar Two" in t for t in final_j26_titles)
    assert any("Regulation 23" in t for t in final_j26_titles)

    # Final Dec 2026-only cards MUST NOT be present
    assert not any("CRA-1" in t for t in final_j26_titles)

    # Intermediate cards MUST NOT be present in Final
    assert not any("Corporate Social Responsibility Policy" in t for t in final_j26_titles)
    assert not any("Small Company" in t for t in final_j26_titles)
    assert not any("Section 22(1)" in t for t in final_j26_titles)

    # 4. CMA Final Dec 2026 Student
    user_final_d26 = uuid.uuid4()
    create_enrollment(
        user_id=user_final_d26,
        scheme_id=scheme_final.id,
        target_term_id=term_final_d26.id,
        daily_minutes=120,
    )
    ctx_final_d26 = get_viewer_context(user_final_d26)
    assert ctx_final_d26 is not None
    assert ctx_final_d26["term_code"] == "2026-12"

    changes_final_d26 = my_changes(ctx_final_d26, flt={})
    final_d26_titles = [c["title"] for c in changes_final_d26["cards"]]

    # Final June 2026 AND Dec 2026 cards must be present
    assert any("Form ADT-4" in t for t in final_d26_titles)
    assert any("Pillar Two" in t for t in final_d26_titles)
    assert any("CRA-1 and CRA-3" in t for t in final_d26_titles)

    # Summary check
    summary_final_d26 = my_summary(ctx_final_d26)
    assert summary_final_d26["total_cards_count"] >= 5
    assert len(summary_final_d26["breakdown_by_paper"]) >= 2
