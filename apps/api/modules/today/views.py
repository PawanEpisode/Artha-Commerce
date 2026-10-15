"""
Thin views for /api/v1/today/. Auth, the `today_plan` flag (fails closed until the owner opens the beta), parse, call a service or a
selector, serialise. `GET` views never write (PRD section 9, audit AUD-014); generation is the explicit, idempotent `POST open/`.
"""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings as django_settings
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status as http
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from core.http import request_has_secret
from core.permissions import flag_required

from . import actions, generation, lifecycle, selectors, serializers, services
from .domain import constants as c
from .errors import InvalidDate, PlanNotGenerated

TODAY_FLAG = "today_plan"


class TodayView(APIView):
    permission_classes = [IsAuthenticated, flag_required(TODAY_FLAG, strict=True)]

    def parse(self, serializer_class, data):
        s = serializer_class(data=data)
        s.is_valid(raise_exception=True)
        return s.validated_data


class ReadView(TodayView):
    throttle_classes = [UserRateThrottle, ScopedRateThrottle]
    throttle_scope = "today_read"


class WriteView(TodayView):
    throttle_classes = [UserRateThrottle, ScopedRateThrottle]
    throttle_scope = "today_write"


class OpenView(WriteView):
    """The app-open call: ensure today's plan exists and return it. Idempotent; a second call returns the same plan."""

    def post(self, request):
        data = self.parse(serializers.OpenSerializer, request.data)
        now = timezone.now()
        result = services.open_today(request.user.id, local_date=data.get("date"), now=now)
        if result.plan is None:
            return Response(
                serializers.empty_state_payload(result.state, local_date=result.local_date, tz=result.tz, now=now)
            )
        lite = data["lite"] or selectors.get_settings(request.user.id).lite_mode == "on"
        payload = serializers.plan_payload(result.plan, user_id=request.user.id, now=now, lite=lite)
        payload["created"] = result.created
        return Response(payload)


class PlanView(ReadView):
    """The plan for a date, read only. 404 `plan_not_generated` when there is none: the web then calls `open/`."""

    def get(self, request):
        query = self.parse(serializers.DateQuerySerializer, request.query_params)
        now = timezone.now()
        today, _tz = generation.student_today(request.user.id, now)
        day = query.get("date", today)
        plan = selectors.get_plan(request.user.id, day)
        if plan is None or plan.status == "draft":
            raise PlanNotGenerated
        lite = query["lite"] or selectors.get_settings(request.user.id).lite_mode == "on"
        payload = serializers.plan_payload(plan, user_id=request.user.id, now=now, lite=lite)
        etag = serializers.etag_of(payload)
        if request.headers.get("If-None-Match") == etag:
            response = HttpResponse(status=304)
        else:
            response = Response(payload)
        response["ETag"] = etag
        response["Cache-Control"] = "private, no-cache"
        return response


class CelebratedView(WriteView):
    """The web shows the day-complete celebration once, then records it here so no other device shows it again."""

    def post(self, request):
        self.parse(serializers.CelebratedSerializer, request.data)
        now = timezone.now()
        plan = services.mark_celebrated(request.user.id, now=now)
        if plan is None:
            raise PlanNotGenerated
        return Response(
            {"version": plan.version, "server_time": now.isoformat(), "celebrated_at": plan.celebrated_at.isoformat()}
        )


class PreviewView(ReadView):
    """What a later day would hold (at most 14 days ahead), computed and thrown away."""

    def get(self, request):
        query = self.parse(serializers.PreviewQuerySerializer, request.query_params)
        now = timezone.now()
        today, tz = generation.student_today(request.user.id, now)
        day = query["date"]
        if not today < day <= today + timedelta(days=c.PREVIEW_MAX_DAYS_AHEAD):
            raise InvalidDate(
                "Preview a day after today and within two weeks.",
                extra={
                    "date": [
                        f"Use a date from {(today + timedelta(days=1)).isoformat()} to {(today + timedelta(days=c.PREVIEW_MAX_DAYS_AHEAD)).isoformat()}."
                    ]
                },
            )
        gen = generation.generate(request.user.id, day, tz, plan=None, is_preview=True)
        return Response(
            serializers.preview_payload(request.user.id, gen, selectors.own_tasks_on(request.user.id, day), now=now)
        )


class HistoryView(ReadView):
    """Day counters for the week strip and recaps. A day without a plan is absent."""

    def get(self, request):
        query = self.parse(serializers.HistoryQuerySerializer, request.query_params)
        now = timezone.now()
        today, _tz = generation.student_today(request.user.id, now)
        last = query.get("to", today)
        first = query.get("first", last - timedelta(days=6))
        if first > last or (last - first).days + 1 > c.HISTORY_MAX_DAYS:
            raise InvalidDate(
                "Ask for at most 92 days, oldest first.",
                extra={"from": [f"Use a range of 1 to {c.HISTORY_MAX_DAYS} days."]},
            )
        rows = selectors.completion_history(request.user.id, first, last, today)
        return Response(serializers.history_payload(rows, first=first, last=last, now=now))


class SettingsView(TodayView):
    """The student's own settings. GET never creates the row; PUT creates it on the first save."""

    throttle_classes = [UserRateThrottle, ScopedRateThrottle]

    @property
    def throttle_scope(self):
        return "today_read" if self.request.method == "GET" else "today_write"

    def get(self, request):
        return Response(serializers.settings_payload(selectors.get_settings(request.user.id), now=timezone.now()))

    def put(self, request):
        values = self.parse(serializers.SettingsSerializer, request.data)
        row = services.save_settings(request.user.id, values)
        return Response(serializers.settings_payload(row, now=timezone.now()))


# ---- task actions -----------------------------------------------------------------------------------------------------------


class TaskActionView(WriteView):
    """Parse, call the action service, answer `{task, counts, ...}`. The services own every rule."""

    serializer_class = serializers.ActionSerializer

    def post(self, request, task_id):
        data = self.parse(self.serializer_class, request.data)
        now = timezone.now()
        task, extra = self.act(request.user.id, task_id, data, now)
        return Response(serializers.task_response(task, now=now, **extra))

    def act(self, user_id, task_id, data, now):  # pragma: no cover - overridden
        raise NotImplementedError


class StartView(TaskActionView):
    def act(self, user_id, task_id, data, now):
        result = actions.start_task(
            user_id, task_id, client_id=data["client_id"], client_ts=data.get("client_ts"), now=now
        )
        return result.task, {"link": result.link}


class CompleteView(TaskActionView):
    serializer_class = serializers.CompleteSerializer

    def act(self, user_id, task_id, data, now):
        task = actions.complete_task(
            user_id,
            task_id,
            client_id=data["client_id"],
            client_ts=data.get("client_ts"),
            run_manual_action=data["run_manual_action"],
            now=now,
        )
        return task, {}


class SkipView(TaskActionView):
    serializer_class = serializers.SkipSerializer

    def act(self, user_id, task_id, data, now):
        result = actions.skip_task(
            user_id,
            task_id,
            client_id=data["client_id"],
            reason=data.get("reason"),
            client_ts=data.get("client_ts"),
            now=now,
        )
        return result.task, {"suppressed_days": result.suppressed_days}


class SnoozeView(TaskActionView):
    serializer_class = serializers.SnoozeSerializer

    def act(self, user_id, task_id, data, now):
        task = actions.snooze_task(
            user_id, task_id, client_id=data["client_id"], until=data["until"], client_ts=data.get("client_ts"), now=now
        )
        return task, {}


class UndoView(WriteView):
    def post(self, request, task_id):
        data = self.parse(serializers.UndoSerializer, request.data)
        now = timezone.now()
        task = actions.undo_task(
            request.user.id, task_id, client_id=data["client_id"], from_state=data["from_state"], now=now
        )
        return Response(serializers.task_response(task, now=now))


class SwapView(WriteView):
    def post(self, request, task_id):
        data = self.parse(serializers.ActionSerializer, request.data)
        now = timezone.now()
        result = actions.swap_task(
            request.user.id, task_id, client_id=data["client_id"], client_ts=data.get("client_ts"), now=now
        )
        body = serializers.task_response(result.old, now=now)
        return Response(
            {
                "version": body["version"],
                "server_time": body["server_time"],
                "old": body["task"],
                "new": serializers.task_dict(result.new),
                "counts": body["counts"],
            }
        )


class TasksView(WriteView):
    """POST: add an own task (201, or 200 for a retry of the same `client_id`)."""

    def post(self, request):
        data = self.parse(serializers.AddTaskSerializer, request.data)
        now = timezone.now()
        task, created = actions.add_task(
            request.user.id,
            client_id=data["client_id"],
            title=data["title"],
            local_date=data.get("date"),
            est_minutes=data["est_minutes"],
            subject_id=data["subject_id"],
            chapter_id=data["chapter_id"],
            now=now,
        )
        return Response(
            serializers.task_response(task, now=now), status=http.HTTP_201_CREATED if created else http.HTTP_200_OK
        )


class TaskDetailView(WriteView):
    """PATCH edits and DELETE removes an own task. Suggested tasks answer 403 `provider_task_readonly`."""

    def patch(self, request, task_id):
        data = dict(self.parse(serializers.EditTaskSerializer, request.data))
        version = data.pop("version")
        now = timezone.now()
        task = actions.edit_task(request.user.id, task_id, data, version=version, now=now)
        return Response(serializers.task_response(task, now=now))

    def delete(self, request, task_id):
        data = self.parse(serializers.DeleteSerializer, request.query_params)  # DELETE has no body (PRD section 9)
        now = timezone.now()
        result = actions.delete_task(request.user.id, task_id, client_id=data.get("client_id"), now=now)
        return Response(serializers.task_response(result.task, now=now, undo_until=result.undo_until.isoformat()))


class RegenerateView(WriteView):
    throttle_scope = "today_regen"

    def post(self, request):
        data = self.parse(serializers.RegenerateSerializer, request.data)
        now = timezone.now()
        plan, info = actions.regenerate(
            request.user.id,
            expected_generation=data["expected_generation"],
            reason=data["reason"],
            client_id=data["client_id"],
            now=now,
        )
        payload = serializers.plan_payload(plan, user_id=request.user.id, now=now)
        payload["regenerated"] = info
        return Response(payload)


TICK_HEADER = "X-Today-Tick-Secret"


class TickView(APIView):
    """
    Cron entry (Vercel Cron GET or a POST from any scheduler): closes finished days, pre-generates the new day's plans and prunes old
    rows. Authenticated by a shared secret, not a student token, open whatever the flag says (a student's data is housekept even
    with the flag off), bounded to about 20 seconds and safe to repeat or overlap.
    """

    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_classes: list = []
    throttle_scope = "none"  # no throttle: the secret is the gate (the contract test reads this)

    def _tick(self, request):
        if not request_has_secret(request, django_settings.TODAY_TICK_SECRET, TICK_HEADER):
            return Response({"error": {"code": "forbidden", "message": "Not allowed.", "details": None}}, status=403)
        return Response(lifecycle.tick())

    get = post = _tick
