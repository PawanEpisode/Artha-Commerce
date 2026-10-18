"""
Selectors (read model queries) for F-11 Paper Analysis and Recommendations.
All consumer queries and UI reads go through this layer.
Reference: ERD 3.6, 3.7 and PRD section 6.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Sequence
from dataclasses import asdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from django.db.models import Prefetch
from django.utils import timezone

from modules.coverage.selectors import exam_context
from modules.practice.selectors import accuracy as practice_accuracy
from modules.questionbank.selectors import duplicate_cluster_ids
from modules.syllabus.models import Subject

from .domain.explain import (
    DISCLAIMER_KEY,
)
from .domain.params import DEFAULT_PARAMS
from .domain.scoring import (
    ChapterInput,
    PaperSittingInput,
    SubjectScoringInput,
    score_subject,
)
from .domain.types import (
    AskedSummary,
    PriorityView,
    ReasonPayload,
    ScoredChapter,
    SubjectPriority,
)
from .models import (
    ChapterAggregate,
    Paper,
    PaperQuestion,
    Plan,
    PlanItem,
    Settings,
    Snapshot,
    SubjectState,
    TermChapterStat,
    TopicStat,
    WeightSet,
)


def get_or_create_settings(user_id: UUID) -> Settings:
    settings, _ = Settings.objects.get_or_create(user_id=user_id)
    return settings


def subject_statuses(user_id: UUID, enrollment_id: UUID | None = None) -> list[dict[str, Any]]:
    """
    Returns data readiness and paper availability status for subjects.
    """
    subjects = Subject.objects.filter(is_active=True).select_related("scheme")
    results = []

    for sub in subjects:
        state = SubjectState.objects.filter(subject_id=sub.id).first()
        status = state.data_status if state else "insufficient"
        papers_pub = state.papers_published if state else 0
        exam_papers = state.exam_papers_published if state else 0
        stats_ver = state.stats_version if state else 0

        ranking = "available" if status in ("ready", "limited") else "withheld"

        results.append({
            "subject_id": str(sub.id),
            "subject_key": sub.key,
            "name": sub.name,
            "data_status": status,
            "ranking": ranking,
            "papers_published": papers_pub,
            "exam_papers_published": exam_papers,
            "stats_version": stats_ver,
        })

    return results


def chapter_stats(
    subject_id: UUID,
    window: int = 6,
    include_practice: bool = False,
    include_older: bool = True,
) -> list[dict[str, Any]]:
    """
    Returns chapter statistics for a given subject and window.
    """
    subject = Subject.objects.filter(pk=subject_id).first()
    if not subject:
        return []

    view_key = f"w{window}-p{1 if include_practice else 0}-o{1 if include_older else 0}"
    aggs = ChapterAggregate.objects.filter(
        subject_key=subject.key,
        view_key=view_key,
    ).select_related("chapter")

    if not aggs.exists():
        aggs = ChapterAggregate.objects.filter(
            subject_key=subject.key,
        ).select_related("chapter")

    results = []
    for agg in aggs:
        results.append({
            "chapter_id": str(agg.chapter_id),
            "chapter_key": agg.chapter_key,
            "name": agg.chapter.name if agg.chapter else agg.chapter_key,
            "section": getattr(agg.chapter, "section", "") or "",
            "papers_considered": agg.papers_considered,
            "asked_n": agg.asked_n,
            "avg_effective": float(agg.avg_effective),
            "avg_when_asked": float(agg.avg_when_asked) if agg.avg_when_asked is not None else None,
            "max_effective": float(agg.max_effective) if agg.max_effective is not None else None,
            "last_asked_term_code": agg.last_asked_term_code,
            "share_of_marks": float(agg.share_of_marks) if agg.share_of_marks is not None else None,
            "trend": float(agg.trend) if agg.trend is not None else None,
            "comparability": agg.comparability,
            "carried_papers": agg.carried_papers,
            "weight_basis": agg.weight_basis,
        })

    return sorted(results, key=lambda x: -x["avg_effective"])


def patterns(subject_id: UUID, window: int = 6) -> dict[str, Any]:
    """
    Returns paper structural patterns (formats, nature, compulsory vs optional marks).
    """
    papers = list(
        Paper.objects.filter(
            subject_id=subject_id,
            status=Paper.Status.PUBLISHED,
            include_in_stats=True,
        )
        .order_by("-term_sort")[:window]
        .prefetch_related("questions__choice_group")
    )

    if not papers:
        return {
            "papers_considered": 0,
            "avg_total_marks": 0.0,
            "avg_attemptable_marks": 0.0,
            "avg_optional_marks": 0.0,
            "formats": {},
            "sections": [],
        }

    total_marks_sum = sum(p.total_marks for p in papers)
    attemptable_sum = sum(p.marks_attemptable for p in papers)
    optional_sum = sum(p.marks_optional_offered for p in papers)
    n = len(papers)

    format_marks: dict[str, Decimal] = {}
    for p in papers:
        for q in p.questions.all():
            fmt = q.format or "descriptive"
            format_marks[fmt] = format_marks.get(fmt, Decimal("0.0")) + q.marks

    total_fmt_m = sum(format_marks.values(), Decimal("0.01"))
    format_pcts = {fmt: round(float(m / total_fmt_m) * 100, 1) for fmt, m in format_marks.items()}

    return {
        "papers_considered": n,
        "avg_total_marks": round(float(total_marks_sum / n), 1),
        "avg_attemptable_marks": round(float(attemptable_sum / n), 1),
        "avg_optional_marks": round(float(optional_sum / n), 1),
        "formats": format_pcts,
    }


def chapter_history(chapter_id: UUID, window: int = 12) -> list[dict[str, Any]]:
    """
    Detailed historical sitting breakdown for a single chapter.
    """
    stats = (
        TermChapterStat.objects.filter(chapter_id=chapter_id)
        .select_related("paper")
        .order_by("-term_sort")[:window]
    )

    history = []
    for s in stats:
        history.append({
            "term_code": s.term_code,
            "paper_title": s.paper.title if s.paper else "",
            "paper_kind": s.paper_kind,
            "marks_offered": float(s.marks_offered),
            "marks_effective": float(s.marks_effective),
            "marks_compulsory": float(s.marks_compulsory),
            "question_count": s.question_count,
            "marks_theory": float(s.marks_theory),
            "marks_practical": float(s.marks_practical),
            "marks_objective": float(s.marks_objective),
            "marks_descriptive": float(s.marks_descriptive),
        })

    return history


def chapter_priority(
    user_id: UUID,
    enrollment_id: UUID | None = None,
    subject_key: str | None = None,
    force_refresh: bool = False,
) -> PriorityView:
    """
    Computes priority view for student recommendations with snapshot caching.
    Pure scoring algorithm (ps-1) + reason explanation.
    """
    settings = get_or_create_settings(user_id)
    ctx = exam_context(user_id, enrollment_id)
    days_left = ctx.days_left if ctx else 45

    # Check active weightset
    active_ws = WeightSet.objects.filter(status=WeightSet.Status.ACTIVE).first()
    engine_ver = active_ws.engine_version if active_ws else "ps-1"
    ws_id = active_ws.id if active_ws else UUID("00000000-0000-0000-0000-000000000000")

    # Build inputs hash for caching
    hash_str = f"{user_id}:{settings.window}:{settings.include_practice}:{settings.include_older}:{days_left}:{ws_id}:{subject_key}"
    inputs_hash = hashlib.sha256(hash_str.encode()).hexdigest()

    if not force_refresh:
        cached = (
            Snapshot.objects.filter(
                user_id=user_id,
                scope_key=subject_key or "all",
                inputs_hash=inputs_hash,
                expires_at__gt=timezone.now(),
            )
            .order_by("-created_at")
            .first()
        )
        if cached:
            try:
                data = cached.results
                if data.get("v") == 1:
                    sub_views = []
                    for s in data.get("subjects", []):
                        ch_views = [
                            ScoredChapter(
                                chapter_id=UUID(c["chapter_id"]),
                                chapter_key=c["chapter_key"],
                                name=c["name"],
                                rank=c["rank"],
                                score=c["score"],
                                tier=c["tier"],
                                confidence=c["confidence"],
                                components=c["components"],
                                expected_marks=c["expected_marks"],
                                weight_basis=c["weight_basis"],
                                comparability=c["comparability"],
                                history=c["history"],
                                student=c["student"],
                                reasons=[
                                    ReasonPayload(code=r["code"], params=r["params"], sentence=r["sentence"])
                                    for r in c.get("reasons", [])
                                ],
                                caveats=c.get("caveats", []),
                                links=c.get("links", {}),
                            )
                            for c in s.get("chapters", [])
                        ]
                        sub_views.append(
                            SubjectPriority(
                                subject_key=s["subject_key"],
                                data_status=s["data_status"],
                                ranking=s["ranking"],
                                papers_considered=s["papers_considered"],
                                sources=s["sources"],
                                confidence=s["confidence"],
                                core_share_of_marks=s["core_share_of_marks"],
                                tiers=s["tiers"],
                                chapters=ch_views,
                            )
                        )
                    return PriorityView(
                        v=1,
                        snapshot_id=str(cached.id),
                        engine_version=cached.engine_version,
                        weightset_id=str(cached.weightset_id),
                        template_version=1,
                        generated_at=cached.created_at.isoformat(),
                        days_left=days_left,
                        exam_date_source="enrolment" if ctx else "default",
                        disclaimer_key=DISCLAIMER_KEY,
                        subjects=sub_views,
                    )
            except Exception:
                pass

    # Compute fresh
    subjects_qs = Subject.objects.filter(is_active=True)
    if subject_key:
        subjects_qs = subjects_qs.filter(key=subject_key)

    subjects = list(subjects_qs.select_related("scheme"))
    subject_priorities: list[SubjectPriority] = []

    for sub in subjects:
        state = SubjectState.objects.filter(subject_id=sub.id).first()
        d_status = state.data_status if state else "insufficient"
        ranking_avail = "available" if d_status in ("ready", "limited") else "withheld"

        papers = list(
            Paper.objects.filter(
                subject_id=sub.id,
                status=Paper.Status.PUBLISHED,
                include_in_stats=True,
            )
            .order_by("-term_sort")[:settings.window]
        )

        chapters = list(sub.chapters.filter(is_active=True).order_by("sort_order"))
        chapter_ids = [c.id for c in chapters]
        user_accs = practice_accuracy(user_id, chapter_ids, by="chapter")

        tcs = list(TermChapterStat.objects.filter(paper__in=papers))
        tcs_by_ch_paper = {(s.chapter_id, s.paper_id): s for s in tcs}
        view_k = f"w{settings.window}-p{1 if settings.include_practice else 0}-o{1 if settings.include_older else 0}"
        aggs = {a.chapter_id: a for a in ChapterAggregate.objects.filter(subject_key=sub.key, view_key=view_k)}
        if not aggs:
            aggs = {a.chapter_id: a for a in ChapterAggregate.objects.filter(subject_key=sub.key)}

        c_inputs: list[ChapterInput] = []
        for ch in chapters:
            agg = aggs.get(ch.id)
            comp = agg.comparability if agg else "native"
            is_carried = (comp != "native")

            sittings = []
            for idx, p in enumerate(papers):
                stat = tcs_by_ch_paper.get((ch.id, p.id))
                eff_m = float(stat.marks_effective) if stat else 0.0
                sittings.append(
                    PaperSittingInput(
                        paper_id=p.id,
                        term_code=p.term_code,
                        paper_kind=p.paper_kind,
                        age_index=idx,
                        effective_marks=eff_m,
                        is_carried=is_carried,
                    )
                )

            u_acc = user_accs.get(ch.id, {})
            ans = u_acc.get("answered", 0) if isinstance(u_acc, dict) else u_acc[0]
            corr = float(u_acc.get("correct", 0)) if isinstance(u_acc, dict) else float(u_acc[1])
            agg = aggs.get(ch.id)
            comp = agg.comparability if agg else "native"

            c_inputs.append(
                ChapterInput(
                    chapter_id=ch.id,
                    chapter_key=ch.key,
                    name=ch.name,
                    section=ch.section or "",
                    sort_order=ch.sort_order,
                    marks_min=float(ch.marks_min) if ch.marks_min is not None else None,
                    marks_max=float(ch.marks_max) if ch.marks_max is not None else None,
                    sittings=sittings,
                    comparability=comp,
                    coverage_fraction=0.0,
                    practice_answered=ans,
                    practice_correct=float(corr),
                    weakness_source="practice_accuracy",
                )
            )

        if not c_inputs:
            continue

        scored_chapters = score_subject(
            SubjectScoringInput(
                subject_key=sub.key,
                total_subject_marks=float(getattr(sub, "total_marks", 100.0) or 100.0),
                chapters=c_inputs,
                days_left=days_left,
            ),
            params=DEFAULT_PARAMS,
        )

        core_n = sum(1 for c in scored_chapters if c.tier == "core")
        next_n = sum(1 for c in scored_chapters if c.tier == "next")
        rest_n = sum(1 for c in scored_chapters if c.tier == "rest")
        core_marks = sum(c.expected_marks for c in scored_chapters if c.tier == "core")
        total_exp = sum(c.expected_marks for c in scored_chapters) or 1.0
        core_share = round(core_marks / total_exp, 2)

        sources = {
            "exam": sum(1 for p in papers if p.paper_kind == "exam"),
            "mtp": sum(1 for p in papers if p.paper_kind == "mtp"),
            "rtp": sum(1 for p in papers if p.paper_kind == "rtp"),
        }

        subject_priorities.append(
            SubjectPriority(
                subject_key=sub.key,
                data_status=d_status,
                ranking=ranking_avail,
                papers_considered=len(papers),
                sources=sources,
                confidence="medium" if len(papers) >= 4 else "low",
                core_share_of_marks=core_share,
                tiers={"core": core_n, "next": next_n, "rest": rest_n},
                chapters=scored_chapters,
            )
        )

    # Save snapshot
    snap_id = uuid.uuid4()
    p_view = PriorityView(
        v=1,
        snapshot_id=str(snap_id),
        engine_version=engine_ver,
        weightset_id=str(ws_id),
        template_version=1,
        generated_at=timezone.now().isoformat(),
        days_left=days_left,
        exam_date_source="enrolment" if ctx else "default",
        disclaimer_key=DISCLAIMER_KEY,
        subjects=subject_priorities,
    )

    results_dict = asdict(p_view)
    for s in results_dict.get("subjects", []):
        for c in s.get("chapters", []):
            c["chapter_id"] = str(c["chapter_id"])

    Snapshot.objects.create(
        id=snap_id,
        user_id=user_id,
        enrollment_id=enrollment_id or UUID("00000000-0000-0000-0000-000000000000"),
        scope_key=subject_key or "all",
        weightset_id=ws_id,
        engine_version=engine_ver,
        inputs_hash=inputs_hash,
        inputs_summary={"days_left": days_left, "window": settings.window},
        results_schema=1,
        data_status="ready" if any(s.data_status == "ready" for s in subject_priorities) else "limited",
        expires_at=timezone.now() + timedelta(days=7),
        results=results_dict,
    )

    return p_view


def _term_to_year(term: str | None) -> int | None:
    if not term:
        return None
    part = term.split("-")[0]
    return int(part) if part.isdigit() else None


def asked_summary(
    question_ids: Sequence[UUID],
    subject_id: UUID | None = None,
) -> dict[UUID, AskedSummary | None]:
    """
    Returns AskedSummary badges for questions (consumed by F-09 PYQ and question cards).
    Fallback scope: question (duplicate cluster) -> topic -> chapter.
    Never shown if window_n < 3.
    """
    if not question_ids:
        return {}

    # Check duplicate cluster ids
    cluster_map = duplicate_cluster_ids(question_ids)
    results: dict[UUID, AskedSummary | None] = {}

    from modules.questionbank.models import Question
    questions = list(
        Question.objects.filter(id__in=question_ids)
        .select_related("primary_chapter", "primary_topic")
    )

    for q in questions:
        cid = cluster_map.get(q.id)
        # 1. Scope: question (if duplicate cluster has appeared in papers)
        if cid:
            pqs = (
                PaperQuestion.objects.filter(
                    question_id__in=PaperQuestion.objects.filter(paper__status=Paper.Status.PUBLISHED)
                    .values_list("question_id", flat=True)
                )
                .select_related("paper")
            )
            # count distinct terms
            terms = set(pqs.values_list("paper__term_code", flat=True))
            if len(terms) >= 2:
                last_term = sorted(terms)[-1] if terms else None
                results[q.id] = AskedSummary(
                    scope="question",
                    asked_n=len(terms),
                    window_n=6,
                    last_asked_term_code=last_term,
                    last_asked_year=_term_to_year(last_term),
                    label_key="asked_question",
                    label=f"This exact question appeared in {len(terms)} past exam sittings",
                )
                continue

        # 2. Scope: topic
        if q.primary_topic_id:
            ts = TopicStat.objects.filter(topic_id=q.primary_topic_id).first()
            if ts and ts.window_n >= 3 and ts.asked_n > 0:
                results[q.id] = AskedSummary(
                    scope="topic",
                    asked_n=ts.asked_n,
                    window_n=ts.window_n,
                    last_asked_term_code=ts.last_asked_term_code,
                    last_asked_year=_term_to_year(ts.last_asked_term_code),
                    label_key="asked_topic",
                    label=f"This topic appeared in {ts.asked_n} of the last {ts.window_n} sittings",
                )
                continue

        # 3. Scope: chapter
        if q.primary_chapter_id:
            ca = ChapterAggregate.objects.filter(
                chapter_id=q.primary_chapter_id,
                window=6,
            ).first()
            if ca and ca.window_n >= 3:
                results[q.id] = AskedSummary(
                    scope="chapter",
                    asked_n=ca.asked_n,
                    window_n=ca.window_n,
                    last_asked_term_code=ca.last_asked_term_code,
                    last_asked_year=_term_to_year(ca.last_asked_term_code),
                    label_key="asked_chapter",
                    label=f"This chapter appeared in {ca.asked_n} of the last {ca.window_n} sittings",
                )
                continue

        results[q.id] = None

    return results


def my_active_plan(user_id: UUID, enrollment_id: UUID | None = None) -> Plan | None:
    """
    Returns active plan and its items for the user.
    """
    return (
        Plan.objects.filter(user_id=user_id, status=Plan.Status.ACTIVE)
        .prefetch_related(
            Prefetch("items", queryset=PlanItem.objects.order_by("planned_date", "position"))
        )
        .first()
    )


def todays_items(user_id: UUID, local_date: date, limit: int = 5) -> list[PlanItem]:
    """
    Returns items scheduled for today from active plan (consumed by Today provider).
    """
    plan = Plan.objects.filter(user_id=user_id, status=Plan.Status.ACTIVE).first()
    if not plan:
        return []

    return list(
        PlanItem.objects.filter(
            plan=plan,
            planned_date=local_date,
            state=PlanItem.State.PLANNED,
        )
        .order_by("position")[:limit]
    )
