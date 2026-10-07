"""
Runs queued `core_job` rows until stopped (the always-on worker) or until the queue is empty (`--once`, for cron and tests).

    python manage.py run_worker                     # forever, polls every 2 seconds when idle
    python manage.py run_worker --once              # drain what is due now, then exit
    python manage.py run_worker --types notes.ocr   # only some job types
"""

import os
import socket
import time

from django.core.management.base import BaseCommand

from core import jobs


class Command(BaseCommand):
    help = "Claim and run background jobs from core_job."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Exit when no job is due.")
        parser.add_argument("--types", nargs="*", default=None, help="Only claim these job types.")
        parser.add_argument("--sleep", type=float, default=2.0, help="Seconds to wait when idle (default 2).")
        parser.add_argument("--max-jobs", type=int, default=0, help="Stop after this many jobs (0 = no limit).")

    def handle(self, *args, once, types, sleep, max_jobs, **options):
        worker = f"{socket.gethostname()}:{os.getpid()}"
        ran = 0
        while True:
            job = jobs.claim_next(types=types, worker=worker)
            if job is None:
                if once:
                    break
                time.sleep(sleep)
                continue
            status = jobs.run_job(job)
            ran += 1
            self.stdout.write(f"{job.type} {status}")
            if max_jobs and ran >= max_jobs:
                break
        self.stdout.write(self.style.SUCCESS(f"Ran {ran} job(s)."))
