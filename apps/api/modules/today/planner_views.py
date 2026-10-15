"""
Thin views for `/api/v1/today/planner/` (PRD slice 17). Same shape as `views.py`: auth, the `today_planner` flag (fails closed until
the owner opens the beta), parse, call a service or a selector, serialise. `GET` never writes.
"""

from __future__ import annotations

from core.permissions import flag_required
from django.utils import timezone
from rest_framework import status as http
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle, UserRateThrottle

from . import adaptive_services, generation, planner_selectors, planner_services, serializers
from . import planner_serializers as ps
from .adapters import tracking as tracking_adapter
from .errors import StudyPlanNotFound
from .views import TodayView

PLANNER_FLAG = "today_planner"


class PlannerView(TodayView):
    permission_classes = [IsAuthenticated, flag_required(PLANNER_FLAG, strict=True)]
    throttle_classes = [UserRateThrottle, ScopedRateThrottle]
    throttle_scope = "today_read"

    def payload(self, user_id, plan, now):
        today, tz = generation.student_today(user_id, now)
        last = tracking_adapter.local_date(plan.last_replanned_at, tz) if plan.last_replanned_at else None
        return ps.plan_payload(plan, today=today, tz=tz, now=now, last_replanned_on=last)


class PlannerRootView(PlannerView):
    """GET: the plan, read only. POST: make it (or change the daily minutes). Idempotent."""

    @property
    def throttle_scope(self):
        return "today_read" if self.request.method == "GET" else "today_write"

    def get(self, request):
        plan = planner_selectors.active_plan(request.user.id)
        if plan is None:
            raise StudyPlanNotFound
        return Response(self.payload(request.user.id, plan, timezone.now()))

    def post(self, request):
        data = self.parse(ps.CreatePlanSerializer, request.data)
        now = timezone.now()
        result = planner_services.create_plan(request.user.id, daily_minutes=data.get("daily_minutes"), now=now)
        body = self.payload(request.user.id, result.plan, now)
        body["created"] = result.created
        return Response(body, status=http.HTTP_201_CREATED if result.created else http.HTTP_200_OK)


class ReplanView(PlannerView):
    """The student's own "Re-plan". Always records what moved; with a shortfall it answers the options to choose from."""

    throttle_scope = "today_replan"

    def post(self, request):
        self.parse(ps.ReplanSerializer, request.data)
        now = timezone.now()
        result = planner_services.replan(request.user.id, trigger="manual", now=now)
        body = self.payload(request.user.id, result.plan, now)
        body["replan"] = ps.event_dict(result.event) if result.event is not None else None
        return Response(body)


class OptionView(PlannerView):
    """Apply the option the student picked (or `none`). Applied once: a second call is `409 option_expired`."""

    throttle_scope = "today_write"

    def post(self, request):
        data = self.parse(ps.ChooseOptionSerializer, request.data)
        now = timezone.now()
        result = planner_services.choose_option(request.user.id, data["event_id"], data["option"], now=now)
        body = self.payload(request.user.id, result.plan, now)
        body["replan"] = ps.event_dict(result.event)
        return Response(body)


class EventsView(PlannerView):
    """The re-plan history of the active plan, newest first."""

    def get(self, request):
        query = self.parse(ps.EventsQuerySerializer, request.query_params)
        plan = planner_selectors.active_plan(request.user.id)
        if plan is None:
            raise StudyPlanNotFound
        return Response(ps.events_payload(planner_selectors.events_of(plan, query["limit"]), now=timezone.now()))


# ---- day feedback, adaptive budget, bonus round (R2, behind the same flag) -------------------------------------------------


class FeedbackView(PlannerView):
    """One tap after the day: too much, just right, too little. Answers the budget suggestion it may have produced."""

    throttle_scope = "today_write"

    def post(self, request):
        data = self.parse(serializers.FeedbackSerializer, request.data)
        now = timezone.now()
        result = adaptive_services.record_feedback(request.user.id, data["rating"], day=data.get("date"), now=now)
        return Response(
            {
                "version": ps.PLANNER_VERSION,
                "server_time": now.isoformat(),
                "date": result.feedback.local_date.isoformat(),
                "rating": result.feedback.rating,
                "suggestion": result.suggestion,
            }
        )


class BudgetSuggestionView(PlannerView):
    """GET: the standing suggestion or `null`. POST `{accept}`: apply it (the minutes setting) or dismiss it."""

    @property
    def throttle_scope(self):
        return "today_read" if self.request.method == "GET" else "today_write"

    def get(self, request):
        return Response(
            {
                "version": ps.PLANNER_VERSION,
                "server_time": timezone.now().isoformat(),
                "suggestion": adaptive_services.current_suggestion(request.user.id),
            }
        )

    def post(self, request):
        data = self.parse(serializers.SuggestionAnswerSerializer, request.data)
        answered = adaptive_services.answer_suggestion(request.user.id, accept=data["accept"])
        return Response(
            {"version": ps.PLANNER_VERSION, "server_time": timezone.now().isoformat(), "suggestion": answered}
        )


class BonusView(PlannerView):
    """ "Do a little more": up to 3 extra tasks within 20 minutes that never count toward the day."""

    throttle_scope = "today_write"

    def post(self, request):
        self.parse(serializers.BonusSerializer, request.data)
        now = timezone.now()
        plan, added = adaptive_services.add_bonus(request.user.id, now=now)
        payload = serializers.plan_payload(plan, user_id=request.user.id, now=now)
        payload["bonus"] = {"added": added}
        return Response(payload)
