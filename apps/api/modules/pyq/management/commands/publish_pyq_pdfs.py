"""
python manage.py publish_pyq_pdfs [--root DIR] [--dry-run] [--force]

Uploads the past-paper PDFs in `docs/source-material/question-bank/cma-final/pyqs` to the private notes bucket and links each
to its paper, so students read and mark them in the PDF reader instead of leaving for the institute's site. Run it after the
papers are loaded (`load_question_bank_seed`). Safe to run again: a paper that already has its PDF is left alone, unless
`--force` replaces it. Always run `--dry-run` first and read the list.
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from modules.pyq import hosted
from modules.pyq.domain.sources import discover
from modules.pyq.models import PyqPaper

DEFAULT_ROOT = (
    Path(settings.BASE_DIR).parent.parent / "docs" / "source-material" / "question-bank" / "cma-final" / "pyqs"
)


class Command(BaseCommand):
    help = "Upload the past-paper PDFs from source-material and link them to their papers."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--root", default=str(DEFAULT_ROOT), help="Folder holding the P13 - ... paper folders.")
        parser.add_argument("--dry-run", action="store_true", help="Show what would be uploaded and change nothing.")
        parser.add_argument("--force", action="store_true", help="Replace a PDF that is already hosted.")

    def handle(self, *args, **options) -> None:
        root = Path(options["root"])
        if not root.is_dir():
            raise CommandError(f"Folder not found: {root}")
        files, unmatched = discover(root)
        for name in unmatched:
            self.stdout.write(self.style.WARNING(f"  skipped (does not map to a paper): {name}"))

        counts = {"published": 0, "replaced": 0, "kept": 0, "no paper": 0, "failed": 0}
        for source in files:
            paper = PyqPaper.objects.filter(external_ref=source.external_ref).first()
            label = f"{source.external_ref}  {source.link_kind:<18} {source.path.name}"
            if paper is None:
                counts["no paper"] += 1
                self.stdout.write(self.style.WARNING(f"  no paper loaded for {label}"))
                continue
            if options["dry_run"]:
                self.stdout.write(f"  would host {label}")
                continue
            try:
                outcome = hosted.publish_pdf(paper, source, force=options["force"])
            except Exception as exc:  # one bad file must not stop the rest
                counts["failed"] += 1
                self.stdout.write(self.style.ERROR(f"  FAILED {label}: {type(exc).__name__}: {exc}"))
                continue
            counts[outcome] += 1
            self.stdout.write(f"  {outcome}: {label}")

        summary = ", ".join(f"{n} {k}" for k, n in counts.items() if n) or "nothing to do"
        self.stdout.write(self.style.SUCCESS(f"Done ({'dry run: ' if options['dry_run'] else ''}{summary})."))
        if counts["failed"]:
            raise CommandError(f"{counts['failed']} file(s) failed; run again to retry them.")
