from datetime import timedelta

import pytest
from django.utils import timezone

from modules.coverage.models import ChapterProgress, Enrollment
from modules.progression import selectors, services
from modules.progression.errors import ConflictError, RollbackExpiredError
from modules.progression.models import ArticleshipProfile, ExemptionLedger, LevelTransition, PaperResult
from modules.progression.tests.conftest import USER


def test_full_level_pass_graduation(enrolled, final_scheme):
    prior_id = enrolled.id
    res = services.execute_transition(
        user_id=USER,
        transition_type=LevelTransition.TransitionType.FULL_LEVEL_PASS,
        target_level_code="final",
        paper_results=[
            {"subject_key": "taxation", "status": "passed", "marks": 65},
            {"subject_key": "corporate-laws", "status": "passed", "marks": 58},
        ],
        articleship_data={
            "is_active": True,
            "firm_name": "KPMG India",
            "weekday_minutes": 150,
            "weekend_minutes": 360,
            "study_mode": ArticleshipProfile.StudyMode.ACTIVE_STUDY,
        },
    )

    assert res["status"] == "applied"
    assert res["vault_archived_enrollment_id"] == str(prior_id)
    assert "Congratulations" in res["message"]

    # Check prior enrollment is archived
    prior_enr = Enrollment.objects.get(pk=prior_id)
    assert prior_enr.status == Enrollment.Status.ARCHIVED

    # Check new enrollment is active and for Final
    new_enr = Enrollment.objects.get(pk=res["new_enrollment_id"])
    assert new_enr.status == Enrollment.Status.ACTIVE
    assert new_enr.level.code == "final"

    # Check paper results were saved
    results = PaperResult.objects.filter(transition_id=res["transition_id"])
    assert results.count() == 2
    tax_res = results.get(subject_key="taxation")
    assert tax_res.marks_obtained == 65

    # Check exemption ledger: taxation scored >= 60 so it has an exemption
    exemption = ExemptionLedger.objects.get(user_id=USER, subject_key="taxation")
    assert exemption.marks_obtained == 65
    assert not exemption.is_exhausted


def test_group_clearance_excludes_cleared_papers(enrolled, final_scheme):
    prior_id = enrolled.id
    res = services.execute_transition(
        user_id=USER,
        transition_type=LevelTransition.TransitionType.GROUP_CLEARANCE,
        cleared_group_keys=["group-1"],
    )

    assert res["status"] == "applied"
    assert res["new_enrollment_id"] == str(prior_id)

    # Current enrollment remains active
    enr = Enrollment.objects.get(pk=prior_id)
    assert enr.status == Enrollment.Status.ACTIVE

    # Taxation was in group-1, so its chapters should now be excluded and exam ready
    tax_progress = ChapterProgress.objects.filter(enrollment=enr, chapter__subject__key="taxation")
    assert tax_progress.exists()
    for cp in tax_progress:
        assert cp.is_excluded is True
        assert cp.status == ChapterProgress.Status.EXAM_READY


def test_paper_exemption_60_plus_rule(enrolled):
    res = services.execute_transition(
        user_id=USER,
        transition_type=LevelTransition.TransitionType.EXEMPTION_UPDATE,
        paper_results=[
            {"subject_key": "taxation", "status": "exempted", "marks": 72, "is_permanent": True},
        ],
    )
    assert res["status"] == "applied"

    exemption = ExemptionLedger.objects.get(user_id=USER, subject_key="taxation")
    assert exemption.marks_obtained == 72
    assert exemption.is_permanent is True
    assert exemption.valid_until_term_code is None


def test_rollback_transition_within_48_hours(enrolled, final_scheme):
    prior_id = enrolled.id
    res = services.execute_transition(
        user_id=USER,
        transition_type=LevelTransition.TransitionType.FULL_LEVEL_PASS,
        target_level_code="final",
    )
    new_id = res["new_enrollment_id"]

    # Undo transition
    rollback_res = services.rollback_transition(USER, res["transition_id"])
    assert rollback_res["status"] == "reverted"

    # Prior enrollment is active again
    prior_enr = Enrollment.objects.get(pk=prior_id)
    assert prior_enr.status == Enrollment.Status.ACTIVE

    # Target enrollment is archived
    new_enr = Enrollment.objects.get(pk=new_id)
    assert new_enr.status == Enrollment.Status.ARCHIVED


def test_rollback_expired_after_48_hours(enrolled, final_scheme):
    res = services.execute_transition(
        user_id=USER,
        transition_type=LevelTransition.TransitionType.FULL_LEVEL_PASS,
        target_level_code="final",
    )
    t = LevelTransition.objects.get(pk=res["transition_id"])
    # Backdate transition by 49 hours
    LevelTransition.objects.filter(pk=t.id).update(created_at=timezone.now() - timedelta(hours=49))

    with pytest.raises(RollbackExpiredError):
        services.rollback_transition(USER, t.id)


def test_rollback_already_reverted_conflict(enrolled, final_scheme):
    res = services.execute_transition(
        user_id=USER,
        transition_type=LevelTransition.TransitionType.FULL_LEVEL_PASS,
        target_level_code="final",
    )
    services.rollback_transition(USER, res["transition_id"])

    with pytest.raises(ConflictError):
        services.rollback_transition(USER, res["transition_id"])


def test_articleship_upsert_and_daily_minutes(enrolled):
    profile = services.upsert_articleship(
        USER,
        {
            "is_active": True,
            "firm_name": "PwC",
            "study_mode": ArticleshipProfile.StudyMode.WORK_FOCUS_PAUSE,
            "weekday_minutes": 90,
            "weekend_minutes": 240,
        },
        active_enrollment=enrolled,
    )

    assert profile.firm_name == "PwC"
    assert profile.is_active is True
    # In work_focus_pause mode, planned study time is set to 30 mins
    enrolled.refresh_from_db()
    assert enrolled.daily_minutes == 30


def test_dpdp_export_and_erasure(enrolled, final_scheme):
    services.execute_transition(
        user_id=USER,
        transition_type=LevelTransition.TransitionType.FULL_LEVEL_PASS,
        target_level_code="final",
        articleship_data={"is_active": True, "firm_name": "Deloitte"},
        paper_results=[{"subject_key": "taxation", "marks": 64}],
    )

    exported = selectors.export_all(USER)
    assert exported["articleship"]["firm_name"] == "Deloitte"
    assert len(exported["exemptions"]) >= 1
    assert len(exported["transition_history"]) >= 1

    # Now erase
    del_res = services.delete_all_for_user(USER)
    assert del_res["transitions_deleted"] >= 1
    assert del_res["articleship_profiles_deleted"] >= 1
    assert del_res["exemptions_deleted"] >= 1

    assert LevelTransition.objects.filter(user_id=USER).count() == 0
    assert ArticleshipProfile.objects.filter(user_id=USER).count() == 0
    assert ExemptionLedger.objects.filter(user_id=USER).count() == 0
