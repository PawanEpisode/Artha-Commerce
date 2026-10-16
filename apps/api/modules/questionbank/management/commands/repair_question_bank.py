"""
Management command: python manage.py repair_question_bank [--dry-run]

One-off clean-up for question rows made by the early seeders:

1. Archives generated filler (the same stem repeated as "(Item 3)", "(Part 7)", ...).
2. Archives exact duplicates (same normalised stem, kind and source), keeping the oldest.
3. Makes marks agree everywhere, using this order: the paper's own mark for that question, then the exam pattern's marks per
   MCQ (CMA: 15 MCQs x 2 marks), then the live version's marks. The list page and the detail page then show the same number.
4. Fills a missing difficulty with the estimate from `domain/difficulty.py`.

Safe to run again: a second run changes nothing.
"""

from __future__ import annotations

import re
from collections import defaultdict
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from modules.mcqbank.models import PatternProfile
from modules.pyq.models import PaperQuestion
from modules.questionbank.domain.difficulty import estimate_difficulty
from modules.questionbank.domain.fingerprint import normalise_for_fingerprint
from modules.questionbank.models import CollectionItem, Question

FILLER = re.compile(r"\((item|part|question)\s+\d+\)\s*$", re.I)
MCQ_KINDS = {"mcq_single", "mcq_multi"}


class Command(BaseCommand):
    help = "Archive filler and duplicate questions, align marks with the exam pattern, fill missing difficulty."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Report what would change and roll back.")

    def handle(self, *args, **options):
        dry = options["dry_run"]
        with transaction.atomic():
            filler = self._archive_filler()
            dupes = self._archive_duplicates()
            marks = self._align_marks()
            diff = self._fill_difficulty()
            if dry:
                transaction.set_rollback(True)
        verb = "Would change" if dry else "Changed"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb}: {filler} filler archived, {dupes} duplicates archived, {marks} marks aligned, {diff} difficulties filled."
            )
        )

    def _live(self):
        return Question.objects.filter(status=Question.Status.ACTIVE, deleted_at__isnull=True).select_related(
            "live_version"
        )

    def _archive(self, question: Question) -> None:
        question.status = Question.Status.ARCHIVED
        question.visibility = Question.Visibility.PRIVATE
        question.deleted_at = timezone.now()
        question.save(update_fields=["status", "visibility", "deleted_at", "updated_at"])

    def _archive_filler(self) -> int:
        count = 0
        for q in self._live():
            if q.live_version and FILLER.search(q.live_version.stem_md or ""):
                self._archive(q)
                count += 1
        return count

    def _archive_duplicates(self) -> int:
        groups: dict[tuple[str, str, str], list[Question]] = defaultdict(list)
        for q in self._live().order_by("created_at", "id"):
            if q.live_version:
                key = (normalise_for_fingerprint(q.live_version.stem_md or ""), q.kind, q.source_name)
                groups[key].append(q)
        count = 0
        for items in groups.values():
            for extra in items[1:]:
                self._archive(extra)
                count += 1
        return count

    def _pattern_marks(self, q: Question) -> Decimal | None:
        if q.kind not in MCQ_KINDS:
            return None
        subject_keys = {q.subject_key} - {""}
        subject_keys |= set(
            CollectionItem.objects.filter(question=q)
            .exclude(collection__subject_key__isnull=True)
            .values_list("collection__subject_key", flat=True)
        )
        if q.primary_subject_id:
            subject_keys.add(q.primary_subject.key)
        profile = (
            PatternProfile.objects.filter(
                status=PatternProfile.Status.ACTIVE, subject_key__in=subject_keys, marks_per_mcq__isnull=False
            )
            .order_by("-effective_from")
            .first()
        )
        return profile.marks_per_mcq if profile else None

    def _align_marks(self) -> int:
        count = 0
        for q in self._live():
            v = q.live_version
            if v is None:
                continue
            paper_marks = PaperQuestion.objects.filter(question=q).values_list("marks", flat=True).first()
            target = paper_marks if paper_marks is not None else self._pattern_marks(q)
            if target is None:
                target = v.marks
            target = Decimal(target).quantize(Decimal("0.1"))
            if v.marks != target or q.marks != target:
                v.marks = target
                v.save(update_fields=["marks"])
                q.marks = target
                q.save(update_fields=["marks", "updated_at"])
                count += 1
        return count

    def _fill_difficulty(self) -> int:
        count = 0
        for q in self._live().filter(difficulty__isnull=True):
            v = q.live_version
            if v is None:
                continue
            options = list(v.options.order_by("position").values_list("body_md", flat=True))
            q.difficulty = estimate_difficulty(kind=q.kind, stem=v.stem_md or "", options=options, marks=v.marks)
            q.save(update_fields=["difficulty", "updated_at"])
            count += 1
        return count
