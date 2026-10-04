"""python manage.py rebuild_coverage [--user UUID]: recompute derived coverage data from the event ledger."""

from django.core.management.base import BaseCommand

from modules.coverage import services
from modules.coverage.models import Enrollment


class Command(BaseCommand):
    help = "Rebuild topic progress, chapter progress and roll-ups from the ledger (the source of truth)."

    def add_arguments(self, parser):
        parser.add_argument("--user", help="Only this student (Supabase user UUID).")

    def handle(self, *args, user, **options):
        qs = Enrollment.objects.select_related("scheme__level")
        if user:
            qs = qs.filter(user_id=user)
        count = 0
        for enrollment in qs.iterator():
            services.rebuild_enrollment(enrollment)
            count += 1
        self.stdout.write(f"Rebuilt {count} enrolment(s).")
