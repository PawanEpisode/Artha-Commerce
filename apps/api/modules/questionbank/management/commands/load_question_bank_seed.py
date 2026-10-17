"""
Management command:
    python manage.py load_question_bank_seed [--paper 13] [--kind mcq|workbook|pyq] [--dry-run] [--publish]

Loads the committed seed JSON through the existing services and prints, per paper and kind, how many items were parsed,
created, updated, unchanged, merged into an existing duplicate, held back for review, or skipped (with the reason).
Idempotent: a second run creates nothing. `--dry-run` runs everything inside a transaction that is rolled back, so the
counts are exactly what a real run would report. Without `--publish`, nothing goes live.
"""

from __future__ import annotations

from contextlib import nullcontext

from django.core.management.base import BaseCommand
from django.db import transaction

from modules.questionbank import seed_loader as loader


class Command(BaseCommand):
    help = "Load the CMA Final question-bank seeds (MCQ banks, workbooks, previous year papers)."

    def add_arguments(self, parser):
        parser.add_argument("--paper", help="One paper, e.g. 13 or 20A. Default: all.")
        parser.add_argument("--kind", choices=list(loader.KINDS), help="mcq, workbook or pyq. Default: all.")
        parser.add_argument("--dry-run", action="store_true", help="Run, report, and roll everything back.")
        parser.add_argument(
            "--replace-legacy",
            action="store_true",
            help="If an earlier paper with questions already holds a term, withdraw it and load the seeded paper instead.",
        )
        parser.add_argument("--publish", action="store_true", help="Publish items with no doubts. Drafts stay drafts.")

    def handle(self, *args, **options):
        kinds = [options["kind"]] if options["kind"] else list(loader.KINDS)
        reports: list[loader.LoadReport] = []
        # Only a dry run needs the outer transaction (to roll it back); a real run commits per item.
        with transaction.atomic() if options["dry_run"] else nullcontext():
            for kind in kinds:
                for path in loader.seed_files(kind, options["paper"]):
                    fn = loader.load_pyq_seed if kind == "pyq" else loader.load_item_seed
                    kwargs = {"replace_legacy": options["replace_legacy"]} if kind == "pyq" else {}
                    report = fn(path, publish=options["publish"], **kwargs)
                    reports.append(report)
                    self.stdout.write(report.row())
            if options["dry_run"]:
                transaction.set_rollback(True)
        for r in reports:
            for note in r.notes:
                self.stdout.write(f"  note {r.paper} {r.kind} {r.label}: {note}")
            for why in r.skipped:
                self.stdout.write(self.style.WARNING(f"  skipped {r.paper} {r.kind} {r.label}: {why}"))
        total = {
            k: sum(getattr(r, k) for r in reports)
            for k in ("parsed", "created", "updated", "unchanged", "merged", "drafts", "published")
        }
        skipped = sum(len(r.skipped) for r in reports)
        self.stdout.write(
            "TOTAL "
            + " ".join(f"{k}={v}" for k, v in total.items())
            + f" skipped={skipped}"
            + (" (dry run, rolled back)" if options["dry_run"] else "")
        )
