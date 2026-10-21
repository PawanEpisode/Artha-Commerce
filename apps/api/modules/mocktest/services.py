"""
Services for F-08 Mock Tests and MTP.
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from django.db import IntegrityError, models, transaction
from django.utils import timezone

from core import events as core_events
from modules.practice import services as practice_services
from modules.practice.models import AttemptAnswer, Session

from . import errors
from .domain import blueprint, choice, clock, generator, integrity, keystring, palette, percentile
from .models import (
    Attempt,
    AttemptEvent,
    AttemptSection,
    AuditLog,
    ChoiceGroup,
    CohortStat,
    ExamFormat,
    Item,
    Paper,
    PaperReview,
    PaperVersion,
    Section,
    Series,
    Settings,
)


def create_paper_draft(
    actor_id: uuid.UUID,
    payload: dict[str, Any],
    *,
    client_id: uuid.UUID | None = None,
) -> Paper:
    """
    Creates a new draft paper and initial draft version v1.
    """
    with transaction.atomic():
        paper = Paper.objects.create(
            course_id=payload["course_id"],
            level_id=payload["level_id"],
            scheme_id=payload["scheme_id"],
            subject_id=payload.get("subject_id"),
            subject_key=payload.get("subject_key") or "",
            series_id=payload.get("series_id"),
            exam_term_id=payload.get("exam_term_id"),
            title=payload["title"],
            slug=payload.get("slug") or payload["title"].lower().replace(" ", "-")[:120],
            description=payload.get("description", ""),
            kind=payload.get("kind", Paper.Kind.MOCK),
            source_tag=payload.get("source_tag", Paper.SourceTag.PLATFORM),
            coaching_name=payload.get("coaching_name", ""),
            ownership=payload.get("ownership", Paper.Ownership.PLATFORM),
            rights_status=payload.get("rights_status", Paper.RightsStatus.ORIGINAL),
            visibility=payload.get("visibility", Paper.Visibility.PRIVATE),
            status=Paper.Status.DRAFT,
            delivery_mode=payload.get("delivery_mode", Paper.DeliveryMode.NATIVE),
            revision_label=payload.get("revision_label", Paper.RevisionLabel.ORIGINAL),
            revision_of_id=payload.get("revision_of_id"),
            owner_user_id=actor_id if payload.get("ownership") != Paper.Ownership.PLATFORM else None,
            client_id=client_id,
            origin_module=payload.get("origin_module", "editor"),
            external_ref=payload.get("external_ref"),
        )

        version = PaperVersion.objects.create(
            paper=paper,
            version_no=1,
            state=PaperVersion.State.DRAFT,
            total_marks=Decimal(str(payload.get("total_marks", "100.00"))),
            duration_seconds=payload.get("duration_seconds", 10800),
            reading_seconds=payload.get("reading_seconds", 0),
            upload_window_seconds=payload.get("upload_window_seconds", 0),
            section_timing=payload.get("section_timing", PaperVersion.SectionTiming.NONE),
            scoring_mode=payload.get("scoring_mode", PaperVersion.ScoringMode.RULE),
            instructions_md=payload.get("instructions_md", ""),
            created_by=actor_id,
        )

        paper.live_version_id = version.id
        paper.save(update_fields=["live_version_id"])

        AuditLog.objects.create(
            actor_id=actor_id,
            action="paper_create_draft",
            target_type="paper",
            target_id=paper.id,
            meta={"version_id": str(version.id)},
        )

    return paper


def set_blueprint(
    actor_id: uuid.UUID,
    version_id: uuid.UUID,
    *,
    sections_data: list[dict[str, Any]],
    items_data: list[dict[str, Any]],
    choice_groups_data: list[dict[str, Any]] | None = None,
) -> tuple[bool, list[str]]:
    """
    Sets sections, choice groups and items for a draft paper version.
    """
    version = PaperVersion.objects.select_related("paper").get(id=version_id)
    if version.state != PaperVersion.State.DRAFT:
        raise errors.InvalidBlueprint(["Cannot edit blueprint of a non-draft paper version."])

    is_valid, problems, total_marks = blueprint.validate_blueprint(
        sections=sections_data,
        items=items_data,
        choice_groups=choice_groups_data,
        section_timing=version.section_timing,
    )
    if not is_valid:
        raise errors.InvalidBlueprint(problems)

    with transaction.atomic():
        # Clear existing structure for this version
        Section.objects.filter(version=version).delete()

        # Re-create sections
        sec_map = {}
        for s_idx, sec in enumerate(sections_data, start=1):
            sec_obj = Section.objects.create(
                version=version,
                key=sec["key"],
                title=sec["title"],
                position=sec.get("position", s_idx),
                kind=sec.get("kind", Section.Kind.OBJECTIVE),
                duration_seconds=sec.get("duration_seconds"),
                instructions_md=sec.get("instructions_md", ""),
                marks_total=Decimal(str(sec.get("marks_total", 0))),
            )
            sec_map[sec["key"]] = sec_obj

        # Create choice groups
        grp_map = {}
        if choice_groups_data:
            for g_idx, grp in enumerate(choice_groups_data, start=1):
                sec_obj = sec_map.get(grp["section_key"])
                if sec_obj:
                    g_obj = ChoiceGroup.objects.create(
                        section=sec_obj,
                        key=grp["key"],
                        label=grp["label"],
                        required_count=grp.get("required_count", 1),
                        overflow_policy=grp.get("overflow_policy", ChoiceGroup.OverflowPolicy.BLOCK),
                        position=grp.get("position", g_idx),
                    )
                    grp_map[grp["key"]] = g_obj

        # Create items
        for it in items_data:
            sec_obj = sec_map[it["section_key"]]
            grp_obj = grp_map.get(it.get("choice_group_key"))
            Item.objects.create(
                version=version,
                section=sec_obj,
                choice_group=grp_obj,
                position=it["position"],
                display_label=it.get("display_label", f"Q.{it['position']}"),
                question_id=it["question_id"],
                question_version_id=it.get("question_version_id"),
                marks=Decimal(str(it.get("marks", "1.00"))),
                negative_marks=Decimal(str(it["negative_marks"])) if it.get("negative_marks") is not None else None,
                suggested_seconds=it.get("suggested_seconds"),
            )

        # Update version totals and content hash
        version.total_marks = total_marks
        version.item_count = len(items_data)
        version.content_hash = blueprint.compute_content_hash(items_data)
        version.save(update_fields=["total_marks", "item_count", "content_hash", "updated_at"])

    return True, []


def publish_version(
    editor_id: uuid.UUID,
    version_id: uuid.UUID,
    *,
    visibility: str = Paper.Visibility.PUBLIC,
) -> PaperVersion:
    """
    Publishes a paper version, marking it live and updating the parent paper.
    """
    with transaction.atomic():
        version = PaperVersion.objects.select_for_update().select_related("paper").get(id=version_id)
        paper = version.paper

        # Validate blueprint before publishing
        sections_data = list(version.sections.values("key", "title", "position", "kind", "duration_seconds"))
        items_data = list(
            version.items.values("position", "display_label", "question_id", "marks", "negative_marks").annotate(
                section_key=models.F("section__key"),
                choice_group_key=models.F("choice_group__key"),
            )
        )
        choice_groups_data = list(
            ChoiceGroup.objects.filter(section__version=version).values(
                "key", "label", "required_count", "overflow_policy"
            ).annotate(section_key=models.F("section__key"))
        )

        is_valid, problems, total_marks = blueprint.validate_blueprint(
            sections=sections_data,
            items=items_data,
            choice_groups=choice_groups_data,
            section_timing=version.section_timing,
        )
        if not is_valid:
            raise errors.InvalidBlueprint(problems)

        # Supersede older live versions
        PaperVersion.objects.filter(paper=paper, state=PaperVersion.State.LIVE).exclude(id=version.id).update(
            state=PaperVersion.State.SUPERSEDED
        )

        now = timezone.now()
        version.state = PaperVersion.State.LIVE
        version.published_at = now
        version.total_marks = total_marks
        version.save(update_fields=["state", "published_at", "total_marks", "updated_at"])

        paper.status = Paper.Status.LIVE
        paper.visibility = visibility
        paper.live_version_id = version.id
        if not paper.released_at:
            paper.released_at = now
        paper.save(update_fields=["status", "visibility", "live_version_id", "released_at", "updated_at"])

        AuditLog.objects.create(
            actor_id=editor_id,
            action="paper_publish",
            target_type="paper_version",
            target_id=version.id,
            meta={"paper_id": str(paper.id), "visibility": visibility},
        )

        # Emit domain event
        core_events.emit_domain_event(
            "mock_paper_published",
            {
                "paper_id": str(paper.id),
                "series_id": str(paper.series_id) if paper.series_id else None,
                "level_id": str(paper.level_id),
                "scheme_id": str(paper.scheme_id),
                "subject_key": paper.subject_key,
                "source_tag": paper.source_tag,
                "kind": paper.kind,
                "released_at": paper.released_at.isoformat() if paper.released_at else None,
            },
            actor_id=editor_id,
        )

    return version


def start_attempt(
    user_id: uuid.UUID,
    paper_id: uuid.UUID,
    *,
    version_id: uuid.UUID | None = None,
    run_mode: str = Attempt.RunMode.EXAM,
    section_scope: str | None = None,
    client_id: uuid.UUID | None = None,
    tz: str = "Asia/Kolkata",
    stop_timer: bool = False,
) -> Attempt:
    """
    Starts an exam attempt in a single atomic transaction.
    Enforces exclusivity:
      1. One live strict exam per student (DB partial unique index).
      2. One open attempt per paper per student (DB partial unique index).
    Creates underlying F-06 session via create_session_from_items.
    """
    client_id = client_id or uuid.uuid4()

    with transaction.atomic():
        paper = Paper.objects.select_related("course", "level", "scheme").get(id=paper_id)
        if paper.status != Paper.Status.LIVE and paper.owner_user_id != user_id:
            raise errors.PaperNotAvailable("This paper is not open for attempts.")

        # Resolve version
        if version_id:
            version = PaperVersion.objects.get(id=version_id, paper=paper)
        else:
            version = PaperVersion.objects.get(id=paper.live_version_id)

        # Check existing live strict exam
        if run_mode == Attempt.RunMode.EXAM:
            existing_exam = Attempt.objects.filter(
                user_id=user_id,
                run_mode=Attempt.RunMode.EXAM,
                phase__in=[Attempt.Phase.READING, Attempt.Phase.WRITING, Attempt.Phase.UPLOAD],
                deleted_at__isnull=True,
            ).first()
            if existing_exam:
                raise errors.ExamInProgress(existing_exam.id)

        # Check existing open attempt on this paper
        existing_attempt = Attempt.objects.filter(
            user_id=user_id,
            paper=paper,
            phase__in=[Attempt.Phase.INSTRUCTIONS, Attempt.Phase.READING, Attempt.Phase.WRITING, Attempt.Phase.UPLOAD],
            section_scope__isnull=True,
            deleted_at__isnull=True,
        ).first()
        if existing_attempt:
            return existing_attempt

        # Load student settings (extra time, etc.)
        settings_obj = Settings.objects.filter(user_id=user_id).first()
        extension_pct = settings_obj.time_extension_pct if settings_obj else 0
        extra_secs = clock.calculate_extra_seconds(version.duration_seconds, extension_pct)

        # Determine attempt number for this student on this paper
        attempt_count = Attempt.objects.filter(user_id=user_id, paper=paper).count()
        attempt_no = attempt_count + 1

        # Fetch paper items
        items_qs = (
            Item.objects.filter(version=version)
            .select_related("section", "choice_group")
            .order_by("position")
        )
        if section_scope:
            items_qs = items_qs.filter(section__key=section_scope)

        items_list = list(items_qs)
        if not items_list:
            raise errors.PaperNotAvailable("No questions available in paper.")

        # Prepare practice session items payload
        session_items = [
            {
                "question_id": str(it.question_id),
                "marks": float(it.marks),
                "negative_marks": float(it.negative_marks) if it.negative_marks is not None else None,
                "section_label": it.section.title,
                "position": it.position,
            }
            for it in items_list
        ]

        # Determine practice mode
        p_mode = "exam" if run_mode == Attempt.RunMode.EXAM else "timed"
        origin_kind = "mtp" if paper.source_tag == Paper.SourceTag.INSTITUTE else "mock"

        # Create session through F-06 practice service
        session_created = practice_services.create_session_from_items(
            user_id=user_id,
            mode=p_mode,
            origin=origin_kind,
            origin_ref=str(paper.id),
            items=session_items,
            time_limit_seconds=version.duration_seconds + extra_secs,
            scoring_profile="official",
            tz=tz,
            title=f"{paper.title} (Mock)",
        )

        # Build frozen layout snapshot
        layout = [
            {
                "pos": it.position,
                "item_id": str(it.id),
                "section": it.section.key,
                "group": it.choice_group.key if it.choice_group else None,
                "label": it.display_label,
            }
            for it in items_list
        ]

        attempt = Attempt.objects.create(
            user_id=user_id,
            client_id=client_id,
            session_id=session_created.session_id,
            paper=paper,
            paper_version=version,
            attempt_no=attempt_no,
            run_mode=run_mode,
            section_scope=section_scope,
            delivery_mode=paper.delivery_mode,
            phase=Attempt.Phase.INSTRUCTIONS,
            extra_seconds=extra_secs,
            time_extension_pct=extension_pct,
            layout=layout,
            lease_epoch=1,
            share_anonymous=bool(settings_obj and settings_obj.percentile_optin),
        )

        # Create AttemptSection rows
        sections = list(Section.objects.filter(version=version).order_by("position"))
        for s_idx, sec in enumerate(sections, start=1):
            sec_status = AttemptSection.Status.PENDING
            # In non-sequential, sections are accessible immediately when writing starts
            AttemptSection.objects.create(
                attempt=attempt,
                section=sec,
                position=s_idx,
                status=sec_status,
                max_score=sec.marks_total,
            )

        # Emit mock_attempt_started
        core_events.emit_domain_event(
            "mock_attempt_started",
            {
                "attempt_id": str(attempt.id),
                "paper_id": str(paper.id),
                "paper_version_id": str(version.id),
                "run_mode": attempt.run_mode,
                "source_tag": paper.source_tag,
                "kind": paper.kind,
                "duration_seconds": version.duration_seconds + extra_secs,
            },
            user_id=user_id,
        )

    return attempt


def accept_instructions(user_id: uuid.UUID, attempt_id: uuid.UUID) -> Attempt:
    """
    Student accepts instructions. Starts reading phase or writing phase.
    """
    now = timezone.now()
    with transaction.atomic():
        attempt = Attempt.objects.select_for_update().select_related("paper_version").get(
            id=attempt_id, user_id=user_id
        )

        if attempt.phase != Attempt.Phase.INSTRUCTIONS:
            return attempt  # idempotent

        attempt.instructions_accepted_at = now
        version = attempt.paper_version

        if version.reading_seconds > 0:
            attempt.phase = Attempt.Phase.READING
            attempt.reading_started_at = now
            attempt.reading_ends_at = now + timedelta(seconds=version.reading_seconds)
            attempt.save(
                update_fields=[
                    "instructions_accepted_at",
                    "phase",
                    "reading_started_at",
                    "reading_ends_at",
                    "updated_at",
                ]
            )
        else:
            _start_writing_internal(attempt, now)

    return attempt


def start_writing(user_id: uuid.UUID, attempt_id: uuid.UUID) -> Attempt:
    """
    Transitions to writing phase (e.g. skips remaining reading time).
    """
    now = timezone.now()
    with transaction.atomic():
        attempt = Attempt.objects.select_for_update().select_related("paper_version").get(
            id=attempt_id, user_id=user_id
        )
        if attempt.phase in (Attempt.Phase.INSTRUCTIONS, Attempt.Phase.READING):
            _start_writing_internal(attempt, now)
    return attempt


def _start_writing_internal(attempt: Attempt, now: datetime) -> None:
    version = attempt.paper_version
    total_duration = version.duration_seconds + attempt.extra_seconds
    writing_ends = now + timedelta(seconds=total_duration)

    attempt.phase = Attempt.Phase.WRITING
    attempt.writing_started_at = now
    attempt.writing_ends_at = writing_ends

    # Start F-06 session clock
    practice_services.start_session(attempt.user_id, attempt.session_id)

    # Open sections
    sections = list(attempt.sections.select_related("section").order_by("position"))
    if version.section_timing == PaperVersion.SectionTiming.SEQUENTIAL:
        if sections:
            first_sec = sections[0]
            first_sec.status = AttemptSection.Status.OPEN
            first_sec.opens_at = now
            dur = first_sec.section.duration_seconds or total_duration
            first_sec.closes_at = now + timedelta(seconds=dur)
            first_sec.save(update_fields=["status", "opens_at", "closes_at"])
    else:
        for s in sections:
            s.status = AttemptSection.Status.OPEN
            s.opens_at = now
            s.closes_at = writing_ends
            s.save(update_fields=["status", "opens_at", "closes_at"])

    attempt.save(
        update_fields=["phase", "writing_started_at", "writing_ends_at", "updated_at"]
    )


def acquire_lease(
    user_id: uuid.UUID,
    attempt_id: uuid.UUID,
    *,
    tab_id: str,
    label: str,
    takeover: bool = False,
) -> dict[str, Any]:
    """
    Acquires single-writer lease via atomic CAS.
    """
    now = timezone.now()
    expires_at = now + timedelta(seconds=90)

    with transaction.atomic():
        attempt = Attempt.objects.select_for_update().get(id=attempt_id, user_id=user_id)

        # Check existing holder
        if (
            not takeover
            and attempt.lease_tab_id
            and attempt.lease_tab_id != tab_id
            and attempt.lease_expires_at
            and attempt.lease_expires_at > now
        ):
            raise errors.LeaseHeld(attempt.lease_label)

        attempt.lease_epoch += 1
        attempt.lease_tab_id = tab_id
        attempt.lease_label = label[:120]
        attempt.lease_expires_at = expires_at
        attempt.save(
            update_fields=["lease_epoch", "lease_tab_id", "lease_label", "lease_expires_at", "updated_at"]
        )

        AttemptEvent.objects.create(
            attempt=attempt,
            user_id=user_id,
            type="lease_taken",
            server_ts=now,
            meta={"epoch": attempt.lease_epoch, "tab_id": tab_id, "label": label},
        )

    return {
        "epoch": attempt.lease_epoch,
        "expires_at": expires_at.isoformat(),
        "label": attempt.lease_label,
    }


def heartbeat(
    user_id: uuid.UUID,
    attempt_id: uuid.UUID,
    *,
    epoch: int,
    position: int | None = None,
    section: str | None = None,
    events_data: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Heartbeat called by the client every 30s.
    Renews lease if epoch matches, records client events, returns server clock.
    """
    now = timezone.now()
    with transaction.atomic():
        attempt = Attempt.objects.select_for_update().select_related("paper_version").get(
            id=attempt_id, user_id=user_id
        )

        # Check lease
        if attempt.lease_epoch != epoch:
            raise errors.LeaseLost(attempt.lease_label)

        attempt.lease_expires_at = now + timedelta(seconds=90)
        attempt.last_heartbeat_at = now
        if position is not None:
            attempt.last_position = position
        if section is not None:
            attempt.last_section_key = section
        attempt.save(
            update_fields=[
                "lease_expires_at",
                "last_heartbeat_at",
                "last_position",
                "last_section_key",
                "updated_at",
            ]
        )

        # Record events if under cap 500
        if events_data:
            existing_count = AttemptEvent.objects.filter(attempt=attempt).count()
            allowed = max(0, 500 - existing_count)
            events_to_create = []
            for ev in events_data[:allowed]:
                ev_type = ev.get("type", "client_event")
                ev_dur = ev.get("duration_ms")
                events_to_create.append(
                    AttemptEvent(
                        attempt=attempt,
                        user_id=user_id,
                        type=ev_type,
                        client_ts=ev.get("client_ts"),
                        server_ts=now,
                        duration_ms=ev_dur,
                        position=ev.get("position"),
                        meta=ev.get("meta", {}),
                    )
                )
                # Increment denormalized counters
                if ev_type == "focus_lost":
                    attempt.focus_lost_count += 1
                elif ev_type == "focus_regained" and ev_dur:
                    attempt.focus_lost_seconds += ev_dur // 1000
                elif ev_type == "fullscreen_exit":
                    attempt.fullscreen_exit_count += 1

            if events_to_create:
                AttemptEvent.objects.bulk_create(events_to_create)
                attempt.save(
                    update_fields=[
                        "focus_lost_count",
                        "focus_lost_seconds",
                        "fullscreen_exit_count",
                        "updated_at",
                    ]
                )

        # Derive clock state
        sec_dicts = [
            {"key": s.section.key, "status": s.status, "closes_at": s.closes_at}
            for s in attempt.sections.select_related("section")
        ]
        c_state = clock.state_at(
            phase=attempt.phase,
            instructions_accepted_at=attempt.instructions_accepted_at,
            reading_seconds=attempt.paper_version.reading_seconds,
            reading_ends_at=attempt.reading_ends_at,
            writing_started_at=attempt.writing_started_at,
            writing_ends_at=attempt.writing_ends_at,
            upload_until=attempt.upload_until,
            duration_seconds=attempt.paper_version.duration_seconds,
            extra_seconds=attempt.extra_seconds,
            paused_seconds=attempt.paused_seconds,
            is_paused=False,
            now=now,
            sections=sec_dicts,
            section_timing=attempt.paper_version.section_timing,
        )

    return {
        "server_time": now.isoformat(),
        "phase": c_state.phase,
        "remaining_ms": c_state.remaining_ms,
        "section_remaining_ms": c_state.section_remaining_ms,
        "active_section_key": c_state.active_section_key,
        "auto_submit_due": c_state.auto_submit_due,
    }


def save_answers(
    user_id: uuid.UUID,
    attempt_id: uuid.UUID,
    *,
    epoch: int,
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Saves answers in bulk (or single).
    Reads Attempt without lock (PK read), validates epoch, phase and sections.
    """
    attempt = Attempt.objects.select_related("paper_version").get(id=attempt_id, user_id=user_id)
    if attempt.lease_epoch != epoch:
        raise errors.LeaseLost(attempt.lease_label)

    now = timezone.now()
    if attempt.phase == Attempt.Phase.READING:
        raise errors.ReadingPhase()
    if attempt.phase in (Attempt.Phase.DONE, Attempt.Phase.ABANDONED):
        raise errors.AttemptClosed()

    # Pre-fetch sections
    sections_by_key = {
        s.section.key: s for s in attempt.sections.select_related("section")
    }

    results = []
    for it in items:
        pos = it["position"]
        answer_val = it.get("answer")
        flags = it.get("flags", {})

        # Find section for position from layout snapshot
        pos_layout = next((l for l in attempt.layout if l.get("pos") == pos), None)
        sec_key = pos_layout.get("section") if pos_layout else None
        sec_obj = sections_by_key.get(sec_key) if sec_key else None

        if sec_obj and sec_obj.status == AttemptSection.Status.CLOSED:
            # Check 15-second grace
            if sec_obj.closed_at and now > sec_obj.closed_at + timedelta(seconds=clock.SECTION_GRACE_SECONDS):
                results.append({"position": pos, "status": "section_closed"})
                continue

        # Save to F-06 practice service
        try:
            ans_payload = dict(answer_val) if isinstance(answer_val, dict) else {}
            if "selected_option_id" in ans_payload and "selected_option_ids" not in ans_payload:
                ans_payload["selected_option_ids"] = [ans_payload["selected_option_id"]]
            practice_services.save_answer(
                user_id=user_id,
                session_id=attempt.session_id,
                position=pos,
                answer_data=ans_payload,
                flagged=flags.get("marked_for_review", False),
            )
            results.append({"position": pos, "status": "saved"})
        except Exception as e:
            results.append({"position": pos, "status": "error", "message": str(e)})

    return results


def close_section(
    user_id: uuid.UUID,
    attempt_id: uuid.UUID,
    section_key: str,
    *,
    epoch: int,
) -> dict[str, Any]:
    """
    Closes a section early or on timeout (irreversible). Opens next in sequential timing.
    """
    now = timezone.now()
    with transaction.atomic():
        attempt = Attempt.objects.select_for_update().select_related("paper_version").get(
            id=attempt_id, user_id=user_id
        )
        if attempt.lease_epoch != epoch:
            raise errors.LeaseLost(attempt.lease_label)

        sec_qs = attempt.sections.select_related("section").order_by("position")
        target_sec = None
        next_sec = None

        sections_list = list(sec_qs)
        for idx, s in enumerate(sections_list):
            if s.section.key == section_key:
                target_sec = s
                if idx + 1 < len(sections_list):
                    next_sec = sections_list[idx + 1]
                break

        if not target_sec:
            raise errors.SectionClosed()

        target_sec.status = AttemptSection.Status.CLOSED
        target_sec.closed_at = now
        target_sec.closed_by = "student"
        target_sec.save(update_fields=["status", "closed_at", "closed_by"])

        # If sequential, open next section
        if (
            attempt.paper_version.section_timing == PaperVersion.SectionTiming.SEQUENTIAL
            and next_sec
        ):
            next_sec.status = AttemptSection.Status.OPEN
            next_sec.opens_at = now
            dur = next_sec.section.duration_seconds or 1800
            next_sec.closes_at = now + timedelta(seconds=dur)
            next_sec.save(update_fields=["status", "opens_at", "closes_at"])

    return {"closed": section_key, "next_open": next_sec.section.key if next_sec else None}


def submit_attempt(
    user_id: uuid.UUID,
    attempt_id: uuid.UUID,
    *,
    epoch: int | None = None,
    auto: bool = False,
) -> Attempt:
    """
    Submits the exam attempt (idempotent).
    Resolves choices, submits underlying practice session, computes section marks,
    evaluates integrity class and percentile eligibility, and sets phase to upload or done.
    """
    now = timezone.now()

    with transaction.atomic():
        attempt = Attempt.objects.select_for_update().select_related("paper", "paper_version").get(
            id=attempt_id, user_id=user_id
        )

        if attempt.phase in (Attempt.Phase.UPLOAD, Attempt.Phase.DONE):
            return attempt  # already submitted

        paper = attempt.paper
        version = attempt.paper_version

        # 1. Submit underlying session first so answers are graded and marks_awarded populated
        try:
            practice_services.submit_session(
                user_id=user_id,
                session_id=attempt.session_id,
                auto=auto,
            )
        except Exception:
            pass

        session = Session.objects.get(id=attempt.session_id)
        answers = list(session.answers.all())

        def _is_answered(a: AttemptAnswer) -> bool:
            return a.status in (AttemptAnswer.Status.ANSWERED, AttemptAnswer.Status.GRADED) or bool(
                a.selected_option_ids or a.numeric_value is not None or a.submission_id or a.answered_at
            )

        # Build answered map
        answered_map = {}
        for ans in answers:
            answered_map[ans.position] = {
                "answered": _is_answered(ans),
                "marks_awarded": ans.marks_awarded,
                "answered_at": ans.answered_at,
            }

        # 2. Resolve choices
        choice_groups = list(
            ChoiceGroup.objects.filter(section__version=version).prefetch_related("items")
        )
        groups_input = []
        for cg in choice_groups:
            positions = [it.position for it in cg.items.all()]
            groups_input.append({
                "key": cg.key,
                "required_count": cg.required_count,
                "overflow_policy": cg.overflow_policy,
                "positions": positions,
            })

        choice_res = choice.resolve_choices(groups_input, answered_map)
        attempt.choice_resolution = choice_res.resolution

        # 3. Copy scores from session
        attempt.score = session.score or Decimal("0.00")
        attempt.max_score = session.max_score or Decimal("0.00")

        # Deduct excluded positions from total score if they were graded
        if choice_res.excluded_positions:
            excluded_marks = sum(
                (a.marks_awarded or Decimal("0"))
                for a in answers
                if a.position in choice_res.excluded_positions
            )
            attempt.score = max(Decimal("0.00"), attempt.score - excluded_marks)

        if attempt.max_score and attempt.max_score > Decimal("0"):
            attempt.percent = round(
                Decimal("100.00") * (attempt.score or Decimal("0")) / attempt.max_score, 2
            )
        else:
            attempt.percent = Decimal("0.00")
        attempt.score_status = session.score_status

        # Comparable score (objective/auto-graded only)
        auto_graded_answers = [
            a for a in answers
            if a.result in ("correct", "incorrect", "partial", "skipped")
            and a.position not in choice_res.excluded_positions
        ]
        comp_score = sum((a.marks_awarded or Decimal("0")) for a in auto_graded_answers)
        comp_max = sum((a.marks_max or Decimal("0")) for a in auto_graded_answers)
        attempt.comparable_score = comp_score
        attempt.comparable_max = comp_max

        # Time used
        if attempt.writing_started_at:
            elapsed = int((now - attempt.writing_started_at).total_seconds())
            attempt.time_used_seconds = max(0, elapsed - attempt.paused_seconds)

        # 5. Integrity and percentile eligibility
        attempt.integrity_class = integrity.compute_integrity_class(
            section_scope=attempt.section_scope,
            run_mode=attempt.run_mode,
            time_extension_pct=attempt.time_extension_pct,
            attempt_no=attempt.attempt_no,
            replay_flagged=attempt.replay_flagged,
        )
        attempt.percentile_eligible = integrity.is_percentile_eligible(
            integrity_class=attempt.integrity_class,
            share_anonymous=attempt.share_anonymous,
            paper_visibility=paper.visibility,
            score_status=attempt.score_status or "final",
        )

        # 6. Score sections
        for a_sec in attempt.sections.select_related("section").all():
            sec_positions = [
                l["pos"] for l in attempt.layout if l.get("section") == a_sec.section.key
            ]
            sec_answers = [a for a in answers if a.position in sec_positions]

            a_sec.answered = sum(1 for a in sec_answers if _is_answered(a))
            a_sec.correct = sum(1 for a in sec_answers if a.result == "correct")
            a_sec.incorrect = sum(1 for a in sec_answers if a.result == "incorrect")
            a_sec.skipped = sum(1 for a in sec_answers if a.result == "skipped")
            a_sec.not_counted = sum(
                1 for a in sec_answers if a.position in choice_res.excluded_positions
            )
            a_sec.score = sum((a.marks_awarded or Decimal("0")) for a in sec_answers if a.position not in choice_res.excluded_positions)
            a_sec.status = AttemptSection.Status.CLOSED
            a_sec.closed_at = now
            a_sec.save()

        # 7. Next phase: upload window vs done
        if version.upload_window_seconds > 0 and not auto:
            attempt.phase = Attempt.Phase.UPLOAD
            attempt.upload_until = now + timedelta(seconds=version.upload_window_seconds)
            attempt.completion = Attempt.Completion.SUBMITTED
        else:
            attempt.phase = Attempt.Phase.DONE
            attempt.completed_at = now
            attempt.completion = (
                Attempt.Completion.AUTO_SUBMITTED if auto else Attempt.Completion.SUBMITTED
            )

        attempt.save()

        # Increment paper attempt count
        Paper.objects.filter(id=paper.id).update(attempt_count=models.F("attempt_count") + 1)

        # 8. Emit domain event
        core_events.emit_domain_event(
            "mock_attempt_completed",
            {
                "attempt_id": str(attempt.id),
                "session_id": str(attempt.session_id),
                "paper_id": str(paper.id),
                "paper_version_id": str(version.id),
                "series_id": str(paper.series_id) if paper.series_id else None,
                "source_tag": paper.source_tag,
                "kind": paper.kind,
                "run_mode": attempt.run_mode,
                "integrity_class": attempt.integrity_class,
                "completion": attempt.completion,
                "scheme_id": str(paper.scheme_id) if paper.scheme_id else None,
                "subject_key": paper.subject_key,
                "tz": "Asia/Kolkata",
                "local_date": now.strftime("%Y-%m-%d"),
                "started_at": attempt.writing_started_at.isoformat() if attempt.writing_started_at else None,
                "ended_at": now.isoformat(),
                "time_used_seconds": attempt.time_used_seconds,
                "score": float(attempt.score or 0),
                "max_score": float(attempt.max_score or 0),
                "score_status": attempt.score_status or "final",
                "comparable_score": float(attempt.comparable_score or 0),
                "comparable_max": float(attempt.comparable_max or 0),
                "answer_key_status": paper.answer_key_status,
                "attempt_no": attempt.attempt_no,
                "section_scores": [
                    {
                        "key": s.section.key,
                        "score": float(s.score or 0),
                        "max": float(s.max_score or 0),
                        "answered": s.answered,
                        "time_seconds": s.time_spent_seconds,
                    }
                    for s in attempt.sections.select_related("section")
                ],
                "by_chapter": [],
            },
            user_id=user_id,
        )

    return attempt


def parse_and_apply_key_string(paper_id: uuid.UUID, key_string: str) -> list[dict[str, Any]]:
    """
    Parses a pasted key string and previews/returns matched items.
    """
    parsed = keystring.parse_key_string(key_string)
    return parsed


def preview_blueprint_fill(
    user_id: uuid.UUID,
    spec: dict[str, Any],
) -> dict[str, Any]:
    """
    Runs builder fill dry-run and returns marks filled, shortfalls and questions count.
    """
    target_marks = Decimal(str(spec.get("marks", 100)))
    chapter_ids = spec.get("chapter_ids", [])
    weights = {str(cid): 1.0 for cid in chapter_ids}

    # Gather candidate questions from QuestionBank
    from modules.questionbank.models import Question
    from modules.questionbank.selectors import search_ids

    q_ids = search_ids(
        viewer_id=user_id,
        flt={"chapter_ids": [uuid.UUID(cid) for cid in chapter_ids if cid]},
        limit=200,
    )
    candidates = []
    for q in Question.objects.filter(id__in=q_ids).select_related("published_version"):
        v = q.published_version
        if v:
            # find chapter
            ch_id = str(chapter_ids[0]) if chapter_ids else ""
            candidates.append({
                "id": str(q.id),
                "chapter_id": ch_id,
                "marks": v.marks or Decimal("1.00"),
                "kind": q.kind,
            })

    selected, shortfalls, total_filled = generator.fill_blueprint(
        target_marks=target_marks,
        chapter_weights=weights,
        candidates=candidates,
        seed=spec.get("seed", 42),
    )

    return {
        "target_marks": float(target_marks),
        "total_filled_marks": float(total_filled),
        "selected_count": len(selected),
        "shortfalls": shortfalls,
        "selected_ids": [s["id"] for s in selected],
    }


def generate_paper(
    user_id: uuid.UUID,
    spec: dict[str, Any],
    *,
    client_id: uuid.UUID | None = None,
    start: bool = False,
    run_mode: str = Attempt.RunMode.RELAXED,
) -> dict[str, Any]:
    """
    Generates a private custom mock paper from user spec and saves it.
    Optionally starts an attempt immediately.
    """
    preview = preview_blueprint_fill(user_id, spec)

    # Create private Paper
    paper_title = spec.get("title") or f"Custom Mock ({spec.get('subject_key', 'General')})"
    paper = create_paper_draft(
        actor_id=user_id,
        payload={
            "course_id": spec["course_id"],
            "level_id": spec["level_id"],
            "scheme_id": spec["scheme_id"],
            "subject_id": spec.get("subject_id"),
            "subject_key": spec.get("subject_key", ""),
            "title": paper_title,
            "kind": Paper.Kind.GENERATED,
            "source_tag": Paper.SourceTag.USER,
            "ownership": Paper.Ownership.USER_CREATED,
            "visibility": Paper.Visibility.PRIVATE,
            "total_marks": preview["total_filled_marks"],
            "duration_seconds": spec.get("duration_seconds", 10800),
        },
        client_id=client_id,
    )

    version = paper.versions.first()
    sections_data = [{"key": "A", "title": "Questions", "position": 1, "kind": "mixed"}]
    items_data = [
        {
            "position": idx,
            "display_label": f"Q.{idx}",
            "question_id": q_id,
            "section_key": "A",
            "marks": 1.0,
        }
        for idx, q_id in enumerate(preview["selected_ids"], start=1)
    ]

    set_blueprint(user_id, version.id, sections_data=sections_data, items_data=items_data)
    publish_version(user_id, version.id, visibility=Paper.Visibility.PRIVATE)

    attempt = None
    if start:
        attempt = start_attempt(user_id, paper.id, run_mode=run_mode)

    return {
        "paper_id": str(paper.id),
        "public_id": paper.public_id,
        "attempt_id": str(attempt.id) if attempt else None,
    }


def release_key(
    editor_id: uuid.UUID,
    paper_id: uuid.UUID,
    *,
    question_version_ids: dict[uuid.UUID, uuid.UUID] | None = None,
) -> dict[str, Any]:
    """
    Releases answer key for an MTP paper. Updates answer_key_status to complete,
    and updates affected attempts.
    """
    with transaction.atomic():
        paper = Paper.objects.select_for_update().get(id=paper_id)
        now = timezone.now()
        paper.answer_key_status = Paper.AnswerKeyStatus.COMPLETE
        paper.key_released_at = now
        paper.save(update_fields=["answer_key_status", "key_released_at", "updated_at"])

        # Update affected attempts
        attempts = list(Attempt.objects.filter(paper=paper, phase__in=[Attempt.Phase.UPLOAD, Attempt.Phase.DONE]))
        for att in attempts:
            att.score_status = "final"
            att.save(update_fields=["score_status", "updated_at"])

        core_events.emit_domain_event(
            "mock_key_released",
            {
                "paper_id": str(paper.id),
                "answer_key_status": paper.answer_key_status,
                "affected_attempts": len(attempts),
            },
            actor_id=editor_id,
        )

        AuditLog.objects.create(
            actor_id=editor_id,
            action="key_release",
            target_type="paper",
            target_id=paper.id,
            meta={"affected_attempts": len(attempts)},
        )

    return {"status": "complete", "affected_attempts": len(attempts)}


def get_or_create_settings(user_id: uuid.UUID) -> Settings:
    settings_obj, _ = Settings.objects.get_or_create(user_id=user_id)
    return settings_obj


def set_settings(user_id: uuid.UUID, patch: dict[str, Any]) -> Settings:
    settings_obj = get_or_create_settings(user_id)
    fields = []
    for k, v in patch.items():
        if hasattr(settings_obj, k) and k != "user_id":
            setattr(settings_obj, k, v)
            fields.append(k)
    if fields:
        fields.append("updated_at")
        settings_obj.save(update_fields=fields)
    return settings_obj


def delete_all_for_user(user_id: uuid.UUID) -> dict[str, int]:
    """
    Deletes all personal attempts, events, settings and private papers for a user (DPDP).
    """
    with transaction.atomic():
        events_del = AttemptEvent.objects.filter(user_id=user_id).count()
        AttemptEvent.objects.filter(user_id=user_id).delete()

        attempts_del = Attempt.objects.filter(user_id=user_id).count()
        Attempt.objects.filter(user_id=user_id).delete()

        papers_del = Paper.objects.filter(owner_user_id=user_id, kind=Paper.Kind.GENERATED).count()
        Paper.objects.filter(owner_user_id=user_id, kind=Paper.Kind.GENERATED).delete()

        settings_del = Settings.objects.filter(user_id=user_id).count()
        Settings.objects.filter(user_id=user_id).delete()

    return {
        "attempts": attempts_del,
        "events": events_del,
        "generated_papers": papers_del,
        "settings": settings_del,
    }


def export_for_user(user_id: uuid.UUID) -> dict[str, Any]:
    """
    Exports user mock test history and preferences (DPDP).
    """
    attempts_qs = Attempt.objects.filter(user_id=user_id).select_related("paper")
    settings_obj = Settings.objects.filter(user_id=user_id).first()

    attempts_data = [
        {
            "id": str(a.id),
            "paper_title": a.paper.title,
            "run_mode": a.run_mode,
            "phase": a.phase,
            "score": float(a.score) if a.score is not None else None,
            "max_score": float(a.max_score) if a.max_score is not None else None,
            "percent": float(a.percent) if a.percent is not None else None,
            "completed_at": a.completed_at.isoformat() if a.completed_at else None,
        }
        for a in attempts_qs
    ]

    return {
        "user_id": str(user_id),
        "attempts": attempts_data,
        "settings": {
            "time_extension_pct": settings_obj.time_extension_pct if settings_obj else 0,
            "default_run_mode": settings_obj.default_run_mode if settings_obj else "relaxed",
            "percentile_optin": settings_obj.percentile_optin if settings_obj else False,
        },
    }
