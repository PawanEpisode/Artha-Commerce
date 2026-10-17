"""
Management command to backfill / recompute analytics facts from practice sessions.
Usage:
    python manage.py recompute_analytics [--user-id=<uuid>] [--all]
"""

import uuid
from django.core.management.base import BaseCommand
from modules.practice.models import Session
from modules.analytics import services


class Command(BaseCommand):
    help = "Recomputes analytics facts from completed practice sessions."

    def add_arguments(self, parser):
        parser.add_argument("--user-id", type=str, help="Specific user UUID to recompute")
        parser.add_argument("--all", action="store_true", help="Recompute all completed sessions")

    def handle(self, *args, **options):
        user_id_raw = options.get("user_id")
        recompute_all = options.get("all")

        if not user_id_raw and not recompute_all:
            self.stderr.write("Please provide --user-id or --all.")
            return

        qs = Session.objects.filter(status__in=["submitted", "auto_submitted", "abandoned"]).order_by("submitted_at")
        if user_id_raw:
            uid = uuid.UUID(user_id_raw)
            qs = qs.filter(user_id=uid)

        total = qs.count()
        self.stdout.write(f"Found {total} session(s) to process.")

        processed = 0
        for sess in qs:
            services.refresh_session(sess.user_id, sess.id)
            processed += 1
            if processed % 50 == 0:
                self.stdout.write(f"Processed {processed}/{total} sessions...")

        self.stdout.write(self.style.SUCCESS(f"Successfully recomputed {processed} session(s)."))
