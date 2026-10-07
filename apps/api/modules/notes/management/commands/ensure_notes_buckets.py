"""Creates the private `notes-private` bucket in Supabase Storage if it is missing. Safe to run on every deploy."""

from django.core.management.base import BaseCommand

from core import storage
from modules.notes.media_kinds import BUCKET


class Command(BaseCommand):
    help = "Create the private notes bucket if it does not exist."

    def handle(self, *args, **options):
        created = storage.get_storage().ensure_bucket(BUCKET, public=False)
        self.stdout.write(self.style.SUCCESS(f"{BUCKET}: {'created' if created else 'already exists'}"))
