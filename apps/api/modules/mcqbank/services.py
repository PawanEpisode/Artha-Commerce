"""
Service functions for MCQ Bank (F-05 ERD 3.2).
Manages MCQ sets, exam presets, external logs, pattern verifications, and adaptive practice chains.
"""

from __future__ import annotations

import datetime
import logging
import uuid
from decimal import Decimal
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from modules.coverage import services as coverage_services
from modules.practice import services as practice_services
from modules.questionbank.models import Collection, CollectionItem

from .domain.adaptive import compute_item_difficulty, update_theta_from_answers
from .domain.links import is_safe_linkout_url
from .events import (
    emit_adaptive_round_applied,
    emit_external_logged,
    emit_set_published,
    emit_set_withdrawn,
)
from .models import (
    AbilityEstimate,
    AdaptiveRound,
    AdaptiveRun,
    ExternalLog,
    McqSet,
    PatternProfile,
    TestPreset,
)

logger = logging.getLogger(__name__)


def publish_set(editor_id: uuid.UUID, set_id: uuid.UUID) -> McqSet:
    """
    Publishes an MCQ set after verifying delivery and rights rules.
    Hosted requires collection with members, link_out requires valid https url.
    """
    with transaction.atomic():
        mcq_set = McqSet.objects.select_for_update().get(id=set_id)

        if mcq_set.delivery == McqSet.Delivery.HOSTED:
            if not mcq_set.collection_id:
                raise ValidationError("Hosted set must reference an F-06 collection.")
            count = CollectionItem.objects.filter(collection_id=mcq_set.collection_id).count()
            if count == 0:
                raise ValidationError("Hosted set collection cannot be empty.")
            mcq_set.question_count = count
        else:
            if not mcq_set.source_url:
                raise ValidationError("Link-out set must have a source_url.")
            if not is_safe_linkout_url(mcq_set.source_url):
                raise ValidationError(f"URL {mcq_set.source_url} is not an allowed secure linkout.")

        mcq_set.status = McqSet.Status.PUBLISHED
        mcq_set.published_at = timezone.now()
        mcq_set.save(update_fields=["status", "published_at", "question_count", "updated_at"])

    ch_ids = [mcq_set.chapter_id] if mcq_set.chapter_id else []
    emit_set_published(
        set_id=mcq_set.id,
        slug=mcq_set.slug,
        delivery=mcq_set.delivery,
        subject_key=mcq_set.subject_key,
        chapter_ids=ch_ids,
        term_code=mcq_set.term_code,
        question_count=mcq_set.question_count,
    )
    return mcq_set


def withdraw_set(actor_id: uuid.UUID, set_id: uuid.UUID, reason: str) -> None:
    """Withdraws a set from the catalogue."""
    with transaction.atomic():
        mcq_set = McqSet.objects.select_for_update().get(id=set_id)
        mcq_set.status = McqSet.Status.WITHDRAWN
        mcq_set.withdrawn_reason = reason
        mcq_set.save(update_fields=["status", "withdrawn_reason", "updated_at"])

    emit_set_withdrawn(set_id=mcq_set.id, reason=reason)


def switch_to_hosted(
    admin_id: uuid.UUID,
    set_id: uuid.UUID,
    *,
    rights_basis: str,
    rights_note: str,
    collection_id: uuid.UUID,
) -> McqSet:
    """Admin-only switch of a link-out set to hosted content."""
    with transaction.atomic():
        mcq_set = McqSet.objects.select_for_update().get(id=set_id)
        if not Collection.objects.filter(id=collection_id).exists():
            raise ValidationError(f"Collection {collection_id} does not exist.")

        count = CollectionItem.objects.filter(collection_id=collection_id).count()
        mcq_set.delivery = McqSet.Delivery.HOSTED
        mcq_set.collection_id = collection_id
        mcq_set.rights_basis = rights_basis
        mcq_set.rights_note = rights_note
        mcq_set.license_tier = "host"
        mcq_set.question_count = count
        mcq_set.save()

    return mcq_set


def record_click(user_id: uuid.UUID, set_id: uuid.UUID) -> None:
    """Validates existence of link-out set for click event analytics."""
    if not McqSet.objects.filter(id=set_id, status=McqSet.Status.PUBLISHED).exists():
        raise ValidationError("Set does not exist or is not published.")


def log_external_result(
    user_id: uuid.UUID,
    set_id: uuid.UUID,
    *,
    score: Decimal,
    max_score: Decimal,
    taken_on: datetime.date,
    client_id: uuid.UUID,
) -> ExternalLog:
    """
    Records a student's self-reported score for a link-out set.
    Upserts daily log and fires idempotent coverage event.
    """
    if score < 0 or score > max_score or max_score <= 0:
        raise ValidationError("Score must be between 0 and max_score (which must be > 0).")

    mcq_set = McqSet.objects.get(id=set_id)
    score_pct = round((score / max_score) * Decimal("100"), 1)
    chapter_id = mcq_set.chapter_id
    subject_id = mcq_set.subject_id

    # Deterministic coverage client_id
    cov_key = f"{set_id}:{chapter_id}:{taken_on}:practice_done"
    coverage_client_id = uuid.uuid5(uuid.NAMESPACE_DNS, cov_key)

    with transaction.atomic():
        log, _ = ExternalLog.objects.update_or_create(
            user_id=user_id,
            set=mcq_set,
            taken_on=taken_on,
            deleted_at__isnull=True,
            defaults={
                "client_id": client_id,
                "score": score,
                "max_score": max_score,
                "score_pct": score_pct,
                "chapter_id": chapter_id,
                "subject_id": subject_id,
                "coverage_client_id": coverage_client_id,
            },
        )

    # Coverage integration (append-only ledger)
    if chapter_id:
        try:
            coverage_services.record_event(
                user_id=user_id,
                chapter_id=chapter_id,
                event_name="practice_done",
                value=float(score_pct),
                source="manual",
                client_id=coverage_client_id,
                strict=False,
            )
        except Exception as exc:
            logger.warning("Failed to record coverage event for external log %s: %s", log.id, exc)

    emit_external_logged(
        user_id=user_id,
        set_id=set_id,
        chapter_id=chapter_id,
        score_pct=float(score_pct),
    )
    return log


def delete_external_log(user_id: uuid.UUID, log_id: uuid.UUID) -> None:
    """Soft deletes an external log."""
    log = ExternalLog.objects.get(id=log_id, user_id=user_id, deleted_at__isnull=True)
    log.deleted_at = timezone.now()
    log.save(update_fields=["deleted_at", "updated_at"])


def save_preset(
    user_id: uuid.UUID,
    *,
    name: str,
    kind: str,
    mode: str,
    picker: str,
    spec: dict,
    time_limit_seconds: int | None = None,
    scoring_profile: str = "practice",
    pattern_id: uuid.UUID | None = None,
    client_id: uuid.UUID | None = None,
) -> TestPreset:
    """Saves a practice test preset. Enforces 20-preset student limit."""
    with transaction.atomic():
        if client_id:
            existing = TestPreset.objects.filter(user_id=user_id, client_id=client_id).first()
            if existing:
                return existing

        count = TestPreset.objects.filter(user_id=user_id, deleted_at__isnull=True).count()
        if count >= 20:
            raise ValidationError("You have reached the limit of 20 saved presets.")

        preset = TestPreset.objects.create(
            user_id=user_id,
            is_system=False,
            name=name,
            kind=kind,
            mode=mode,
            picker=picker,
            spec=spec,
            time_limit_seconds=time_limit_seconds,
            scoring_profile=scoring_profile,
            pattern_id=pattern_id,
            client_id=client_id,
        )
    return preset


def use_preset(user_id: uuid.UUID, preset_id: uuid.UUID) -> dict[str, Any]:
    """Touches preset use_count and prepares parameters to launch an F-06 session."""
    preset = TestPreset.objects.get(id=preset_id, deleted_at__isnull=True)
    if not preset.is_system and preset.user_id != user_id:
        raise PermissionDenied("You do not own this preset.")

    preset.use_count += 1
    preset.last_used_at = timezone.now()
    preset.save(update_fields=["use_count", "last_used_at", "updated_at"])

    return {
        "picker": preset.picker,
        "mode": preset.mode,
        "spec": preset.spec,
        "time_limit_seconds": preset.time_limit_seconds,
        "scoring_profile": preset.scoring_profile,
        "origin_module": "mcq_bank",
        "origin_ref": f"preset:{preset.id}",
    }


def delete_preset(user_id: uuid.UUID, preset_id: uuid.UUID) -> None:
    """Soft deletes a student preset."""
    preset = TestPreset.objects.get(id=preset_id, user_id=user_id, deleted_at__isnull=True)
    preset.deleted_at = timezone.now()
    preset.save(update_fields=["deleted_at", "updated_at"])


def verify_pattern(editor_id: uuid.UUID, pattern_id: uuid.UUID) -> PatternProfile:
    """Marks a pattern profile as verified by editor."""
    pattern = PatternProfile.objects.get(id=pattern_id)
    pattern.verified = True
    pattern.verified_by = editor_id
    pattern.verified_at = timezone.now()
    pattern.status = PatternProfile.Status.ACTIVE
    pattern.save(update_fields=["verified", "verified_by", "verified_at", "status", "updated_at"])
    return pattern


# --- Adaptive Practice (R3) -------------------------------------------------------------------


def start_adaptive(
    user_id: uuid.UUID,
    *,
    scope_type: str,
    scope_id: uuid.UUID,
    subject_key: str,
    chapter_key: str = "",
    client_id: uuid.UUID,
) -> AdaptiveRun:
    """Starts or returns active adaptive run for this scope."""
    with transaction.atomic():
        run = AdaptiveRun.objects.filter(
            user_id=user_id,
            scope_type=scope_type,
            scope_id=scope_id,
            status=AdaptiveRun.Status.ACTIVE,
        ).first()

        if run:
            return run

        active_count = AdaptiveRun.objects.filter(user_id=user_id, status=AdaptiveRun.Status.ACTIVE).count()
        if active_count >= 3:
            raise ValidationError("You already have 3 active adaptive runs. Stop one to start another.")

        run = AdaptiveRun.objects.create(
            user_id=user_id,
            client_id=client_id,
            scope_type=scope_type,
            scope_id=scope_id,
            subject_key=subject_key,
            chapter_key=chapter_key,
        )
    return run


def next_round(user_id: uuid.UUID, run_id: uuid.UUID, *, round_no: int) -> dict[str, Any]:
    """
    Advances adaptive run: applies previous round under row lock, updates theta,
    creates F-06 session for round_no, and creates AdaptiveRound record.
    """
    with transaction.atomic():
        run = AdaptiveRun.objects.select_for_update().get(id=run_id, user_id=user_id)
        if run.status != AdaptiveRun.Status.ACTIVE:
            raise ValidationError(f"Adaptive run is {run.status}.")

        # Check if previous round needs application
        prev_round = AdaptiveRound.objects.filter(run=run, round_no=round_no - 1, state="open").first()
        if prev_round:
            _apply_round(user_id, run, prev_round)

        # Create session for the new round
        picker_spec = {
            "v": 1,
            "run_id": str(run.id),
            "round_no": round_no,
        }
        session = practice_services.create_session(
            user_id=user_id,
            mode="chapter_quiz",
            picker="mcq_adaptive",
            spec=picker_spec,
            origin_module="mcq_bank",
            origin_ref=f"adaptive:{run.id}:{round_no}",
            client_id=uuid.uuid4(),
        )

        # Current theta
        est, _ = AbilityEstimate.objects.get_or_create(
            user_id=user_id, scope_type=run.scope_type, scope_id=run.scope_id
        )

        round_record, _ = AdaptiveRound.objects.get_or_create(
            run=run,
            round_no=round_no,
            defaults={
                "session_id": session.session_id,
                "state": "open",
                "theta_before": est.theta,
                "theta_after": est.theta,
            },
        )
        run.rounds_started = max(run.rounds_started, round_no)
        run.last_active_at = timezone.now()
        run.save(update_fields=["rounds_started", "last_active_at", "updated_at"])

    return {
        "round_no": round_no,
        "session_id": session.session_id,
        "theta": est.theta,
    }


def _apply_round(user_id: uuid.UUID, run: AdaptiveRun, round_obj: AdaptiveRound) -> None:
    """Applies student's answers from session into ability estimate."""
    from modules.practice.models import AttemptAnswer

    session_id = round_obj.session_id
    answers = list(
        AttemptAnswer.objects.filter(session_id=session_id).order_by("created_at").select_related("question")
    )
    if not answers:
        round_obj.state = "applied"
        round_obj.applied_at = timezone.now()
        round_obj.save(update_fields=["state", "applied_at"])
        return

    est, _ = AbilityEstimate.objects.get_or_create(user_id=user_id, scope_type=run.scope_type, scope_id=run.scope_id)

    pairs = []
    for a in answers:
        q = getattr(a, "question", None)
        diff = q.difficulty if q else None
        b = compute_item_difficulty(diff)
        pairs.append((a.result, b))

    theta_before = float(est.theta)
    is_subj = run.scope_type == "subject"
    theta_after, new_n, correct_count = update_theta_from_answers(theta_before, pairs, est.n, is_subject_scope=is_subj)

    est.theta = Decimal(str(theta_after))
    est.n = new_n
    est.save(update_fields=["theta", "n", "updated_at"])

    round_obj.state = "applied"
    round_obj.theta_before = Decimal(str(round(theta_before, 3)))
    round_obj.theta_after = Decimal(str(round(theta_after, 3)))
    round_obj.answered = len(answers)
    round_obj.correct = correct_count
    round_obj.applied_at = timezone.now()
    round_obj.save(update_fields=["state", "theta_before", "theta_after", "answered", "correct", "applied_at"])

    run.rounds_applied += 1
    run.save(update_fields=["rounds_applied", "updated_at"])

    emit_adaptive_round_applied(
        user_id=user_id,
        run_id=run.id,
        scope_type=run.scope_type,
        theta_before=theta_before,
        theta_after=theta_after,
    )


def stop_adaptive(user_id: uuid.UUID, run_id: uuid.UUID) -> None:
    """Stops an active adaptive run."""
    run = AdaptiveRun.objects.get(id=run_id, user_id=user_id)
    run.status = AdaptiveRun.Status.STOPPED
    run.save(update_fields=["status", "updated_at"])


# --- Central Deletion & Export (DPDP) ----------------------------------------------------------


def delete_all_for_user(user_id: uuid.UUID) -> dict[str, int]:
    """Deletes all student-specific presets, logs, runs, and ability estimates."""
    p_cnt, _ = TestPreset.objects.filter(user_id=user_id).delete()
    l_cnt, _ = ExternalLog.objects.filter(user_id=user_id).delete()
    r_cnt, _ = AdaptiveRun.objects.filter(user_id=user_id).delete()
    e_cnt, _ = AbilityEstimate.objects.filter(user_id=user_id).delete()
    return {
        "presets_deleted": p_cnt,
        "external_logs_deleted": l_cnt,
        "adaptive_runs_deleted": r_cnt,
        "ability_estimates_deleted": e_cnt,
    }


def export_for_user(user_id: uuid.UUID) -> dict[str, Any]:
    """Exports personal study presets, external logs, and ability state."""
    presets = list(
        TestPreset.objects.filter(user_id=user_id, deleted_at__isnull=True).values(
            "name", "kind", "mode", "spec", "use_count", "last_used_at"
        )
    )
    logs = list(
        ExternalLog.objects.filter(user_id=user_id, deleted_at__isnull=True).values(
            "set__title", "taken_on", "score", "max_score", "score_pct"
        )
    )
    estimates = list(AbilityEstimate.objects.filter(user_id=user_id).values("scope_type", "scope_id", "theta", "n"))
    return {
        "presets": presets,
        "external_logs": logs,
        "ability_estimates": estimates,
    }
