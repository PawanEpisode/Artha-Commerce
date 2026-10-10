"""
Load platform deck seed files: `python manage.py load_recall_seed [files...] [--publish] [--dry-run]`.

Without files it reads every `*.json` directly in `modules/recall/seed` whose name starts with neither an underscore nor `sample_`
(the sample file loads only with `--include-sample`). Decks load as
drafts; `--publish` also publishes them (the rights gate still applies). Safe to repeat: items match on `ref`, decks on `slug`.
A file with `"sample": true` is never published unless `--include-sample` is given.
"""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from modules.recall.services import seed

SEED_DIR = Path(__file__).resolve().parents[2] / "seed"


def _expand(files, include_sample):
    """Named files stay as given; a named folder becomes every `*.json` inside it (per-paper seed folders, e.g.
    `seed/cma-final-paper13/`), skipping names that start with `_`, and `sample_` unless asked for."""
    out = []
    for f in files:
        p = Path(f)
        if p.is_dir():
            out += sorted(
                q
                for q in p.rglob("*.json")
                if not q.name.startswith("_") and (include_sample or not q.name.startswith("sample_"))
            )
        else:
            out.append(p)
    return out


class _Rollback(Exception):  # noqa: N818 - control flow for --dry-run
    pass


class Command(BaseCommand):
    help = "Load platform deck seed files as drafts (idempotent on item `ref` and deck `slug`)."

    def add_arguments(self, parser):
        parser.add_argument(
            "files", nargs="*", help="Seed files, or a folder (every *.json inside it, e.g. seed/cma-final-paper13). Default: every non-underscore *.json directly in modules/recall/seed."
        )
        parser.add_argument(
            "--publish", action="store_true", help="Also publish the loaded drafts (rights gate applies)."
        )
        parser.add_argument(
            "--include-sample",
            action="store_true",
            help="Include the sample file when no files are named, and allow --publish for files marked sample.",
        )
        parser.add_argument("--dry-run", action="store_true", help="Do everything, then roll the database back.")

    def handle(self, *args, files=(), publish=False, include_sample=False, dry_run=False, **options):
        paths = _expand(files, include_sample) or sorted(
            p
            for p in SEED_DIR.glob("*.json")
            if not p.name.startswith("_") and (include_sample or not p.name.startswith("sample_"))
        )
        if not paths:
            raise CommandError(f"No seed files found in {SEED_DIR}.")
        failed = False
        for path in paths:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise CommandError(f"{path}: {exc}") from exc
            try:
                with transaction.atomic():
                    report = seed.load_seed(data, publish=publish, include_sample=include_sample)
                    if dry_run:
                        raise _Rollback
            except _Rollback:
                pass
            self.stdout.write(f"{path.name}{' (sample)' if report.sample else ''}{' [dry run]' if dry_run else ''}")
            for d in report.decks:
                line = (
                    f"  {d.slug}: items +{d.items_created} ~{d.items_updated} ={d.items_unchanged}"
                    f", draft v{d.draft_version_no or '-'}, live v{d.published_version_no or '-'}"
                )
                self.stdout.write(line + (f"  [{d.skipped}]" if d.skipped else ""))
                for err in d.errors:
                    failed = True
                    self.stderr.write(f"    ERROR {err}")
        if failed:
            raise CommandError("Some decks were not loaded. Fix the file and run again; nothing partial was kept.")
