"""python manage.py load_syllabus_seed [--publish] [paths...]: idempotent loader for modules/syllabus/seed/**/*.json."""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from modules.syllabus import services
from modules.syllabus.services import SchemeStateError

SEED_DIR = Path(__file__).resolve().parents[2] / "seed"


class Command(BaseCommand):
    help = "Load syllabus scheme files (idempotent, keyed on stable keys). New schemes stay draft unless --publish."

    def add_arguments(self, parser):
        parser.add_argument("paths", nargs="*", help="Seed files. Defaults to every file under modules/syllabus/seed.")
        parser.add_argument("--publish", action="store_true", help="Publish loaded draft schemes (after human review).")
        parser.add_argument(
            "--prune-legacy",
            action="store_true",
            help="Delete the old placeholder schemes ('indicative', '2023-sample') that earlier seed files created. "
            "Schemes with enrolled students are kept. Combine with --dry-run to preview.",
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="With --prune-legacy: only list what would be deleted."
        )

    def handle(self, *args, paths, publish, prune_legacy=False, dry_run=False, **options):
        if prune_legacy and dry_run:
            self._prune(dry_run=True)
            return
        files = [Path(p) for p in paths] or sorted(SEED_DIR.rglob("*.json"))
        if not files:
            raise CommandError("No seed files found.")
        for file in files:
            data = json.loads(file.read_text())
            scheme = services.load_scheme_from_dict(data)
            if publish and scheme.status == "draft":
                try:
                    services.publish_scheme(scheme)
                except SchemeStateError as exc:
                    # The scheme stays loaded as a draft; only the publish step was refused.
                    self.stderr.write(f"{file.name}: not published: {'; '.join(exc.messages)}")
            self.stdout.write(
                f"{file.parent.parent.name}/{file.parent.name}/{file.name}: {scheme.code} [{scheme.status}]"
            )
        if prune_legacy:
            self._prune(dry_run=False)

    def _prune(self, *, dry_run: bool):
        results = services.prune_legacy_schemes(dry_run=dry_run)
        for scheme, action in results:
            self.stdout.write(f"legacy {scheme.level.course.code}/{scheme.level.code} {scheme.code}: {action}")
        if not results:
            self.stdout.write("No legacy placeholder schemes found.")
