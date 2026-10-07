"""python manage.py load_motivation_seed [paths...]: load the starter motivation library as drafts. Idempotent."""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ...services import motivation

SEED_DIR = Path(__file__).resolve().parents[2] / "seed" / "motivation"


class Command(BaseCommand):
    help = (
        "Load the motivation seed files as DRAFT messages (never published, nothing is sent from a draft). A line that "
        "is already there is left untouched, so running it twice changes nothing. An editor reviews and publishes the "
        "drafts in the Django admin: Notifications, Messages."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "paths", nargs="*", help="Seed files. Defaults to every file in notifications/seed/motivation."
        )

    def handle(self, *args, paths, **options):
        files = [Path(p) for p in paths] or sorted(SEED_DIR.glob("*.json"))
        if not files:
            raise CommandError("No seed files found.")
        total = motivation.SeedResult()
        for file in files:
            try:
                result = motivation.load_seed(json.loads(file.read_text()), source=file.name)
            except (OSError, ValueError) as exc:  # unreadable file, bad JSON or a SeedError (a ValueError)
                raise CommandError(f"{file.name}: {exc}") from None
            total += result
            self.stdout.write(f"{file.name}: {result.created} new, {result.existing} already there")
            for line in result.skipped:
                self.stderr.write(f"skipped: {line}")
        self.stdout.write(
            f"Done: {total.created} drafts created, {total.existing} already there, {len(total.skipped)} file(s) "
            "skipped. Nothing is published; an editor does that in the admin."
        )
