"""Retry queued avatar file deletions (daily). Rows leave the queue when the file is gone; after 8 failures they stay and log."""

import logging

from django.core.management.base import BaseCommand

from core import storage
from modules.profiles.models import StorageDelete

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 8
BATCH = 200


class Command(BaseCommand):
    help = "Retry queued avatar deletions and remove the rows that succeeded."

    def handle(self, *args, **options):
        store = storage.get_storage()
        removed = failed = 0
        rows = list(StorageDelete.objects.filter(attempts__lt=MAX_ATTEMPTS).order_by("created_at")[:BATCH])
        for row in rows:
            try:
                store.delete(row.bucket, [row.path])
            except Exception:
                StorageDelete.objects.filter(pk=row.pk).update(attempts=row.attempts + 1)
                failed += 1
                if row.attempts + 1 >= MAX_ATTEMPTS:
                    logger.error("Avatar deletion gave up after %s attempts: %s/%s", MAX_ATTEMPTS, row.bucket, row.path)
                continue
            row.delete()
            removed += 1
        self.stdout.write(f"sweep_avatars: removed={removed} failed={failed}")
