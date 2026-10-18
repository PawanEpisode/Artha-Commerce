"""
Derived statistics refresh and rebuild service for F-11.
Enforces Postgres row locks on subjectstate and idempotent upserts.
Reference: ERD 3.5.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from decimal import Decimal
from uuid import UUID

from django.db import transaction

from core.events import emit
from modules.syllabus.selectors import chapter_map_edges, chapter_map_stamp

from .domain.aggregate import SittingMark, calculate_chapter_aggregates
from .domain.comparability import evaluate_comparability
from .domain.status import determine_data_status
from .models import (
    Allocation,
    BacktestRun,
    ChapterAggregate,
    Paper,
    SubjectState,
    TermChapterStat,
)

logger = logging.getLogger(__name__)


def refresh_paper_stats(paper_id: UUID) -> None:
    """
    Refreshes statistics for a single paper and recomputes chapter aggregates.
    Lock order: paper, then subjectstate.
    """
    with transaction.atomic():
        paper = Paper.objects.select_for_update().get(id=paper_id)
        state, _ = SubjectState.objects.select_for_update().get_or_create(
            subject_id=paper.subject_id,
            defaults={
                "scheme_id": paper.scheme_id,
                "subject_key": paper.subject_key,
            },
        )

        if paper.status == Paper.Status.PUBLISHED and paper.include_in_stats:
            _sync_term_chapter_stats_for_paper(paper, state.stats_version + 1)
        else:
            TermChapterStat.objects.filter(paper=paper).delete()

        # Recompute aggregates for this subject and scheme
        _recompute_chapter_aggregates_for_subject(paper.subject_id, paper.scheme_id, state.stats_version + 1)

        # Update subjectstate counters & status
        state.stats_version += 1
        published_papers = Paper.objects.filter(
            subject_id=paper.subject_id,
            status=Paper.Status.PUBLISHED,
            include_in_stats=True,
        )
        state.papers_published = published_papers.count()
        state.exam_papers_published = published_papers.filter(paper_kind=Paper.PaperKind.EXAM).count()
        has_limited = published_papers.filter(is_limited=True).exists()

        latest_done_backtest = BacktestRun.objects.filter(
            subject_id=paper.subject_id,
            status=BacktestRun.Status.DONE,
        ).order_by("-created_at").first()

        lift_val = float(latest_done_backtest.lift) if latest_done_backtest and latest_done_backtest.lift is not None else None
        data_status, withheld_reason = determine_data_status(
            papers_published=state.papers_published,
            exam_papers_published=state.exam_papers_published,
            has_limited_paper=has_limited,
            backtest_lift=lift_val,
            admin_withheld=(state.withheld_reason == "editor_override"),
        )
        state.data_status = data_status
        if withheld_reason:
            state.withheld_reason = withheld_reason
        state.save()

        emit(
            "paperanalysis_stats_refreshed",
            subject_key=paper.subject_key,
            scheme_ids=[str(paper.scheme_id)],
            stats_version=state.stats_version,
        )


def _sync_term_chapter_stats_for_paper(paper: Paper, stats_version: int) -> None:
    """Computes and upserts TermChapterStat rows for a published paper."""
    # Group confirmed allocations of this paper by chapter
    allocations = (
        Allocation.objects.filter(
            paper_question__paper=paper,
            status=Allocation.Status.CONFIRMED,
        )
        .select_related("paper_question", "chapter")
    )

    by_chapter: dict[UUID, dict] = defaultdict(
        lambda: {
            "marks_offered": Decimal("0.00"),
            "marks_effective": Decimal("0.00"),
            "marks_compulsory": Decimal("0.00"),
            "marks_objective": Decimal("0.00"),
            "marks_descriptive": Decimal("0.00"),
            "marks_theory": Decimal("0.00"),
            "marks_practical": Decimal("0.00"),
            "question_count": 0,
            "chapter_key": "",
        }
    )

    for alloc in allocations:
        pq = alloc.paper_question
        cid = alloc.chapter_id
        entry = by_chapter[cid]
        entry["chapter_key"] = alloc.chapter_key

        entry["marks_offered"] += alloc.marks
        # Effective marks ratio
        pq_effective = pq.effective_marks
        share_ratio = alloc.share if alloc.share > Decimal("0") else Decimal("1.0")
        eff = (pq_effective * share_ratio).quantize(Decimal("0.01"))
        entry["marks_effective"] += eff
        entry["question_count"] += 1

        if not pq.choice_group_id:
            entry["marks_compulsory"] += eff

        if pq.format in ("mcq", "case_mcq"):
            entry["marks_objective"] += eff
        else:
            entry["marks_descriptive"] += eff

        if pq.format == "practical" or (pq.nature and pq.nature.lower() in ("practical", "application")):
            entry["marks_practical"] += eff
        else:
            entry["marks_theory"] += eff

    # Upsert each chapter
    allocated_chapter_ids = set()
    for cid, stats in by_chapter.items():
        allocated_chapter_ids.add(cid)
        TermChapterStat.objects.update_or_create(
            paper=paper,
            chapter_id=cid,
            defaults={
                "scheme_id": paper.scheme_id,
                "subject_key": paper.subject_key,
                "chapter_key": stats["chapter_key"],
                "term_code": paper.term_code,
                "term_sort": paper.term_sort,
                "paper_kind": paper.paper_kind,
                "marks_offered": stats["marks_offered"],
                "marks_effective": stats["marks_effective"],
                "marks_compulsory": stats["marks_compulsory"],
                "marks_objective": stats["marks_objective"],
                "marks_descriptive": stats["marks_descriptive"],
                "marks_theory": stats["marks_theory"],
                "marks_practical": stats["marks_practical"],
                "question_count": stats["question_count"],
                "stats_version": stats_version,
            },
        )

    # Delete rows whose chapter is no longer allocated
    TermChapterStat.objects.filter(paper=paper).exclude(chapter_id__in=allocated_chapter_ids).delete()


def _recompute_chapter_aggregates_for_subject(subject_id: UUID, scheme_id: UUID, stats_version: int) -> None:
    """Recomputes ChapterAggregate default view (w6-p0-o1) for chapters of the scheme."""
    from modules.syllabus.models import Chapter

    # Get active chapters of subject in this scheme
    chapters = Chapter.objects.filter(subject_id=subject_id, is_active=True)
    if not chapters.exists():
        return

    # Find last 6 exam sittings for this subject (window = 6, practice = 0, older = 1)
    published_papers = (
        Paper.objects.filter(
            subject_id=subject_id,
            status=Paper.Status.PUBLISHED,
            include_in_stats=True,
            paper_kind=Paper.PaperKind.EXAM,
        )
        .order_by("-term_sort")[:6]
    )
    paper_ids = list(published_papers.values_list("id", flat=True))

    term_stats = (
        TermChapterStat.objects.filter(paper_id__in=paper_ids)
        .select_related("paper")
        .order_by("-term_sort")
    )
    stats_by_chapter: dict[UUID, list[SittingMark]] = defaultdict(list)
    for ts in term_stats:
        stats_by_chapter[ts.chapter_id].append(
            SittingMark(
                term_code=ts.term_code,
                effective_marks=ts.marks_effective,
                is_asked=(ts.marks_effective > Decimal("0")),
            )
        )

    # Load chapter map edges for older comparability if needed
    edges = chapter_map_edges(to_scheme_id=scheme_id)

    for ch in chapters:
        sittings = stats_by_chapter.get(ch.id, [])
        agg_res = calculate_chapter_aggregates(sittings)

        # Check comparability
        comp = evaluate_comparability(ch.id, scheme_id, scheme_id, edges)

        ChapterAggregate.objects.update_or_create(
            chapter=ch,
            view_key="w6-p0-o1",
            defaults={
                "scheme_id": scheme_id,
                "subject_key": ch.subject.key,
                "chapter_key": ch.key,
                "papers_considered": agg_res.papers_considered,
                "asked_n": agg_res.asked_n,
                "avg_effective": agg_res.avg_effective,
                "avg_when_asked": agg_res.avg_when_asked,
                "max_effective": agg_res.max_effective,
                "last_asked_term_code": agg_res.last_asked_term_code,
                "trend": agg_res.trend,
                "comparability": comp.status,
                "carried_papers": 0,
                "weight_basis": "inferred",
                "stats_version": stats_version,
                "inputs_hash": chapter_map_stamp(scheme_id),
            },
        )
