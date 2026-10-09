"""Rebuild cards from the review log: `recall_replay --user <uuid> [--card <uuid>]`, or every card with `--all`. Prints counts only."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from modules.recall.models import RecallCard
from modules.recall.services import reviews


class Command(BaseCommand):
    help = "Replay cards from the review log. Safe to repeat: a card that already equals its fold is not touched."

    def add_arguments(self, parser):
        parser.add_argument("--user", help="Student id (uuid).")
        parser.add_argument("--card", help="One card id (uuid); needs --user.")
        parser.add_argument("--all", action="store_true", help="Every student's cards.")

    def handle(self, *args, user=None, card=None, all=False, **options):  # noqa: A002
        if card and not user:
            raise CommandError("--card needs --user.")
        if not (user or all):
            raise CommandError("Give --user, or --all.")
        qs = RecallCard.objects.all()
        if user:
            qs = qs.filter(user_id=user)
        if card:
            qs = qs.filter(id=card)
        seen = changed = 0
        for user_id, card_id in qs.order_by("user_id", "id").values_list("user_id", "id").iterator():
            seen += 1
            changed += 1 if reviews.replay_card(user_id, card_id) else 0
        self.stdout.write(f"replayed {seen} cards, {changed} changed")
