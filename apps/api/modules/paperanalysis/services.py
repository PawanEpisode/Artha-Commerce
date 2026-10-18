"""
Editorial and student mutation services for F-11 Paper Analysis.
Reference: ERD 3.2 and PRD section 6.
"""

from __future__ import annotations

import csv
import io
import uuid
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from django.db import models, transaction
from django.utils import timezone

from core.events import emit
from modules.syllabus.models import Chapter, ExamTerm, Scheme, Subject
from modules.syllabus.selectors import scheme_for_term

from .domain.effective import (
    calculate_choice_group_attemptable,
    calculate_effective_marks,
    is_practical_format_or_nature,
)
from .domain.types import AllocationIn
from .errors import (
    AllocationSumMismatch,
    PaperConflict,
    PaperExists,
    PaperNotReady,
)
from .models import (
    Allocation,
    AllocationAudit,
    ChoiceGroup,
    Flag,
    Paper,
    PaperQuestion,
    Plan,
    PlanItem,
    Settings,
    Snapshot,
    SubjectState,
    WeightSet,
)
from .stats import refresh_paper_stats


@dataclass
class ImportReport:
    total_rows: int = 0
    questions_created: int = 0
    allocations_created: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)
    dry_run: bool = False


@dataclass
class DeleteReport:
    settings_deleted: int = 0
    snapshots_deleted: int = 0
    plans_deleted: int = 0
    flags_deleted: int = 0


def create_paper(
    editor_id: UUID,
    *,
    subject_id: UUID,
    term_code: str,
    paper_kind: str = "exam",
    series: str = "",
    entry_mode: str = "skeleton",
    origin_ref: str | None = None,
    total_marks: Decimal,
    duration_minutes: int | None = None,
    source_url: str | None = None,
) -> Paper:
    """
    Creates a new paper draft.
    FR-F11-01: duplicate (scheme_id, subject_key, term_code, paper_kind, series) is refused with 409 paper_exists.
    """
    subject = Subject.objects.select_related("scheme__level").get(id=subject_id)
    level_id = subject.scheme.level_id
    scheme_id = subject.scheme_id

    # Resolve term and scheme for term if known
    exam_term = ExamTerm.objects.filter(level_id=level_id, code=term_code).first()
    if exam_term:
        term_dto = scheme_for_term(level_id, term_code)
        if term_dto:
            scheme_id = term_dto.id

    scheme = Scheme.objects.get(id=scheme_id)

    # Check duplicate
    if Paper.objects.filter(
        scheme_id=scheme_id,
        subject_key=subject.key,
        term_code=term_code,
        paper_kind=paper_kind,
        series=series,
    ).exists():
        raise PaperExists(f"Paper for {subject.key} {term_code} {paper_kind} {series} already exists.")

    # Determine term_sort date
    if exam_term and exam_term.exam_start:
        term_sort = exam_term.exam_start
    else:
        try:
            parts = term_code.split("-")
            term_sort = date(int(parts[0]), int(parts[1]), 1)
        except Exception:
            term_sort = timezone.localdate()

    title = f"{subject.name}, {term_code}"
    if series:
        title += f" ({series})"

    paper = Paper.objects.create(
        subject=subject,
        scheme=scheme,
        level=scheme.level,
        subject_key=subject.key,
        term_code=term_code,
        exam_term=exam_term,
        term_sort=term_sort,
        paper_kind=paper_kind,
        series=series,
        title=title,
        entry_mode=entry_mode,
        origin_module="skeleton" if entry_mode == "skeleton" else "pyq",
        origin_ref=origin_ref or "",
        source_url=source_url or "",
        total_marks=total_marks,
        duration_minutes=duration_minutes or subject.exam_duration_minutes or 180,
        status=Paper.Status.DRAFT,
        created_by=editor_id,
    )

    # Ensure SubjectState row exists
    SubjectState.objects.get_or_create(
        subject_id=subject.id,
        defaults={
            "scheme_id": scheme.id,
            "subject_key": subject.key,
        },
    )

    return paper


def import_skeleton_csv(
    editor_id: UUID,
    paper_id: UUID,
    csv_content: str | Iterable[dict[str, Any]],
    *,
    dry_run: bool = False,
) -> ImportReport:
    """
    Imports skeleton CSV rows into a draft paper.
    Columns: label,position,marks,format,nature,section,choice_group,pick_n,of_m,chapter_key,topic_key,share,source_ref,tag_hint
    FR-F11-02: atomic transaction with row-level validation.
    """
    report = ImportReport(dry_run=dry_run)

    # Parse rows if string provided
    if isinstance(csv_content, str):
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
    else:
        rows = list(csv_content)

    report.total_rows = len(rows)

    with transaction.atomic():
        paper = Paper.objects.select_for_update().get(id=paper_id)
        if paper.status == Paper.Status.PUBLISHED:
            raise PaperConflict("Cannot import into an already published paper.")

        # Map active chapters of this paper's scheme
        active_chapters = {
            c.key: c
            for c in Chapter.objects.filter(subject=paper.subject, is_active=True)
        }

        # Group rows by question label
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for idx, row in enumerate(rows, start=2):  # 1-indexed header is row 1
            label = str(row.get("label", "")).strip()
            if not label:
                report.errors.append({"row": idx, "error": "Missing question label"})
                continue
            grouped[label].append(row)

        if report.errors:
            if dry_run or report.errors:
                transaction.set_rollback(True)
                return report

        choice_groups: dict[str, ChoiceGroup] = {}

        for label, q_rows in grouped.items():
            first_row = q_rows[0]
            try:
                pos = int(first_row.get("position") or len(grouped))
                marks = Decimal(str(first_row.get("marks", "0.0")))
                q_format = str(first_row.get("format") or "descriptive").strip()
                nature = str(first_row.get("nature") or "").strip() or None
                section = str(first_row.get("section") or "").strip()
                cg_label = str(first_row.get("choice_group") or "").strip()
                source_ref = str(first_row.get("source_ref") or "").strip()
                tag_hint = str(first_row.get("tag_hint") or "").strip() or None
            except Exception as e:
                report.errors.append({"question": label, "error": f"Invalid format: {e}"})
                continue

            # Choice group handling
            cg = None
            if cg_label:
                if cg_label not in choice_groups:
                    pick_n = int(first_row.get("pick_n") or 1)
                    of_m = int(first_row.get("of_m") or 1)
                    cg, _ = ChoiceGroup.objects.get_or_create(
                        paper=paper,
                        label=cg_label,
                        defaults={"pick_n": pick_n, "of_m": of_m},
                    )
                    choice_groups[cg_label] = cg
                else:
                    cg = choice_groups[cg_label]

            eff_marks = calculate_effective_marks(
                marks,
                pick_n=cg.pick_n if cg else None,
                of_m=cg.of_m if cg else None,
            )

            pq, _ = PaperQuestion.objects.update_or_create(
                paper=paper,
                label=label,
                defaults={
                    "position": pos,
                    "marks": marks,
                    "choice_group": cg,
                    "effective_marks": eff_marks,
                    "format": q_format,
                    "nature": nature or "",
                    "section_label": section,
                    "source_ref": source_ref,
                    "tag_hint": tag_hint or "",
                },
            )
            report.questions_created += 1

            # Process allocations for this question
            total_allocated = Decimal("0.0")
            for r in q_rows:
                ch_key = str(r.get("chapter_key") or "").strip()
                if not ch_key:
                    continue
                if ch_key not in active_chapters:
                    report.errors.append({"question": label, "error": f"Unknown chapter '{ch_key}'"})
                    continue
                ch = active_chapters[ch_key]

                # Share or explicit marks
                if "alloc_marks" in r and r["alloc_marks"]:
                    alloc_m = Decimal(str(r["alloc_marks"]))
                    share = (alloc_m / marks).quantize(Decimal("0.001")) if marks > 0 else Decimal("1.0")
                else:
                    share_val = Decimal(str(r.get("share") or "1.0"))
                    alloc_m = (marks * share_val).quantize(Decimal("0.5"))
                    share = share_val

                total_allocated += alloc_m
                Allocation.objects.update_or_create(
                    paper_question=pq,
                    chapter=ch,
                    defaults={
                        "subject": paper.subject,
                        "scheme": paper.scheme,
                        "subject_key": paper.subject_key,
                        "chapter_key": ch.key,
                        "marks": alloc_m,
                        "share": share,
                        "origin": Allocation.Origin.IMPORT,
                        "status": Allocation.Status.SUGGESTED,
                    },
                )
                report.allocations_created += 1

        # Recompute question count on paper
        paper.question_count = PaperQuestion.objects.filter(paper=paper).count()
        paper.save(update_fields=["question_count", "updated_at"])

        if dry_run or report.errors:
            transaction.set_rollback(True)

    return report


def set_allocations(
    editor_id: UUID,
    paper_question_id: UUID,
    rows: Sequence[AllocationIn],
    *,
    rev: int,
    origin: str = "editor",
) -> PaperQuestion:
    """
    Sets chapter allocations for a paper question.
    FR-F11-05: Sum of allocated marks must equal question marks exactly.
    Lock order: paper question row lock with optimistic rev check.
    """
    with transaction.atomic():
        pq = PaperQuestion.objects.select_for_update().select_related("paper").get(id=paper_question_id)

        if pq.rev != rev:
            raise PaperConflict(f"Question was updated by another editor (expected rev {rev}, got {pq.rev})")

        total_alloc_marks = sum((r.marks for r in rows), Decimal("0.00"))
        if total_alloc_marks != pq.marks:
            raise AllocationSumMismatch(
                f"Sum of allocations ({total_alloc_marks}m) does not equal question marks ({pq.marks}m)"
            )

        # Capture before state for audit
        old_allocs = [
            {"chapter_key": a.chapter_key, "marks": str(a.marks), "status": a.status}
            for a in pq.allocations.all()
        ]

        # Delete existing and create new
        pq.allocations.all().delete()
        for r in rows:
            chapter = Chapter.objects.get(id=r.chapter_id)
            share = (r.marks / pq.marks).quantize(Decimal("0.001"))
            Allocation.objects.create(
                paper_question=pq,
                chapter=chapter,
                topic_id=r.topic_id,
                subject_id=pq.paper.subject_id,
                scheme_id=pq.paper.scheme_id,
                subject_key=pq.paper.subject_key,
                chapter_key=chapter.key,
                marks=r.marks,
                share=share,
                status=r.status,
                origin=origin,
                rationale=r.rationale or "",
                decided_by=editor_id,
                decided_at=timezone.now(),
            )

        # Audit
        new_allocs = [
            {"chapter_key": a.chapter_key, "marks": str(a.marks), "status": a.status}
            for a in pq.allocations.all()
        ]
        AllocationAudit.objects.create(
            paper_question_id=pq.id,
            action="edit",
            actor_id=editor_id,
            before=old_allocs,
            after=new_allocs,
        )

        pq.rev += 1
        pq.alloc_state = PaperQuestion.AllocState.SUGGESTED
        pq.save(update_fields=["rev", "alloc_state", "updated_at"])

        # If paper was published, return to in_review (FR-F11-10)
        paper = pq.paper
        if paper.status == Paper.Status.PUBLISHED:
            paper.status = Paper.Status.IN_REVIEW
            paper.rev += 1
            paper.save(update_fields=["status", "rev", "updated_at"])
            refresh_paper_stats(paper.id)

    return pq


def confirm_question(
    editor_id: UUID,
    paper_question_id: UUID,
    *,
    rev: int,
) -> PaperQuestion:
    """
    Confirms all allocations of a question.
    FR-F11-07: Human confirmation required to count in statistics.
    """
    with transaction.atomic():
        pq = PaperQuestion.objects.select_for_update().select_related("paper").get(id=paper_question_id)

        if pq.rev != rev:
            raise PaperConflict(f"Question was updated by another editor (expected rev {rev}, got {pq.rev})")

        allocs = list(pq.allocations.all())
        total_m = sum((a.marks for a in allocs), Decimal("0.00"))
        if total_m != pq.marks:
            raise AllocationSumMismatch(f"Allocations sum to {total_m}m, expected {pq.marks}m")

        now = timezone.now()
        for a in allocs:
            a.status = Allocation.Status.CONFIRMED
            a.decided_by = editor_id
            a.decided_at = now
            a.save(update_fields=["status", "decided_by", "decided_at", "updated_at"])

        pq.alloc_state = PaperQuestion.AllocState.CONFIRMED
        pq.confirmed_by = editor_id
        pq.confirmed_at = now
        pq.rev += 1
        pq.save(update_fields=["alloc_state", "confirmed_by", "confirmed_at", "rev", "updated_at"])

        AllocationAudit.objects.create(
            paper_question_id=pq.id,
            action="confirm",
            actor_id=editor_id,
            after=[{"chapter_key": a.chapter_key, "marks": str(a.marks)} for a in allocs],
        )

        # Update paper confirmed marks
        paper = pq.paper
        confirmed_sum = (
            PaperQuestion.objects.filter(paper=paper, alloc_state=PaperQuestion.AllocState.CONFIRMED)
            .aggregate(s=models.Sum("marks"))
        )["s"] or Decimal("0.0")
        paper.confirmed_marks = confirmed_sum
        paper.save(update_fields=["confirmed_marks", "updated_at"])

    return pq


def publish_paper(
    editor_id: UUID,
    paper_id: UUID,
    *,
    rev: int,
    exception_note: str | None = None,
) -> Paper:
    """
    Publishes a paper and refreshes statistics.
    Lock order: paper, then subjectstate.
    FR-F11-09: 100% confirmed marks, or >= 95% with an exception note.
    """
    with transaction.atomic():
        paper = Paper.objects.select_for_update().get(id=paper_id)
        if paper.rev != rev:
            raise PaperConflict(f"Paper conflict: expected rev {rev}, got {paper.rev}")

        # Guard: check 95% threshold
        threshold = paper.total_marks * Decimal("0.95")
        if paper.confirmed_marks < threshold:
            raise PaperNotReady(
                f"Paper only has {paper.confirmed_marks}m confirmed out of {paper.total_marks}m "
                f"(requires at least 95%: {threshold}m)"
            )

        if paper.confirmed_marks < paper.total_marks and not exception_note:
            raise PaperNotReady("Publishing below 100% requires an exception note.")

        paper.is_limited = bool(paper.confirmed_marks < paper.total_marks)
        paper.exception_note = exception_note or ""
        paper.status = Paper.Status.PUBLISHED
        paper.published_by = editor_id
        paper.published_at = timezone.now()
        paper.rev += 1

        # Calculate pattern totals
        questions = paper.questions.all()
        m_obj = Decimal("0.0")
        m_desc = Decimal("0.0")
        m_theory = Decimal("0.0")
        m_practical = Decimal("0.0")
        for q in questions:
            if q.format in ("mcq", "case_mcq"):
                m_obj += q.effective_marks
            else:
                m_desc += q.effective_marks
            if is_practical_format_or_nature(q.format, q.nature):
                m_practical += q.effective_marks
            else:
                m_theory += q.effective_marks

        paper.marks_objective = m_obj
        paper.marks_descriptive = m_desc
        paper.marks_theory = m_theory
        paper.marks_practical = m_practical

        # Optional and attemptable marks
        cgs = paper.choice_groups.all()
        optional_offered = Decimal("0.0")
        attemptable = Decimal("0.0")
        grouped_q_ids = set()

        for cg in cgs:
            cg_qs = [q.marks for q in cg.questions.all()]
            optional_offered += sum(cg_qs)
            attemptable += calculate_choice_group_attemptable(cg.pick_n, cg.of_m, cg_qs)
            grouped_q_ids.update(cg.questions.values_list("id", flat=True))

        for q in questions:
            if q.id not in grouped_q_ids:
                attemptable += q.marks

        paper.marks_optional_offered = optional_offered
        paper.marks_attemptable = attemptable
        paper.save()

        # Refresh stats with subject state locked
        refresh_paper_stats(paper.id)

        # Emit event
        chapter_ids = list(
            Allocation.objects.filter(paper_question__paper=paper, status=Allocation.Status.CONFIRMED)
            .values_list("chapter_id", flat=True)
            .distinct()
        )
        state = SubjectState.objects.get(subject_id=paper.subject_id)

        emit(
            "paperanalysis_paper_published",
            paper_id=str(paper.id),
            subject_key=paper.subject_key,
            scheme_id=str(paper.scheme_id),
            term_code=paper.term_code,
            paper_kind=paper.paper_kind,
            chapter_ids=[str(cid) for cid in chapter_ids],
            is_limited=paper.is_limited,
            stats_version=state.stats_version,
        )

    return paper


def unpublish_paper(editor_id: UUID, paper_id: UUID, *, reason: str) -> Paper:
    """
    Unpublishes a paper and refreshes statistics to exclude it.
    """
    with transaction.atomic():
        paper = Paper.objects.select_for_update().get(id=paper_id)
        paper.status = Paper.Status.UNPUBLISHED
        paper.rev += 1
        paper.save(update_fields=["status", "rev", "updated_at"])

        refresh_paper_stats(paper.id)

        emit(
            "paperanalysis_paper_unpublished",
            paper_id=str(paper.id),
            subject_key=paper.subject_key,
            reason=reason,
        )

    return paper


def decide_qa(
    editor_id: UUID,
    paper_question_id: UUID,
    *,
    agree: bool,
    note: str = "",
) -> PaperQuestion:
    """
    Records second-review QA outcome for sampled allocations.
    FR-F11-11.
    """
    with transaction.atomic():
        pq = PaperQuestion.objects.select_for_update().get(id=paper_question_id)
        pq.qa_by = editor_id
        pq.qa_state = PaperQuestion.QaState.AGREED if agree else PaperQuestion.QaState.DISPUTED
        pq.rev += 1
        pq.save(update_fields=["qa_state", "qa_by", "rev", "updated_at"])

        AllocationAudit.objects.create(
            paper_question_id=pq.id,
            action="qa_agree" if agree else "qa_disagree",
            actor_id=editor_id,
            reason=note,
        )

    return pq


def flag(
    user_id: UUID | None,
    target_type: str,
    target_id: UUID,
    note: str,
    source: str = "student",
) -> Flag:
    """Submits a student flag or records a system drift alert."""
    return Flag.objects.create(
        user_id=user_id,
        source=source,
        target_type=target_type,
        target_id=target_id,
        note=note[:500],
    )


def delete_all_for_user(user_id: UUID) -> DeleteReport:
    """DPDP Act 2023: deletes all personal records for a user."""
    with transaction.atomic():
        st_del, _ = Settings.objects.filter(user_id=user_id).delete()
        sn_del, _ = Snapshot.objects.filter(user_id=user_id).delete()
        pl_del, _ = Plan.objects.filter(user_id=user_id).delete()
        fl_del, _ = Flag.objects.filter(user_id=user_id, source=Flag.Source.STUDENT).delete()

    return DeleteReport(
        settings_deleted=st_del,
        snapshots_deleted=sn_del,
        plans_deleted=pl_del,
        flags_deleted=fl_del,
    )


def export_for_user(user_id: UUID) -> dict[str, Any]:
    """DPDP Act 2023: exports all personal records for a user."""
    settings = Settings.objects.filter(user_id=user_id).first()
    plans = Plan.objects.filter(user_id=user_id).prefetch_related("items")
    flags = Flag.objects.filter(user_id=user_id, source=Flag.Source.STUDENT)

    return {
        "user_id": str(user_id),
        "settings": {
            "window": settings.window if settings else 6,
            "include_practice": settings.include_practice if settings else False,
            "include_older": settings.include_older if settings else True,
            "show_reasons_default": settings.show_reasons_default if settings else True,
            "hide_tiers": settings.hide_tiers if settings else False,
        } if settings else None,
        "plans": [
            {
                "id": str(p.id),
                "status": p.status,
                "days": p.days,
                "hours_per_day": str(p.hours_per_day),
                "start_date": p.start_date.isoformat(),
                "end_date": p.end_date.isoformat(),
                "summary": p.summary,
                "items": [
                    {
                        "chapter_key": it.chapter_key,
                        "planned_date": it.planned_date.isoformat(),
                        "minutes": it.minutes,
                        "mode": it.mode,
                        "state": it.state,
                    }
                    for it in p.items.all()
                ],
            }
            for p in plans
        ],
        "flags": [
            {
                "target_type": f.target_type,
                "target_id": str(f.target_id),
                "note": f.note,
                "status": f.status,
                "created_at": f.created_at.isoformat(),
            }
            for f in flags
        ],
    }


def preview_plan(
    user_id: UUID,
    *,
    enrollment_id: UUID | None = None,
    days: int,
    hours_per_day: float,
    subject_keys: Sequence[str] | None = None,
    balance_subjects: bool = False,
) -> Any:
    """
    Generates a plan preview using the greedy planner without committing to database.
    """
    from .domain.planner import (
        PlannerChapterCandidate,
        PlannerPaceContext,
        plan_n_days,
    )
    from .domain.types import PlanInputs
    from .selectors import chapter_priority

    priority = chapter_priority(user_id, enrollment_id=enrollment_id)
    all_subjects = priority.subjects
    active_keys = set(subject_keys or [s.subject_key for s in all_subjects])

    candidates: list[PlannerChapterCandidate] = []
    for s in all_subjects:
        if s.subject_key not in active_keys:
            continue
        for ch in s.chapters:
            # Base minutes estimate: 180 standard or based on marks
            est_min = max(60, int(ch.expected_marks * 20))
            candidates.append(
                PlannerChapterCandidate(
                    chapter_id=ch.chapter_id,
                    chapter_key=ch.chapter_key,
                    subject_key=s.subject_key,
                    name=ch.name,
                    sort_order=ch.rank,
                    expected_marks=ch.expected_marks,
                    coverage_fraction=float(ch.student.get("coverage_pct", 0)) / 100.0,
                    accuracy=float(ch.student.get("accuracy", 0.5)),
                    base_minutes=est_min,
                    effort_basis="standard_estimate",
                    confidence=ch.confidence,
                )
            )

    inputs = PlanInputs(
        days=days,
        hours_per_day=hours_per_day,
        subject_keys=list(active_keys),
        balance_subjects=balance_subjects,
    )

    return plan_n_days(inputs, candidates, PlannerPaceContext(pace=1.0, pace_basis="standard"))


def adopt_plan(
    user_id: UUID,
    *,
    client_id: UUID,
    enrollment_id: UUID | None = None,
    days: int,
    hours_per_day: float,
    subject_keys: Sequence[str] | None = None,
    balance_subjects: bool = False,
    start_date: date | None = None,
    preview: Any | None = None,
) -> Plan:
    """
    Adopts a plan preview into an active plan.
    Idempotent on (user_id, client_id).
    Supersedes any previous active plan for the user.
    """
    existing = Plan.objects.filter(user_id=user_id, client_id=client_id).first()
    if existing:
        return existing

    if preview is None:
        preview = preview_plan(
            user_id,
            enrollment_id=enrollment_id,
            days=days,
            hours_per_day=hours_per_day,
            subject_keys=subject_keys,
            balance_subjects=balance_subjects,
        )

    s_date = start_date or timezone.localdate()
    e_date = s_date + timedelta(days=days - 1)
    active_ws = WeightSet.objects.filter(status=WeightSet.Status.ACTIVE).first()

    with transaction.atomic():
        # Supersede any active plan
        Plan.objects.filter(user_id=user_id, status=Plan.Status.ACTIVE).update(
            status=Plan.Status.SUPERSEDED,
            ended_at=timezone.now(),
        )

        plan = Plan.objects.create(
            user_id=user_id,
            enrollment_id=enrollment_id or UUID("00000000-0000-0000-0000-000000000000"),
            client_id=client_id,
            status=Plan.Status.ACTIVE,
            days=days,
            hours_per_day=Decimal(str(round(hours_per_day, 1))),
            start_date=s_date,
            end_date=e_date,
            subject_keys=list(subject_keys or []),
            balance_subjects=balance_subjects,
            snapshot_id=preview.snapshot_id,
            weightset=active_ws,
            summary={
                "budget_hours": preview.budget_hours,
                "hours_used": preview.hours_used,
                "covered_share": preview.covered_share,
                "items_count": len(preview.items),
            },
        )

        # Distribute items across days
        # Each day gets up to hours_per_day * 60 minutes
        day_limit_min = int(hours_per_day * 60)
        current_day_idx = 0
        current_day_min = 0

        for pos, item in enumerate(preview.items):
            if current_day_min + item.minutes > day_limit_min and current_day_idx < (days - 1):
                current_day_idx += 1
                current_day_min = 0

            p_date = s_date + timedelta(days=current_day_idx)
            current_day_min += item.minutes

            PlanItem.objects.create(
                plan=plan,
                user_id=user_id,
                chapter_id=item.chapter_id,
                subject_key=item.subject_key,
                chapter_key=item.chapter_key,
                planned_date=p_date,
                position=pos,
                minutes=item.minutes,
                mode=PlanItem.Mode.FULL if item.mode == "full" else PlanItem.Mode.KEY_POINTS,
                expected_gain=Decimal(str(round(item.expected_gain, 2))),
                mph=Decimal(str(round(item.mph, 2))),
                state=PlanItem.State.PLANNED,
            )

        emit(
            "paperanalysis_plan_adopted",
            plan_id=str(plan.id),
            user_id=str(user_id),
            days=plan.days,
            hours_per_day=float(plan.hours_per_day),
            covered_share=float(preview.covered_share),
        )

    return plan


def replan(
    user_id: UUID,
    plan_id: UUID,
    *,
    days_remaining: int,
    hours_per_day: float,
) -> Plan:
    """
    Replans the remaining uncompleted items of an active plan over new days.
    """
    with transaction.atomic():
        old_plan = Plan.objects.select_for_update().get(id=plan_id, user_id=user_id)
        old_plan.status = Plan.Status.SUPERSEDED
        old_plan.ended_at = timezone.now()
        old_plan.save(update_fields=["status", "ended_at", "updated_at"])

        new_client_id = UUID(int=uuid.uuid4().int)
        new_plan = adopt_plan(
            user_id=user_id,
            client_id=new_client_id,
            enrollment_id=old_plan.enrollment_id,
            days=days_remaining,
            hours_per_day=hours_per_day,
            subject_keys=old_plan.subject_keys,
            balance_subjects=old_plan.balance_subjects,
        )
        new_plan.parent_plan = old_plan
        new_plan.save(update_fields=["parent_plan", "updated_at"])

    return new_plan


def update_plan_item(
    user_id: UUID,
    item_id: UUID,
    *,
    state: str,
    planned_date: date | None = None,
) -> PlanItem:
    """
    Updates the state or planned date of a plan item.
    """
    with transaction.atomic():
        item = PlanItem.objects.select_for_update().get(id=item_id, user_id=user_id)
        if state == PlanItem.State.DONE and item.state != PlanItem.State.DONE:
            item.done_at = timezone.now()
        item.state = state

        if planned_date and planned_date != item.planned_date:
            item.moved_from = item.planned_date
            item.planned_date = planned_date

        item.save()

    return item


def end_plan(user_id: UUID, plan_id: UUID) -> Plan:
    """
    Ends an active plan.
    """
    with transaction.atomic():
        plan = Plan.objects.select_for_update().get(id=plan_id, user_id=user_id)
        plan.status = Plan.Status.ENDED
        plan.ended_at = timezone.now()
        plan.save(update_fields=["status", "ended_at", "updated_at"])
    return plan
