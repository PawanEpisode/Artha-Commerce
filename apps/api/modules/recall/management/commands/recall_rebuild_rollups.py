"""Recompute the daily and per-chapter counters from the review log: `recall_rebuild_rollups --user <uuid> [--from YYYY-MM-DD]`."""

from __future__ import annotations

from datetime import date

from django.core.management.base import BaseCommand, CommandError

from modules.recall.models import RecallReviewLog
from modules.recall.services import rollups


class Command(BaseCommand):
    help = "Rebuild a student's rollups from the log (importance and chapter come from the card as it is now)."

    def add_arguments(self, parser):
        parser.add_argument("--user", help="Student id (uuid).")
        parser.add_argument("--all", action="store_true", help="Every student with reviews.")
        parser.add_argument("--from", dest="since", help="First study day to rebuild (YYYY-MM-DD).")

    def handle(self, *args, user=None, all=False, since=None, **options):  # noqa: A002
        if not (user or all):
            raise CommandError("Give --user, or --all.")
        try:
            start = date.fromisoformat(since) if since else None
        except ValueError as exc:
            raise CommandError("--from must be YYYY-MM-DD.") from exc
        users = [user] if user else list(RecallReviewLog.objects.values_list("user_id", flat=True).distinct())
        rows = sum(rollups.rebuild(u, start) for u in users)
        self.stdout.write(f"rebuilt rollups for {len(users)} students from {rows} log rows")
