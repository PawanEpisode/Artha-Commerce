"""
Management command: python manage.py ingest_analysis_papers [options]

Automates Step 4 (Editorial & Paper Data Setup) for F-11 Paper Analysis:
1. Ingests papers, sections, choice groups, and questions from committed PYQ seeds or skeleton CSV.
2. Creates and confirms question-to-chapter allocations (using Hamilton apportionment / exact 0.5-mark sums).
3. Optionally publishes the paper and triggers statistical rollups (refresh_paper_stats) in one shot.

Examples:
    # Dry-run inspect CMA Final Paper 13 seeds
    python manage.py ingest_analysis_papers --paper 13 --dry-run

    # Ingest, confirm, and publish all CMA Final PYQ papers
    python manage.py ingest_analysis_papers --publish

    # Ingest from a skeleton CSV file
    python manage.py ingest_analysis_papers --skeleton-csv /path/to/paper.csv --subject corporate-and-economic-laws --term-code 2024-06 --publish
"""

from __future__ import annotations

import json
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from modules.paperanalysis.domain.effective import (
    calculate_effective_marks,
    is_practical_format_or_nature,
)
from modules.paperanalysis.models import (
    Allocation,
    ChoiceGroup,
    Paper,
    PaperQuestion,
    SubjectState,
)
from modules.paperanalysis.services import (
    confirm_question,
    import_skeleton_csv,
    publish_paper,
)
from modules.syllabus.models import Chapter, ExamTerm, Subject

SEED_ACTOR_ID = uuid.uuid5(uuid.NAMESPACE_URL, "https://arthacommerce.in/paperanalysis/ingest")
PYQ_SEED_DIR = Path(__file__).resolve().parents[3] / "questionbank" / "seed" / "cma-final" / "pyq"


class Command(BaseCommand):
    help = "Ingest past exam papers, create chapter allocations, publish, and compute statistics automatically."

    def add_arguments(self, parser):
        parser.add_argument("--paper", help="Filter by paper number (e.g. 13, 14, 18, 20A).")
        parser.add_argument("--term", help="Filter by term code (e.g. 2024-06, 2023-12).")
        parser.add_argument(
            "--from-seeds",
            action="store_true",
            default=True,
            help="Ingest from committed PYQ seed JSON files (default).",
        )
        parser.add_argument("--skeleton-csv", help="Path to a skeleton CSV file.")
        parser.add_argument("--subject", help="Subject key (required when using --skeleton-csv).")
        parser.add_argument("--term-code", help="Term code e.g. 2024-06 (required when using --skeleton-csv).")
        parser.add_argument("--total-marks", default="100.0", help="Total marks for paper (default: 100.0).")
        parser.add_argument(
            "--publish",
            action="store_true",
            help="Automatically confirm allocations, publish paper, and refresh statistics.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate the ingestion and report results without committing changes to the database.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite/replace existing draft papers for the same term.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        publish = options["publish"]
        force = options["force"]

        self.stdout.write(self.style.SUCCESS("=== Paper Analysis Automation Ingestion ==="))
        if dry_run:
            self.stdout.write(self.style.WARNING("Running in DRY-RUN mode. No changes will be saved to the database.\n"))

        if options.get("skeleton_csv"):
            self._handle_skeleton_csv(options)
            return

        self._handle_pyq_seeds(options, dry_run=dry_run, publish=publish, force=force)

    def _handle_skeleton_csv(self, options: dict[str, Any]):
        csv_path = Path(options["skeleton_csv"])
        if not csv_path.is_file():
            raise CommandError(f"Skeleton CSV file not found: {csv_path}")

        subject_key = options.get("subject")
        term_code = options.get("term_code")
        if not subject_key or not term_code:
            raise CommandError("--subject and --term-code are required when ingesting from --skeleton-csv")

        subject = Subject.objects.filter(key=subject_key).first()
        if not subject:
            raise CommandError(f"Subject '{subject_key}' not found in database. Run syllabus seeding first.")

        scheme = subject.scheme
        total_marks = Decimal(str(options["total_marks"]))
        dry_run = options["dry_run"]
        publish = options["publish"]

        with transaction.atomic() if not dry_run else transaction.atomic():
            paper = Paper.objects.filter(
                scheme=scheme,
                subject_key=subject_key,
                term_code=term_code,
                paper_kind=Paper.PaperKind.EXAM,
            ).first()

            if paper and paper.status == Paper.Status.PUBLISHED:
                self.stdout.write(self.style.WARNING(f"Paper {paper.title} already published. Skipping."))
                return

            if not paper:
                parts = term_code.split("-")
                term_sort = date(int(parts[0]), int(parts[1]), 1)
                paper = Paper.objects.create(
                    subject=subject,
                    scheme=scheme,
                    level=scheme.level,
                    subject_key=subject_key,
                    term_code=term_code,
                    term_sort=term_sort,
                    paper_kind=Paper.PaperKind.EXAM,
                    title=f"{subject.name}, {term_code}",
                    entry_mode=Paper.EntryMode.SKELETON,
                    origin_module=Paper.OriginModule.SKELETON,
                    total_marks=total_marks,
                    duration_minutes=subject.exam_duration_minutes or 180,
                    status=Paper.Status.DRAFT,
                    created_by=SEED_ACTOR_ID,
                )

            csv_content = csv_path.read_text(encoding="utf-8")
            report = import_skeleton_csv(SEED_ACTOR_ID, paper.id, csv_content, dry_run=dry_run)

            self.stdout.write(
                f"Parsed {report.total_rows} rows: created {report.questions_created} questions, "
                f"{report.allocations_created} allocations."
            )
            if report.errors:
                for err in report.errors:
                    self.stdout.write(self.style.ERROR(f"  Error: {err}"))
                return

            if publish and not dry_run:
                for q in paper.questions.all():
                    confirm_question(SEED_ACTOR_ID, q.id, rev=q.rev)
                paper.refresh_from_db()
                publish_paper(SEED_ACTOR_ID, paper.id, rev=paper.rev)
                self.stdout.write(self.style.SUCCESS(f"Published paper {paper.title} and refreshed statistics."))

            if dry_run:
                transaction.set_rollback(True)

    def _handle_pyq_seeds(self, options: dict[str, Any], *, dry_run: bool, publish: bool, force: bool):
        if not PYQ_SEED_DIR.is_dir():
            raise CommandError(f"Seed directory not found at {PYQ_SEED_DIR}")

        files = sorted(PYQ_SEED_DIR.glob("p*.json"))
        paper_filter = options.get("paper")
        term_filter = options.get("term")

        if paper_filter:
            prefix = f"p{paper_filter.lower()}-"
            files = [f for f in files if f.name.startswith(prefix)]
        if term_filter:
            files = [f for f in files if term_filter in f.name]

        if not files:
            self.stdout.write(self.style.WARNING("No seed files matched the given filters."))
            return

        self.stdout.write(f"Found {len(files)} paper seed file(s) to process.\n")
        stats = {"processed": 0, "published": 0, "skipped": 0, "questions": 0, "allocations": 0}

        context_mgr = transaction.atomic() if not dry_run else transaction.atomic()
        with context_mgr:
            for seed_file in files:
                try:
                    data = json.loads(seed_file.read_text(encoding="utf-8"))
                    payload = data.get("payload", {})
                    out = self._ingest_single_seed(payload, publish=publish, force=force)
                    if out["status"] == "skipped":
                        stats["skipped"] += 1
                        self.stdout.write(self.style.WARNING(f"  [SKIPPED] {seed_file.name}: {out['reason']}"))
                    else:
                        stats["processed"] += 1
                        stats["questions"] += out["questions"]
                        stats["allocations"] += out["allocations"]
                        if out.get("published"):
                            stats["published"] += 1
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"  [PUBLISHED] {out['title']} ({out['questions']} questions, {out['allocations']} allocations)"
                                )
                            )
                        else:
                            self.stdout.write(
                                f"  [LOADED DRAFT] {out['title']} ({out['questions']} questions, {out['allocations']} allocations)"
                            )
                except Exception as exc:
                    self.stdout.write(self.style.ERROR(f"  [ERROR] {seed_file.name}: {exc}"))

            if dry_run:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("\nDry-run completed. All changes rolled back."))

        self.stdout.write(
            f"\nFinished: {stats['processed']} papers ingested ({stats['published']} published, {stats['skipped']} skipped), "
            f"{stats['questions']} questions, {stats['allocations']} allocations.\n"
        )

    def _ingest_single_seed(self, payload: dict[str, Any], *, publish: bool, force: bool) -> dict[str, Any]:
        subject_key = payload.get("subject_key")
        course_code = payload.get("course_code")
        level_code = payload.get("level_code")
        term_code = payload.get("term_code")
        title = payload.get("title", f"{subject_key} {term_code}")
        external_ref = payload.get("external_ref", f"pyq:{subject_key}:{term_code}")

        subject_qs = Subject.objects.select_related("scheme__level__course")
        subject = None
        if course_code and level_code:
            subject = subject_qs.filter(
                scheme__level__course__code=course_code,
                scheme__level__code=level_code,
                key=subject_key,
            ).first()
        if not subject:
            subject = subject_qs.filter(key=subject_key).first()

        if not subject:
            return {
                "status": "skipped",
                "reason": f"Subject '{subject_key}' not found in database. Seed syllabus first.",
            }

        scheme = subject.scheme
        level = scheme.level

        # Check for existing paper
        existing = Paper.objects.filter(
            scheme=scheme,
            subject_key=subject_key,
            term_code=term_code,
            paper_kind=Paper.PaperKind.EXAM,
        ).first()

        # If existing belongs to a different subject/scheme due to earlier mis-mapping, remove it
        if not existing:
            stale = Paper.objects.filter(
                subject_key=subject_key,
                term_code=term_code,
                paper_kind=Paper.PaperKind.EXAM,
            ).first()
            if stale and force:
                stale.questions.all().delete()
                stale.choice_groups.all().delete()
                stale.delete()

        if existing and existing.status == Paper.Status.PUBLISHED and not force:
            return {"status": "skipped", "reason": "Already published (use --force to overwrite)"}

        if existing and force:
            existing.questions.all().delete()
            existing.choice_groups.all().delete()
            paper = existing
            paper.status = Paper.Status.DRAFT
            paper.confirmed_marks = Decimal("0.0")
            paper.subject = subject
            paper.scheme = scheme
            paper.level = level
            paper.save()
        elif existing:
            paper = existing
        else:
            parts = term_code.split("-")
            term_sort = date(int(parts[0]), int(parts[1]), 1)
            exam_term = ExamTerm.objects.filter(level=level, code=term_code).first()

            paper = Paper.objects.create(
                subject=subject,
                scheme=scheme,
                level=level,
                subject_key=subject_key,
                term_code=term_code,
                exam_term=exam_term,
                term_sort=term_sort,
                paper_kind=Paper.PaperKind.EXAM,
                title=title,
                entry_mode=Paper.EntryMode.FROM_BANK,
                origin_module=Paper.OriginModule.PYQ,
                origin_ref=external_ref,
                total_marks=Decimal(str(payload.get("total_marks", 100))),
                duration_minutes=payload.get("duration_minutes", 180),
                status=Paper.Status.DRAFT,
                created_by=SEED_ACTOR_ID,
            )

        SubjectState.objects.get_or_create(
            subject_id=subject.id,
            defaults={"scheme_id": scheme.id, "subject_key": subject.key},
        )

        # Build choice groups
        cg_map: dict[str, ChoiceGroup] = {}
        for cg_def in payload.get("choice_groups", []):
            ref = cg_def.get("ref", cg_def.get("label", "cg"))
            cg, _ = ChoiceGroup.objects.get_or_create(
                paper=paper,
                label=cg_def.get("label", ref),
                defaults={
                    "pick_n": cg_def.get("pick_count", 1),
                    "of_m": cg_def.get("of_count", 1),
                    "note": cg_def.get("section_label", ""),
                },
            )
            cg_map[ref] = cg

        # Active chapters index
        active_chapters = {c.key: c for c in Chapter.objects.filter(subject=subject, is_active=True)}

        leaves = [p for p in payload.get("parts", []) if p.get("is_leaf")]
        questions_count = 0
        allocations_count = 0

        for idx, part in enumerate(leaves, start=1):
            label = part.get("number_label") or str(idx)
            marks = Decimal(str(part.get("marks", "0.0")))
            if marks <= 0:
                continue

            kind = str(part.get("kind", "long_form"))
            fmt = "mcq" if "mcq" in kind else "descriptive"
            nature = "practical" if is_practical_format_or_nature(fmt, None) else "theory"
            cg = cg_map.get(part.get("choice_group_ref"))

            eff_marks = calculate_effective_marks(
                marks,
                pick_n=cg.pick_n if cg else None,
                of_m=cg.of_m if cg else None,
            )

            pq, _ = PaperQuestion.objects.update_or_create(
                paper=paper,
                label=label,
                defaults={
                    "position": idx,
                    "marks": marks,
                    "choice_group": cg,
                    "effective_marks": eff_marks,
                    "format": fmt,
                    "nature": nature,
                    "section_label": getattr(cg, "note", "") if cg else "",
                    "source_ref": external_ref,
                    "text_available": bool(part.get("stem_md")),
                    "alloc_state": PaperQuestion.AllocState.UNTAGGED,
                },
            )
            questions_count += 1

            # Chapter allocation
            ch_key = part.get("chapter_key")
            has_valid_alloc = False
            if ch_key and ch_key in active_chapters:
                ch = active_chapters[ch_key]
                Allocation.objects.update_or_create(
                    paper_question=pq,
                    chapter=ch,
                    defaults={
                        "subject": subject,
                        "scheme": scheme,
                        "subject_key": subject_key,
                        "chapter_key": ch.key,
                        "marks": marks,
                        "share": Decimal("1.000"),
                        "status": Allocation.Status.CONFIRMED,
                        "origin": Allocation.Origin.BANK_MAPPING,
                        "confidence": Decimal(str(part.get("mapping_confidence", 1.0))),
                        "decided_by": SEED_ACTOR_ID,
                        "decided_at": timezone.now(),
                    },
                )
                allocations_count += 1
                has_valid_alloc = True

            if has_valid_alloc:
                pq.alloc_state = PaperQuestion.AllocState.CONFIRMED
                pq.confirmed_by = SEED_ACTOR_ID
                pq.confirmed_at = timezone.now()
                pq.save(update_fields=["alloc_state", "confirmed_by", "confirmed_at", "updated_at"])

        # Update paper totals
        paper.question_count = questions_count
        paper.confirmed_marks = sum(
            (q.marks for q in paper.questions.filter(alloc_state=PaperQuestion.AllocState.CONFIRMED)),
            Decimal("0.0"),
        )
        paper.save(update_fields=["question_count", "confirmed_marks", "updated_at"])

        was_published = False
        if publish and paper.confirmed_marks >= (paper.total_marks * Decimal("0.95")):
            publish_paper(SEED_ACTOR_ID, paper.id, rev=paper.rev)
            was_published = True

        return {
            "status": "ok",
            "title": paper.title,
            "questions": questions_count,
            "allocations": allocations_count,
            "published": was_published,
        }
