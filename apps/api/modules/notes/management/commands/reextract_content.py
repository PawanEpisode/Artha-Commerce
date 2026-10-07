"""
Runs the native text extraction again for derived file content (ERD 9): after the extractor or the language configuration
changed, or to retry content whose extraction `failed`. Nothing is deleted: the extract job rewrites pages of the same rank and
never replaces OCR or AI text (`services.file_pages`), so a student's searchable OCR survives. The original files are not touched.
"""

from django.core.management.base import BaseCommand, CommandError

from core import jobs
from modules.notes.jobs import JOB_EXTRACT_TEXT
from modules.notes.models import Document, FileContent

DEFAULT_STATUSES = ("failed",)


class Command(BaseCommand):
    help = "Queue text extraction again for file content (default: the ones that failed)."

    def add_arguments(self, parser):
        parser.add_argument("--content", action="append", default=[], help="A content id; repeatable.")
        parser.add_argument(
            "--status", action="append", default=[], help="Re-run contents in this text status; repeatable."
        )
        parser.add_argument("--all", action="store_true", help="Every content that has a readable document.")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, content, status, all, dry_run, **options):
        rows = FileContent.objects.filter(page_count__isnull=False).exclude(text_status="locked")
        if content:
            rows = rows.filter(pk__in=content)
        elif not all:
            rows = rows.filter(text_status__in=status or DEFAULT_STATUSES)
        elif status:
            raise CommandError("Use either --all or --status, not both.")
        queued = 0
        for row in rows.iterator():
            document = Document.objects.filter(content_id=row.pk).exclude(status__in=["rejected", "expired"]).first()
            if document is None:
                continue  # nobody holds these bytes: orphaned content is purged, not re-read
            queued += 1
            if dry_run:
                continue
            FileContent.objects.filter(pk=row.pk).update(text_status="pending", text_pages_done=0)
            jobs.enqueue(
                JOB_EXTRACT_TEXT,
                {"content_id": str(row.pk), "document_id": str(document.pk)},
                dedupe_key=f"{JOB_EXTRACT_TEXT}:{row.pk}",
            )
        self.stdout.write(self.style.SUCCESS(f"{'Would queue' if dry_run else 'Queued'} {queued} content(s)."))
