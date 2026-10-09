"""Check the Python domain against the golden vectors the TypeScript twin also reads. Exit code 1 on any mismatch (CI gate)."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from modules.recall.domain.tests import test_vectors as tv


class Command(BaseCommand):
    help = "Verify fsrs6, folding and queue vectors against the domain."

    def handle(self, *args, **options):
        checks = [
            *[(c["name"], tv.test_fsrs6_history, (c,)) for c in tv.FS["cases"]],
            *[(f"interval {d}", tv.test_format_interval, (d, label)) for d, label in tv.FS["format_interval"]],
            *[(f"fuzz {c}/{r}", tv.test_fuzz_unit, (c, r, u)) for c, r, u in tv.FS["fuzz_unit"]],
            *[(c["name"], tv.test_folding, (c,)) for c in tv.FO["cases"]],
            *[(c["name"], tv.test_queue, (c,)) for c in tv.QU["cases"]],
        ]
        failed = []
        for name, fn, args_ in checks:
            try:
                fn(*args_)
            except AssertionError:
                failed.append(name)
        self.stdout.write(f"{len(checks) - len(failed)} of {len(checks)} vectors match")
        if failed:
            raise CommandError("Vectors that do not match: " + ", ".join(failed[:20]))
