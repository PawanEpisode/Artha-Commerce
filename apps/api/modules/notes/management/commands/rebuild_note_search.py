"""Rewrites the stored search vector of every note (after a language-configuration change or a restore from backup)."""

from django.core.management.base import BaseCommand

from modules.notes.models import Note
from modules.notes.services import search_index


class Command(BaseCommand):
    help = "Rebuild notes.search_tsv (PostgreSQL only)."

    def add_arguments(self, parser):
        parser.add_argument("--batch", type=int, default=500)

    def handle(self, *args, batch, **options):
        total = 0
        for note in Note.objects.only("id", "title", "body_text", "lang").iterator(chunk_size=batch):
            search_index.refresh(note)
            total += 1
        self.stdout.write(self.style.SUCCESS(f"Rebuilt {total} note(s)."))
