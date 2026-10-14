"""
Thin views for /api/v1/today/. Auth, the `today_plan` flag (fails closed until the owner opens the beta), parse, call a service or a
selector, serialise. `GET` views never write (PRD section 9, audit AUD-014); generation is the explicit, idempotent `POST open/`.
"""

from __future__ import annotations

from datetime import timedelta

from django.http import HttpResponse
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from core.permissions import flag_required

from . import generation, selectors, serializers, services
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
        payload = serializers.plan_payload(result.plan, user_id=request.user.id, now=now)
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
