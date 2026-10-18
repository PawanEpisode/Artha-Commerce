"""
Close and score timed practice sessions whose time ran out and that nobody opened again.

Expiry also happens whenever a student reads or writes a session, so this only matters for sessions left alone: it
keeps their results and the practice_session_completed event from waiting for the next visit. Safe to run on a
schedule (every few minutes) and more than once.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from modules.practice import services


class Command(BaseCommand):
    help = "Auto-submit timed practice sessions whose deadline has passed."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--limit", type=int, default=500, help="Most sessions to close in one run.")

    def handle(self, *args, **options) -> None:
        closed = services.expire_overdue_sessions(limit=options["limit"])
        self.stdout.write(f"Auto-submitted {closed} expired practice session(s).")
