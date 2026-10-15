"""
Management command to ensure monthly range partitions exist for practice_attemptanswer (F-06 slice 10).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time

from django.core.management.base import BaseCommand
from django.db import connection


def add_months(d: date, n: int) -> date:
    month = d.month - 1 + n
    year = d.year + month // 12
    month = month % 12 + 1
    return date(year, month, 1)


def get_month_range(year: int, month: int) -> tuple[datetime, datetime]:
    start_date = date(year, month, 1)
    end_date = add_months(start_date, 1)
    start_dt = datetime.combine(start_date, time.min, tzinfo=UTC)
    end_dt = datetime.combine(end_date, time.min, tzinfo=UTC)
    return start_dt, end_dt


class Command(BaseCommand):
    help = "Ensure monthly range partitions exist for practice_attemptanswer on PostgreSQL."

    def add_arguments(self, parser):
        parser.add_argument(
            "--months-ahead",
            type=int,
            default=3,
            help="Number of future months to pre-create partitions for (default: 3).",
        )
        parser.add_argument(
            "--months-behind",
            type=int,
            default=1,
            help="Number of past months to ensure exist (default: 1).",
        )

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            self.stdout.write(
                self.style.WARNING(f"Database vendor is {connection.vendor}; skipping partition creation.")
            )
            return

        months_ahead = options["months_ahead"]
        months_behind = options["months_behind"]

        today = date.today()
        current_first = date(today.year, today.month, 1)

        created_count = 0
        with connection.cursor() as cursor:
            # Check if practice_attemptanswer is partitioned
            cursor.execute(
                """
                SELECT c.relkind
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relname = 'practice_attemptanswer'
                """
            )
            row = cursor.fetchone()
            if not row or row[0] != "p":
                self.stdout.write(
                    self.style.WARNING("practice_attemptanswer is not a partitioned table ('relkind != p'); skipping.")
                )
                return

            for delta in range(-months_behind, months_ahead + 1):
                target_month = add_months(current_first, delta)
                y, m = target_month.year, target_month.month
                part_name = f"practice_attemptanswer_y{y}m{m:02d}"
                start_dt, end_dt = get_month_range(y, m)

                sql = f"""
                    CREATE TABLE IF NOT EXISTS {part_name}
                    PARTITION OF practice_attemptanswer
                    FOR VALUES FROM ('{start_dt.isoformat()}') TO ('{end_dt.isoformat()}');
                """
                cursor.execute(sql)
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"Partition verified/created: {part_name}"))

        self.stdout.write(self.style.SUCCESS(f"Done. Processed {created_count} partitions."))
