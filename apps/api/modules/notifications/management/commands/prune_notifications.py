"""Delete expired notification rows in batches (FR-N24). Safe to run again and again; `--dry-run` only counts."""

from django.core.management.base import BaseCommand, CommandError

from ...domain import retention
from ...services.retention import prune


class Command(BaseCommand):
    help = "Prune deliveries (90 days), notifications (180), finished jobs (30) and revoked devices (30)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Print counts per table and delete nothing.")
        parser.add_argument(
            "--batch", type=int, default=retention.BATCH_SIZE, help=f"Rows per delete, at most {retention.BATCH_SIZE}."
        )
        parser.add_argument("--max-rows", type=int, default=None, help="Stop after this many rows in total.")

    def handle(self, *args, dry_run, batch, max_rows, **options):
        try:
            result = prune(dry_run=dry_run, batch=batch, max_rows=max_rows)
        except ValueError as exc:
            raise CommandError(str(exc)) from None
        verb = "would delete" if dry_run else "deleted"
        for table in ("deliveries", "notifications", "jobs", "revoked_devices", "messages_shown"):
            self.stdout.write(f"{table}: {verb} {getattr(result, table)}")
        if result.more:
            self.stdout.write("more rows remain; run it again")
