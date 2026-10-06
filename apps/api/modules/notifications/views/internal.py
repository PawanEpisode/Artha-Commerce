"""
Endpoints for machines, not students (FR-N16): the delayed queue fires a job, the scheduler runs the sweep. No student
authentication, no throttle, no UI flag gate, and not part of CORS (`CORS_URLS_REGEX` in settings). The kill switches
are applied inside the job, so a switched-off feature answers 200 and records `skipped` instead of making the queue retry.
"""

from __future__ import annotations

from rest_framework.response import Response
from rest_framework.views import APIView

from ..errors import InternalUnauthorized
from ..scheduling import auth, jobs, sweep


class InternalView(APIView):
    authentication_classes: list = []
    permission_classes: list = []
    throttle_classes: list = []


class JobFireView(InternalView):
    """POST from the queue, signed. 200 for every outcome except a transient failure (503, so the queue retries)."""

    def post(self, request, job_id):
        if not auth.verify_queue_request(request, job_id):
            raise InternalUnauthorized
        result = jobs.fire_job(job_id)
        return Response({"status": result.outcome.value, "reason": result.reason, "delivery": result.delivery})


class SweepView(InternalView):
    """GET (Vercel cron) or POST (pg_cron) with `Authorization: Bearer <CRON_SECRET>`. Bounded and idempotent."""

    def _run(self, request):
        if not auth.verify_cron_request(request):
            raise InternalUnauthorized
        run = sweep.run_sweep()
        return Response({"fired": run.fired, "skipped": run.skipped, "failed": run.failed, "more": run.more})

    get = post = _run
