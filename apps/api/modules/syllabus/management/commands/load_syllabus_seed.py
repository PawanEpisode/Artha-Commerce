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

    def handle(self, *args, paths, publish, **options):
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
