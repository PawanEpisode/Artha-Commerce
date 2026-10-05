"""
Thin views for /api/v1/focus/. Auth, the `focus_timer` flag, parse, call a service or selector, serialise. Domain errors
become the API's standard error shape; every timer answer carries `server_time` so the web can correct its clock.
"""

from __future__ import annotations

from django.http import HttpResponse
from rest_framework.exceptions import NotFound
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from core.feature_flags import flag_enabled
from modules.tracking import selectors as tracking_selectors
from modules.tracking import services as tracking
from modules.tracking.serializers import session_dict

from . import selectors, serializers, services
from .errors import FocusFeatureDisabled, TrackingError, to_api_exception

FOCUS_FLAG = "focus_timer"


class FocusEnabled(BasePermission):
    """The `focus_timer` flag, evaluated by PostHog for this student. Off means 403 `feature_disabled`."""

    def has_permission(self, request, view):
        if not flag_enabled(FOCUS_FLAG, request.user.id):
            raise FocusFeatureDisabled
        return True


class FocusView(APIView):
    permission_classes = [IsAuthenticated, FocusEnabled]

    def handle_exception(self, exc):
        if isinstance(exc, TrackingError):
            exc = to_api_exception(exc)
        return super().handle_exception(exc)

    def parse(self, serializer_class, data):
        s = serializer_class(data=data)
        s.is_valid(raise_exception=True)
        return s


class WriteView(FocusView):
    throttle_classes = [UserRateThrottle, ScopedRateThrottle]
    throttle_scope = "focus_write"


def _payload(user_id, timer, **extra) -> dict:
    now = services._now()
    settings = selectors.settings_or_default(user_id)
    return {
        "timer": selectors.timer_dict(timer, now) if timer else None,
        "idle": None if timer else selectors.idle_dict(settings, now),
        "live": tracking.live_timer_kind(user_id),
        "settings": selectors.settings_dict(settings),
        "server_time": now,
        **extra,
    }


class SettingsView(WriteView):
    def get(self, request):
        return Response(selectors.settings_dict(selectors.settings_or_default(request.user.id)))

    def put(self, request):
        changes = self.parse(serializers.SettingsSerializer, request.data).changes()
        settings, changed = services.update_settings(request.user.id, changes)
        return Response({**selectors.settings_dict(settings), "changed": changed})

    patch = put


class TimerView(FocusView):
    def get(self, request):
        q = self.parse(serializers.TimerQuerySerializer, request.query_params).validated_data
        return Response(_payload(request.user.id, services.sync(request.user.id, alive=q["alive"])))


class TimerStartView(WriteView):
    def post(self, request):
        s = self.parse(serializers.StartSerializer, request.data)
        d = s.validated_data
        timer, created = services.start(
            request.user.id,
            client_id=d["client_id"],
            phase=d["phase"],
            preset=d.get("preset"),
            custom=s.custom() or None,
            subject_id=d.get("subject_id"),
            chapter_id=d.get("chapter_id"),
            activity_type=d.get("activity_type"),
            at=d.get("at"),
        )
        return Response(_payload(request.user.id, timer), status=201 if created else 200)


class TimerPauseView(WriteView):
    def post(self, request):
        d = self.parse(serializers.ActionSerializer, request.data).validated_data
        return Response(
            _payload(request.user.id, services.pause(request.user.id, version=d.get("version"), at=d.get("at")))
        )


class TimerResumeView(WriteView):
    def post(self, request):
        d = self.parse(serializers.ActionSerializer, request.data).validated_data
        return Response(
            _payload(request.user.id, services.resume(request.user.id, version=d.get("version"), at=d.get("at")))
        )


class TimerExtendView(WriteView):
    def post(self, request):
        d = self.parse(serializers.ActionSerializer, request.data).validated_data
        return Response(_payload(request.user.id, services.extend(request.user.id, version=d.get("version"))))


class TimerCompleteView(WriteView):
    def post(self, request):
        d = self.parse(serializers.ActionSerializer, request.data).validated_data
        return Response(_payload(request.user.id, services.complete(request.user.id, version=d.get("version"))))


class TimerSkipBreakView(WriteView):
    def post(self, request):
        d = self.parse(serializers.ActionSerializer, request.data).validated_data
        return Response(_payload(request.user.id, services.skip_break(request.user.id, version=d.get("version"))))


class TimerHeartbeatView(WriteView):
    def post(self, request):
        return Response(_payload(request.user.id, services.sync(request.user.id, alive=True)))


class TimerClaimView(WriteView):
    def post(self, request):
        d = self.parse(serializers.ClaimSerializer, request.data).validated_data
        timer, outcome = services.claim(request.user.id, count=d["count"], version=d.get("version"))
        return Response(_payload(request.user.id, timer, outcome=outcome))


class TimerEndView(WriteView):
    def post(self, request):
        d = self.parse(serializers.EndSerializer, request.data).validated_data
        session, outcome = services.end(
            request.user.id,
            client_id=d.get("client_id"),
            version=d.get("version"),
            save=d["save"],
            reason=d["reason"],
        )
        return Response(
            _payload(
                request.user.id,
                None,
                outcome=outcome,
                session=session_dict(tracking_selectors.get_session(request.user.id, session.id)) if session else None,
            )
        )


class TimerContextView(WriteView):
    def patch(self, request):
        changes = self.parse(serializers.ContextSerializer, request.data).changes()
        version = changes.pop("version")
        return Response(
            _payload(request.user.id, services.change_context(request.user.id, version=version, changes=changes))
        )


class SessionListView(WriteView):
    """The history: finished Pomodoro rounds, newest first."""

    def get(self, request):
        q = self.parse(serializers.SessionListQuerySerializer, request.query_params).validated_data
        rows, next_cursor = tracking_selectors.list_sessions(
            request.user.id,
            cursor=q.get("cursor"),
            limit=q["limit"],
            start=q.get("from"),
            end=q.get("to"),
            subject_id=q.get("subject_id"),
            chapter_id=q.get("chapter_id"),
            source="pomodoro",
        )
        return Response({"results": [session_dict(s) for s in rows], "next_cursor": next_cursor})


class SessionDetailView(WriteView):
    def _own(self, request, session_id):
        session = tracking_selectors.get_session(request.user.id, session_id)
        if not session or session.source != "pomodoro":
            raise NotFound("Session not found.")
        return session

    def patch(self, request, session_id):
        self._own(request, session_id)
        changes = self.parse(serializers.SessionEditSerializer, request.data).changes()
        session = tracking.edit_session(request.user.id, session_id, changes)
        return Response(session_dict(tracking_selectors.get_session(request.user.id, session.id)))

    def delete(self, request, session_id):
        self._own(request, session_id)
        audit = tracking.delete_session(request.user.id, session_id)
        return Response({"undo_token": audit.id, "undo_until": audit.undo_until})


class DataView(APIView):
    """GET exports what the focus timer stores about the student; DELETE removes it. Not behind the flag."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(selectors.export_all(request.user.id))

    def delete(self, request):
        services.delete_all_for_user(request.user.id)
        return HttpResponse(status=204)
