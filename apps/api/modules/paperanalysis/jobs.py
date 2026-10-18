"""
Background jobs for paper analysis (F-11 ERD 3.5, 3.8).
Handles:
- `paperanalysis.suggest`: AI & question-bank allocation suggestions for paper questions in chunks of 10.
- `paperanalysis.backtest`: Walk-forward replay for a subject and weightset.
- `paperanalysis.rebuild_stats`: Stats rebuild for a paper or subject.
"""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from core import jobs as core_jobs
from modules.syllabus.models import Chapter, Subject

from .domain.apportion import apportion
from .domain.backtest import PaperFoldMark, run_walk_forward_backtest
from .errors import AiBudgetExceeded
from .models import (
    Allocation,
    BacktestRun,
    Paper,
    PaperQuestion,
)
from .stats import _recompute_chapter_aggregates_for_subject, refresh_paper_stats

logger = logging.getLogger(__name__)

JOB_SUGGEST = "paperanalysis.suggest"
JOB_BACKTEST = "paperanalysis.backtest"
JOB_REBUILD_STATS = "paperanalysis.rebuild_stats"

CHUNK_SIZE = 10
PROMPT_VERSION = "alloc-1"
DEFAULT_DAILY_AI_BUDGET = 500

ALLOC_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "allocations": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "chapter_key": {"type": "STRING"},
                    "topic_key": {"type": "STRING", "nullable": True},
                    "share": {"type": "NUMBER"},
                    "confidence": {"type": "NUMBER"},
                    "rationale": {"type": "STRING"},
                },
                "required": ["chapter_key", "share", "confidence", "rationale"],
            },
        }
    },
    "required": ["allocations"],
}


def _load_prompt_template() -> str:
    path = Path(__file__).resolve().parent / "prompts" / "alloc_1.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "Allocate question marks across relevant syllabus chapters."


def check_ai_budget(increment: int = 0) -> None:
    """
    Checks if today's AI suggestion budget is exceeded.
    Throws AiBudgetExceeded if limit reached.
    """
    budget_limit = getattr(settings, "PAPER_ANALYSIS_DAILY_AI_BUDGET", DEFAULT_DAILY_AI_BUDGET)
    today_str = timezone.now().date().isoformat()
    cache_key = f"pa:ai_usage:{today_str}"
    current = cache.get(cache_key, 0)
    if current + increment > budget_limit:
        raise AiBudgetExceeded()
    if increment > 0:
        cache.set(cache_key, current + increment, timeout=86400)


def register_handlers(jobs_module=core_jobs) -> None:
    jobs_module.register_handler(JOB_SUGGEST, run_suggest)
    jobs_module.register_handler(JOB_BACKTEST, run_backtest)
    jobs_module.register_handler(JOB_REBUILD_STATS, run_rebuild_stats)


def run_suggest(payload: dict) -> dict[str, Any]:
    """
    Runs allocation suggestions for a chunk of up to 10 questions of a paper.
    If more questions remain, enqueues the next chunk.
    """
    paper_id = UUID(str(payload["paper_id"]))
    question_ids = [UUID(str(qid)) for qid in payload.get("question_ids", [])]

    paper = Paper.objects.select_related("subject", "scheme").filter(pk=paper_id).first()
    if not paper:
        return {"error": "paper_not_found"}

    if not question_ids:
        # Pick all untagged questions
        question_ids = list(
            PaperQuestion.objects.filter(paper=paper, alloc_state=PaperQuestion.AllocState.UNTAGGED)
            .order_by("position")
            .values_list("id", flat=True)
        )

    if not question_ids:
        return {"suggested": 0, "remaining": 0}

    chunk = question_ids[:CHUNK_SIZE]
    remaining = question_ids[CHUNK_SIZE:]

    questions = list(
        PaperQuestion.objects.filter(id__in=chunk)
        .prefetch_related("allocations")
        .order_by("position")
    )

    chapters = list(
        Chapter.objects.filter(subject=paper.subject, is_active=True).values("id", "key", "name")
    )
    chapter_map = {c["key"]: c for c in chapters}
    chapter_id_map = {c["id"]: c for c in chapters}

    system_prompt = _load_prompt_template()
    suggested_count = 0
    invalid_count = 0

    from integrations import gemini

    for pq in questions:
        # Check if bank mapping exists
        if pq.question_id:
            # Query questionbank mapping if any
            from modules.questionbank.models import Question
            qb_q = Question.objects.filter(pk=pq.question_id).first()
            if qb_q and qb_q.primary_chapter_id and qb_q.primary_chapter_id in chapter_id_map:
                ch = chapter_id_map[qb_q.primary_chapter_id]
                with transaction.atomic():
                    pq.allocations.filter(status=Allocation.Status.SUGGESTED).delete()
                    Allocation.objects.create(
                        paper_question=pq,
                        chapter_id=ch["id"],
                        subject=paper.subject,
                        scheme=paper.scheme,
                        subject_key=paper.subject_key,
                        chapter_key=ch["key"],
                        marks=pq.marks,
                        share=Decimal("1.000"),
                        status=Allocation.Status.SUGGESTED,
                        origin=Allocation.Origin.BANK_MAPPING,
                        basis=Allocation.Basis.SINGLE,
                        confidence=Decimal("1.00"),
                        rationale="Mapped directly from question bank primary chapter.",
                        prompt_version=PROMPT_VERSION,
                        suggested_at=timezone.now(),
                    )
                    pq.alloc_state = PaperQuestion.AllocState.SUGGESTED
                    pq.save(update_fields=["alloc_state", "updated_at"])
                suggested_count += 1
                continue

        # AI Suggestion
        stem = pq.tag_hint or ""
        if not stem and pq.question_id:
            from modules.questionbank.selectors import stem_text
            stems = stem_text([pq.question_id])
            stem = stems.get(pq.question_id, "")

        if not stem:
            continue

        # Check AI budget before calling
        check_ai_budget(increment=1)

        prompt = (
            f"Subject: {paper.subject_key}\n"
            f"Question Marks: {pq.marks}\n"
            f"Question Stem:\n{stem}\n\n"
            f"Available Chapters:\n"
            + "\n".join(f"- {c['key']}: {c['name']}" for c in chapters)
        )

        try:
            res = gemini.generate_structured(
                prompt=prompt,
                system=system_prompt,
                schema=ALLOC_SCHEMA,
            )
            data = json.loads(res.text)
            allocs = data.get("allocations", [])
        except Exception as exc:
            logger.warning("AI generation failed for question %s: %s", pq.id, exc)
            invalid_count += 1
            continue

        # Server-side validation per ERD 3.5:
        # keys must exist, shares sum to 1.0 within 0.02, at most 4 chapters, rationale at most 200 chars
        if not (1 <= len(allocs) <= 4):
            invalid_count += 1
            continue

        valid = True
        total_share = 0.0
        parsed_items = []
        for item in allocs:
            ck = item.get("chapter_key")
            sh = float(item.get("share", 0.0))
            conf = float(item.get("confidence", 0.5))
            rat = str(item.get("rationale", ""))
            if ck not in chapter_map or sh <= 0 or len(rat) > 200:
                valid = False
                break
            total_share += sh
            parsed_items.append((chapter_map[ck], sh, conf, rat))

        if not valid or not (0.98 <= total_share <= 1.02):
            invalid_count += 1
            continue

        # Apportion marks using largest remainder in 0.5 steps
        raw_shares = [Decimal(str(round(p[1], 4))) for p in parsed_items]
        # Normalize sum
        sum_raw = sum(raw_shares)
        if sum_raw != Decimal("1.0"):
            raw_shares = [s / sum_raw for s in raw_shares]

        allocated_marks = apportion(pq.marks, raw_shares)

        with transaction.atomic():
            pq.allocations.filter(status=Allocation.Status.SUGGESTED).delete()
            for (ch, sh, conf, rat), m in zip(parsed_items, allocated_marks, strict=False):
                Allocation.objects.create(
                    paper_question=pq,
                    chapter_id=ch["id"],
                    subject=paper.subject,
                    scheme=paper.scheme,
                    subject_key=paper.subject_key,
                    chapter_key=ch["key"],
                    marks=m,
                    share=Decimal(str(round(sh, 3))),
                    status=Allocation.Status.SUGGESTED,
                    origin=Allocation.Origin.AI,
                    basis=Allocation.Basis.SINGLE if len(parsed_items) == 1 else Allocation.Basis.WEIGHTED,
                    confidence=Decimal(str(round(min(max(conf, 0.0), 1.0), 2))),
                    rationale=(rat or "")[:200],
                    model=getattr(res, "model", "gemini") or "gemini",
                    prompt_version=PROMPT_VERSION,
                    suggested_at=timezone.now(),
                )
            pq.alloc_state = PaperQuestion.AllocState.SUGGESTED
            pq.save(update_fields=["alloc_state", "updated_at"])
        suggested_count += 1

    if remaining:
        core_jobs.enqueue(
            JOB_SUGGEST,
            {"paper_id": str(paper_id), "question_ids": [str(q) for q in remaining]},
            dedupe_key=f"{JOB_SUGGEST}:{paper_id}:{len(remaining)}",
        )

    return {
        "suggested": suggested_count,
        "invalid": invalid_count,
        "remaining": len(remaining),
    }


def run_backtest(payload: dict) -> dict[str, Any]:
    """
    Executes walk-forward back-testing replay for a subject and weightset.
    """
    run_id = UUID(str(payload["backtest_id"]))
    run = BacktestRun.objects.select_related("subject", "scheme", "weightset").filter(pk=run_id).first()
    if not run:
        return {"error": "backtest_run_not_found"}

    run.status = BacktestRun.Status.RUNNING
    run.started_at = timezone.now()
    run.save(update_fields=["status", "started_at"])

    # Load papers for subject and scheme
    papers = list(
        Paper.objects.filter(
            subject=run.subject,
            scheme=run.scheme,
            status=Paper.Status.PUBLISHED,
        )
        .order_by("term_sort")
        .prefetch_related("questions__allocations")
    )

    if len(papers) < 3:
        run.status = BacktestRun.Status.FAILED
        run.finished_at = timezone.now()
        run.metrics = {"error": "insufficient_papers", "count": len(papers)}
        run.save(update_fields=["status", "finished_at", "metrics"])
        return {"status": "failed", "reason": "insufficient_papers"}

    # Build PaperFoldMark list
    fold_marks: list[PaperFoldMark] = []
    for p in papers:
        for q in p.questions.all():
            for a in q.allocations.filter(status=Allocation.Status.CONFIRMED):
                fold_marks.append(
                    PaperFoldMark(
                        paper_id=p.id,
                        term_code=p.term_code,
                        term_sort=p.term_sort,
                        paper_kind=p.kind,
                        chapter_id=a.chapter_id,
                        effective_marks=float(a.marks),
                    )
                )

    res = run_walk_forward_backtest(
        all_sittings=fold_marks,
        k_fraction=float(run.k_fraction),
        min_folds=1,
    )

    run.status = BacktestRun.Status.DONE
    run.finished_at = timezone.now()
    run.papers_used = res.papers_used
    run.folds = res.folds
    run.marks_captured = Decimal(str(round(res.marks_captured, 4)))
    run.baseline_flat = Decimal(str(round(res.baseline_flat, 4)))
    run.lift = Decimal(str(round(res.lift, 3)))
    run.metrics = res.metrics
    run.save(update_fields=[
        "status", "finished_at", "papers_used", "folds",
        "marks_captured", "baseline_flat", "lift", "metrics"
    ])

    return {
        "status": "done",
        "lift": float(run.lift),
        "folds": run.folds,
    }


def run_rebuild_stats(payload: dict) -> dict[str, Any]:
    """
    Rebuilds statistics for a paper or all published papers of a subject.
    """
    paper_id = payload.get("paper_id")
    subject_id = payload.get("subject_id")

    if paper_id:
        p_uuid = UUID(str(paper_id))
        refresh_paper_stats(p_uuid)
        return {"status": "done", "paper_id": str(p_uuid)}

    if subject_id:
        s_uuid = UUID(str(subject_id))
        subject = Subject.objects.filter(pk=s_uuid).first()
        if not subject:
            return {"error": "subject_not_found"}
        _recompute_chapter_aggregates_for_subject(subject)
        return {"status": "done", "subject_id": str(s_uuid)}

    return {"error": "missing_target"}
