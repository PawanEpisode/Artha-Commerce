"""
Thin views for /api/v1/tracking/. Auth, the `time_tracker` flag, parse, call a service or selector, serialise. Domain
errors become the API's standard error shape; reports answer with an ETag so an unchanged report costs a 304.
"""

from __future__ import annotations

import csv
from datetime import date, timedelta

from core.feature_flags import flag_enabled
from django.http import HttpResponse, StreamingHttpResponse
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from modules.coverage import selectors as coverage

from . import selectors, serializers, services
from .domain.reports import HOURS_DEFAULT_DAYS, RangeError
from .errors import FeatureDisabled, TrackingError, to_api_exception
from .serializers import session_dict, settings_dict

TRACKER_FLAG = "time_tracker"


class TrackerEnabled(BasePermission):
    """The `time_tracker` flag (FR-33), evaluated by PostHog for this student. Off means 403 `feature_disabled`."""

    def has_permission(self, request, view):
        if not flag_enabled(TRACKER_FLAG, request.user.id):
            raise FeatureDisabled
        return True


class TrackingView(APIView):
    permission_classes = [IsAuthenticated, TrackerEnabled]

    def handle_exception(self, exc):
        if isinstance(exc, TrackingError):
            exc = to_api_exception(exc)
        elif isinstance(exc, RangeError):
            wrapped = ValidationError({"detail": str(exc)})
            wrapped.default_code = exc.code
            exc = wrapped
        return super().handle_exception(exc)

    def parse(self, serializer_class, data):
        s = serializer_class(data=data)
        s.is_valid(raise_exception=True)
        return s

    def today(self, request) -> date:
        return services.local_today(request.user.id)

    def date_range(self, params, default_days: int = 7) -> tuple[date, date]:
        end = params.get("to") or self.today_cached
        start = params.get("from") or end - timedelta(days=default_days - 1)
        return start, end

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.today_cached = services.local_today(request.user.id)


class WriteView(TrackingView):
    throttle_classes = [UserRateThrottle, ScopedRateThrottle]
    throttle_scope = "tracking_write"


class ReportView(TrackingView):
    throttle_classes = [UserRateThrottle, ScopedRateThrottle]
    throttle_scope = "tracking_reports"

    def cached(self, request, start: date, end: date, build, *extra):
        """ETag flow: 304 when the student's data for this report has not changed, otherwise build and tag the answer."""
        stamp = selectors.report_stamp(
            request.user.id, start, end, request.path, sorted(request.query_params.items()), *extra
        )
        etag = f'W/"{stamp}"'
        if request.headers.get("If-None-Match") == etag:
            response = Response(status=status.HTTP_304_NOT_MODIFIED)
        else:
            response = Response(build())
        response["ETag"] = etag
        response["Cache-Control"] = (
            "private, no-cache"  # revalidate every time; the web caches 60 s and invalidates on writes
        )
        return response


def _now_iso():
    return services._now()


# --- Stopwatch ------------------------------------------------------------------------------------------------
def _stopwatch_payload(user_id, sw) -> dict:
    now = services._now()
    settings = selectors.settings_or_default(user_id)
    return {
        "stopwatch": selectors.stopwatch_dict(sw, now, settings) if sw else None,
        "live": services.live_timer_kind(user_id),
        "idle_minutes": settings.idle_minutes,
        "server_time": now,
    }


class StopwatchView(TrackingView):
    def get(self, request):
        q = self.parse(serializers.StopwatchQuerySerializer, request.query_params).validated_data
        sw = services.sync_stopwatch(request.user.id, alive=q["alive"], active=q["active"])
        return Response(_stopwatch_payload(request.user.id, sw))


class StopwatchStartView(WriteView):
    def post(self, request):
        d = self.parse(serializers.StopwatchStartSerializer, request.data).validated_data
        sw, created = services.start_stopwatch(
            request.user.id,
            client_id=d["client_id"],
            subject_id=d.get("subject_id"),
            chapter_id=d.get("chapter_id"),
            activity_type=d.get("activity_type"),
            at=d.get("at"),
        )
        return Response(_stopwatch_payload(request.user.id, sw), status=201 if created else 200)


class StopwatchPauseView(WriteView):
    def post(self, request):
        d = self.parse(serializers.StopwatchActionSerializer, request.data).validated_data
        sw = services.pause_stopwatch(request.user.id, version=d.get("version"), at=d.get("at"))
        return Response(_stopwatch_payload(request.user.id, sw))


class StopwatchResumeView(WriteView):
    def post(self, request):
        d = self.parse(serializers.StopwatchActionSerializer, request.data).validated_data
        sw = services.resume_stopwatch(request.user.id, version=d.get("version"), at=d.get("at"))
        return Response(_stopwatch_payload(request.user.id, sw))


class StopwatchStopView(WriteView):
    def post(self, request):
        d = self.parse(serializers.StopwatchStopSerializer, request.data).validated_data
        session, outcome = services.stop_stopwatch(
            request.user.id,
            client_id=d.get("client_id"),
            version=d.get("version"),
            save=d["save"],
            end_at=d.get("end_at"),
        )
        return Response(
            {"session": session_dict(session) if session else None, "outcome": outcome, "server_time": services._now()}
        )


class StopwatchContextView(WriteView):
    def patch(self, request):
        s = self.parse(serializers.StopwatchContextSerializer, request.data)
        changes = s.changes()
        version = changes.pop("version")
        sw = services.change_stopwatch_context(request.user.id, version=version, changes=changes)
        return Response(_stopwatch_payload(request.user.id, sw))


class StopwatchIdleView(WriteView):
    def post(self, request):
        d = self.parse(serializers.StopwatchIdleSerializer, request.data).validated_data
        sw = services.answer_idle(request.user.id, answer=d["answer"])
        return Response(_stopwatch_payload(request.user.id, sw))


# --- Sessions -------------------------------------------------------------------------------------------------
def _filters(q: dict) -> dict:
    return {
        "start": q.get("from"),
        "end": q.get("to"),
        "subject_id": q.get("subject_id"),
        "chapter_id": q.get("chapter_id"),
        "source": q.get("source"),
    }


class SessionListView(WriteView):
    def get(self, request):
        q = self.parse(serializers.SessionListQuerySerializer, request.query_params).validated_data
        rows, next_cursor = selectors.list_sessions(
            request.user.id, cursor=q.get("cursor"), limit=q["limit"], **_filters(q)
        )
        return Response({"results": [session_dict(s) for s in rows], "next_cursor": next_cursor})

    def post(self, request):
        d = self.parse(serializers.ManualSessionSerializer, request.data).validated_data
        session, created = services.add_manual(request.user.id, **d)
        return Response(session_dict(session), status=201 if created else 200)


class SessionDetailView(WriteView):
    def _get(self, request, session_id):
        session = selectors.get_session(request.user.id, session_id)
        if not session:
            raise NotFound("Session not found.")
        return session

    def get(self, request, session_id):
        return Response(session_dict(self._get(request, session_id)))

    def patch(self, request, session_id):
        changes = self.parse(serializers.SessionEditSerializer, request.data).changes()
        session = services.edit_session(request.user.id, session_id, changes)
        return Response(session_dict(selectors.get_session(request.user.id, session.id)))

    def delete(self, request, session_id):
        audit = services.delete_session(request.user.id, session_id)
        return Response({"undo_token": audit.id, "undo_until": audit.undo_until})


class AutoCaptureView(WriteView):
    """Opt-in auto capture: time actively spent on a chapter page, reported in short chunks."""

    def post(self, request):
        d = self.parse(serializers.AutoCaptureSerializer, request.data).validated_data
        session, outcome = services.add_auto(
            request.user.id,
            client_id=d["client_id"],
            chapter_id=d["chapter_id"],
            started_at=d["started_at"],
            seconds=d["seconds"],
        )
        return Response(
            {"session": session_dict(session) if session else None, "outcome": outcome, "server_time": services._now()},
            status=201 if outcome == "saved" and session else 200,
        )


class SessionUndoView(WriteView):
    def post(self, request):
        d = self.parse(serializers.UndoSerializer, request.data).validated_data
        restored = services.undo(request.user.id, d["undo_token"], d.get("notes"))
        rows = [selectors.get_session(request.user.id, s.id) for s in restored]
        return Response({"sessions": [session_dict(s) for s in rows]})


class SessionMergeView(WriteView):
    def post(self, request):
        s = self.parse(serializers.MergeSerializer, request.data)
        changes = s.changes()
        ids = changes.pop("session_ids")
        merged = services.merge_sessions(request.user.id, ids, changes)
        audit_token = (
            selectors.SessionAudit.objects.filter(user_id=request.user.id, action="merge")
            .order_by("-created_at")
            .first()
        )
        return Response(
            {
                "session": session_dict(selectors.get_session(request.user.id, merged.id)),
                "undo_token": audit_token.id if audit_token else None,
            },
            status=201,
        )


class SessionSplitView(WriteView):
    def post(self, request, session_id):
        d = self.parse(serializers.SplitSerializer, request.data).validated_data
        first, second, audit = services.split_session(request.user.id, session_id, d["at"])
        rows = [selectors.get_session(request.user.id, s.id) for s in (first, second)]
        return Response({"sessions": [session_dict(s) for s in rows], "undo_token": audit.id}, status=201)


class _Echo:
    def write(self, value):
        return value


def _csv_response(name: str, header: list[str], rows) -> StreamingHttpResponse:
    writer = csv.writer(_Echo())

    def stream():
        yield writer.writerow(header)
        for row in rows:
            yield writer.writerow([_safe(v) for v in row])

    response = StreamingHttpResponse(stream(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{name}"'
    return response


def _safe(value):
    """Spreadsheet formula injection guard: a cell that starts with = + - or @ is prefixed with a quote."""
    if isinstance(value, str) and value[:1] in {"=", "+", "-", "@"}:
        return "'" + value
    return value


class SessionExportView(TrackingView):
    throttle_classes = [UserRateThrottle, ScopedRateThrottle]
    throttle_scope = "tracking_export"

    def get(self, request):
        q = self.parse(serializers.SessionListQuerySerializer, request.query_params).validated_data
        rows = selectors.export_rows(request.user.id, **_filters(q))
        notes = q["include_notes"]
        header = ["date", "start", "end", "minutes", "source", "activity", "subject", "chapter", "edited", "timezone"]
        if notes:
            header.append("note")

        def lines():
            for s in rows:
                row = [
                    s.study_date.isoformat(),
                    s.started_at.isoformat(),
                    s.ended_at.isoformat(),
                    round(s.focus_seconds / 60, 1),
                    s.source,
                    s.activity_type,
                    s.subject.name if s.subject_id else "",
                    s.chapter.name if s.chapter_id else "",
                    "yes" if s.is_edited else "",
                    s.tz,
                ]
                if notes:
                    row.append(s.note)
                yield row

        return _csv_response("study-sessions.csv", header, lines())


# --- Goals and settings ---------------------------------------------------------------------------------------
def _goals_payload(user_id, today) -> dict:
    return {
        "goals": [serializers.goal_dict(g) for g in selectors.goals_in_force(user_id, today)],
        "progress": selectors.goals_progress(user_id, today),
    }


class GoalsView(WriteView):
    def get(self, request):
        return Response(_goals_payload(request.user.id, self.today_cached))

    def put(self, request):
        d = self.parse(serializers.GoalsSerializer, request.data).validated_data
        services.set_goals(request.user.id, d["goals"])
        return Response(_goals_payload(request.user.id, self.today_cached))


class SettingsView(WriteView):
    def get(self, request):
        return Response(settings_dict(services.get_or_create_settings(request.user.id)))

    def put(self, request):
        s = self.parse(serializers.SettingsSerializer, request.data)
        settings, changed = services.update_settings(request.user.id, s.changes())
        return Response({**settings_dict(settings), "changed_keys": changed})

    patch = put

    def delete(self, request):
        return Response(settings_dict(services.reset_settings(request.user.id)))


# --- Reports --------------------------------------------------------------------------------------------------
class SummaryView(ReportView):
    def get(self, request):
        q = self.parse(serializers.ReportQuerySerializer, request.query_params).validated_data
        start, end = self.date_range(q)
        return self.cached(
            request,
            start - (end - start) - timedelta(days=1),
            end,
            lambda: selectors.summary(
                request.user.id, start, end, compare=q["compare"], verified_only=q["verified_only"]
            ),
        )


class SeriesView(ReportView):
    def get(self, request):
        q = self.parse(serializers.ReportQuerySerializer, request.query_params).validated_data
        start, end = self.date_range(q, 30)
        return self.cached(
            request,
            start,
            end,
            lambda: selectors.series(
                request.user.id, start, end, group=q["group"], by=q["by"], verified_only=q["verified_only"]
            ),
        )


class BreakdownView(ReportView):
    def get(self, request):
        q = self.parse(serializers.ReportQuerySerializer, request.query_params).validated_data
        start, end = self.date_range(q, 30)
        by = q["by"] if q["by"] != "total" else "subject"
        parent = q.get("parent_id")
        parent_value = None
        if parent:
            try:
                import uuid

                parent_value = uuid.UUID(parent)
            except ValueError:
                parent_value = parent
        return self.cached(
            request,
            start,
            end,
            lambda: selectors.breakdown(
                request.user.id, start, end, by=by, parent_id=parent_value, verified_only=q["verified_only"]
            ),
        )


class HeatmapView(ReportView):
    def get(self, request):
        q = self.parse(serializers.ReportQuerySerializer, request.query_params).validated_data
        end = q.get("to") or self.today_cached
        start = q.get("from") or end - timedelta(days=364)
        return self.cached(
            request,
            start,
            end,
            lambda: selectors.heatmap(request.user.id, start, end, verified_only=q["verified_only"]),
        )


class HoursView(ReportView):
    def get(self, request):
        q = self.parse(serializers.ReportQuerySerializer, request.query_params).validated_data
        start, end = self.date_range(q, HOURS_DEFAULT_DAYS)
        return self.cached(request, start, end, lambda: selectors.hours(request.user.id, start, end))


class TimeVsCoverageView(ReportView):
    def get(self, request):
        q = self.parse(serializers.ReportQuerySerializer, request.query_params).validated_data
        if not q.get("subject_id"):
            raise ValidationError({"subject_id": ["Required."]})
        start, end = self.date_range(q, 90)

        def build():
            data = selectors.time_vs_coverage(
                request.user.id, q["subject_id"], start, end, verified_only=q["verified_only"]
            )
            if data is None:
                raise NotFound("Subject not found.")
            return data

        return self.cached(request, start, end, build, coverage.progress_stamp(request.user.id))


class WeeklySummaryView(ReportView):
    def get(self, request):
        q = self.parse(serializers.ReportQuerySerializer, request.query_params).validated_data
        first = q.get("week_start")
        anchor = first or self.today_cached - timedelta(days=7)
        return self.cached(
            request,
            anchor,
            anchor + timedelta(days=6),
            lambda: selectors.weekly_summary(request.user.id, self.today_cached, first),
            self.today_cached,
        )


class ReportExportView(TrackingView):
    throttle_classes = [UserRateThrottle, ScopedRateThrottle]
    throttle_scope = "tracking_export"

    def get(self, request):
        q = self.parse(serializers.ReportQuerySerializer, request.query_params).validated_data
        start, end = self.date_range(q, 30)
        by = q["by"] if q["by"] != "total" else "subject"
        data = selectors.breakdown(request.user.id, start, end, by=by, verified_only=q["verified_only"])
        rows = ([i["name"], round(i["seconds"] / 60, 1), i["share_percent"], i["sessions"]] for i in data["items"])
        return _csv_response("study-report.csv", [by, "minutes", "share_percent", "sessions"], rows)


class DataView(TrackingView):
    """GET exports everything tracking stores about the student; DELETE removes it. Not behind the flag."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(selectors.export_all(request.user.id))

    def delete(self, request):
        services.delete_all_for_user(request.user.id)
        return HttpResponse(status=204)
