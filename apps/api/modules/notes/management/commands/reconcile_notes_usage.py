"""Recomputes every student's notes counters from the tables and reports how many had drifted (the target is zero)."""

from django.core.management.base import BaseCommand

from modules.notes import jobs
from modules.notes.models import QuotaUsage


class Command(BaseCommand):
    help = "Recompute notes usage counters and print drift."

    def handle(self, *args, **options):
        users = drifted = 0
        for user_id in QuotaUsage.objects.values_list("pk", flat=True).iterator():
            users += 1
            drifted += jobs._reconcile_user(user_id)
        self.stdout.write(self.style.SUCCESS(f"Checked {users} student(s), {drifted} had drifted."))
