"""Recompute the daily roll-ups and hour buckets from the sessions: `manage.py rebuild_tracking_rollups [--user ID] [--from D] [--to D]`."""

from datetime import date

from django.core.management.base import BaseCommand

from modules.tracking import rollups
from modules.tracking.models import StudySession


class Command(BaseCommand):
    help = "Rebuild tracking roll-ups from study sessions (safe to repeat)."

    def add_arguments(self, parser):
        parser.add_argument("--user", help="Only this student id")
        parser.add_argument("--from", dest="start", type=date.fromisoformat)
        parser.add_argument("--to", dest="end", type=date.fromisoformat)

    def handle(self, *args, user=None, start=None, end=None, **options):
        users = [user] if user else list(StudySession.objects.values_list("user_id", flat=True).distinct())
        total = sum(rollups.rebuild(u, start, end) for u in users)
        self.stdout.write(self.style.SUCCESS(f"Rebuilt {total} day(s) for {len(users)} student(s)."))
