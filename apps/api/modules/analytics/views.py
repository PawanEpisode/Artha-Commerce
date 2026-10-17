"""
API views for Performance Analytics (F-10).
Scoped to requesting student, with ETag 304 handling and fail-closed flag guards.
"""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.http import HttpResponse
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from core.feature_flags import flag_enabled

from . import selectors, services
from .models import Goal, Report, Settings, Share
from .serializers import (
    BuildFixSetSerializer,
    CreateShareSerializer,
    GoalSerializer,
    RefreshSerializer,
    RequestReportSerializer,
    SettingsSerializer,
)


def _check_flag(request) -> None:
    """Gates analytics behind the performance_analytics flag."""
    if not flag_enabled("performance_analytics", request.user.id):
        raise PermissionDenied({"code": "feature_disabled", "detail": "Analytics feature is disabled."})


class OverviewView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _check_flag(request)
        user_id = request.user.id

        etag = selectors.get_data_stamp(user_id)
        if request.headers.get("If-None-Match") == etag:
            return HttpResponse(status=304)

        range_key = request.query_params.get("range", "30d")
        data = selectors.get_overview(user_id, range_key=range_key)

        response = Response(data)
        response["ETag"] = etag
        response["Cache-Control"] = "private, no-cache"
        return response


class PerformanceView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _check_flag(request)
        user_id = request.user.id

        etag = selectors.get_data_stamp(user_id)
        if request.headers.get("If-None-Match") == etag:
            return HttpResponse(status=304)

        subject_key = request.query_params.get("subject")
        range_key = request.query_params.get("range", "30d")
        group_by = request.query_params.get("by", "chapter")

        data = selectors.get_performance(
            user_id,
            subject_key=subject_key,
            range_key=range_key,
            group_by=group_by,
        )

        response = Response({
            "group_by": group_by,
            "range": range_key,
            "items": data,
        })
        response["ETag"] = etag
        response["Cache-Control"] = "private, no-cache"
        return response


class TrendsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _check_flag(request)
        user_id = request.user.id

        etag = selectors.get_data_stamp(user_id)
        if request.headers.get("If-None-Match") == etag:
            return HttpResponse(status=304)

        range_key = request.query_params.get("range") or request.query_params.get("window", "30d")
        interval = request.query_params.get("interval", "day")

        data = selectors.get_trends(user_id, range_key=range_key, interval=interval)

        response = Response({
            "window": range_key,
            "items": data,
        })
        response["ETag"] = etag
        response["Cache-Control"] = "private, no-cache"
        return response


class WeakTopicsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _check_flag(request)
        user_id = request.user.id
        subject_key = request.query_params.get("subject")
        try:
            limit = max(1, min(int(request.query_params.get("limit", 10)), 50))
        except (ValueError, TypeError):
            limit = 10

        items = selectors.get_weak_topics(user_id, subject_key=subject_key, limit=limit)
        return Response({"items": items})


class FixSetsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        _check_flag(request)
        serializer = BuildFixSetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        fix_session = services.build_fix_set(
            request.user.id,
            scope_type=data["scope_type"],
            scope_id=data["scope_id"],
            size=data["size"],
            client_id=data["client_id"],
            tz=data["tz"],
        )
        return Response(fix_session, status=status.HTTP_201_CREATED)


class SpeedView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _check_flag(request)
        user_id = request.user.id
        subject_key = request.query_params.get("subject")
        range_key = request.query_params.get("range", "30d")

        data = selectors.get_speed(user_id, subject_key=subject_key, range_key=range_key)
        return Response(data)


class MistakesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _check_flag(request)
        user_id = request.user.id
        subject_key = request.query_params.get("subject")
        range_key = request.query_params.get("range", "30d")

        items = selectors.get_mistakes(user_id, subject_key=subject_key, range_key=range_key)
        total_tagged = sum(it.get("count", 0) for it in items)
        return Response({
            "total_tagged_mistakes": total_tagged,
            "items": items,
        })


class ReadinessView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _check_flag(request)
        user_id = request.user.id
        subject_key = request.query_params.get("subject")

        res = selectors.get_readiness_data(user_id, subject_key=subject_key)

        # Save today's snapshot lazily
        today = timezone.localdate()
        try:
            services.save_snapshot(
                user_id,
                res,
                today=today,
                scope="subject" if subject_key else "overall",
                scope_key=subject_key or "",
            )
        except Exception:
            pass

        return Response({
            "state": res.state,
            "score": res.score,
            "half_width": res.half_width,
            "confidence": res.confidence,
            "label": res.label,
            "missing_gates": res.missing_gates,
            "components": [
                {
                    "key": c.key,
                    "label": c.label,
                    "value": c.value,
                    "weight": c.weight,
                    "points": c.points,
                    "available": c.available,
                }
                for c in res.components
            ],
            "levers": [
                {
                    "action": l.action,
                    "impact_points": l.impact_points,
                    "target_type": l.target_type,
                    "target_id": l.target_id,
                    "target_name": l.target_name,
                }
                for l in res.levers
            ],
        })


class RefreshView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        _check_flag(request)
        serializer = RefreshSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        limit = serializer.validated_data["limit"]

        count = services.refresh_pending(request.user.id, limit=limit)
        return Response({"refreshed_sessions": count})


class SettingsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _check_flag(request)
        sett, _ = Settings.objects.get_or_create(user_id=request.user.id)
        return Response(SettingsSerializer(sett).data)

    def patch(self, request):
        _check_flag(request)
        sett, _ = Settings.objects.get_or_create(user_id=request.user.id)
        serializer = SettingsSerializer(sett, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        sett.version += 1
        sett.save(update_fields=["version"])
        return Response(SettingsSerializer(sett).data)


class GoalsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _check_flag(request)
        goals = Goal.objects.filter(user_id=request.user.id).order_by("-effective_from")
        return Response({"items": GoalSerializer(goals, many=True).data})

    def post(self, request):
        _check_flag(request)
        serializer = GoalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        goal = serializer.save(user_id=request.user.id)
        return Response(GoalSerializer(goal).data, status=status.HTTP_201_CREATED)


class ReportsView(APIView):
    """R2 progress report generation and history."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        _check_flag(request)
        reports = Report.objects.filter(user_id=request.user.id, deleted_at__isnull=True).order_by("-requested_at")
        return Response({
            "items": [
                {
                    "id": str(r.id),
                    "status": r.status,
                    "period_kind": r.period_kind,
                    "from_date": r.from_date.isoformat(),
                    "to_date": r.to_date.isoformat(),
                    "created_at": r.requested_at.isoformat(),
                    "requested_at": r.requested_at.isoformat(),
                    "expires_at": r.expires_at.isoformat() if r.expires_at else "",
                }
                for r in reports
            ]
        })

    def post(self, request):
        _check_flag(request)
        serializer = RequestReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        v = serializer.validated_data

        today = timezone.localdate()
        from_date = v.get("from_date")
        to_date = v.get("to_date") or today

        if not from_date:
            pk = v["period_kind"]
            if pk == "7d":
                from_date = today - timedelta(days=6)
            elif pk == "90d":
                from_date = today - timedelta(days=89)
            elif pk == "all":
                from_date = date(2020, 1, 1)
            else:
                from_date = today - timedelta(days=29)

        client_id = v.get("client_id") or uuid.uuid4()
        existing = Report.objects.filter(user_id=request.user.id, client_id=client_id).first()
        if existing:
            return Response({"id": str(existing.id), "status": existing.status}, status=status.HTTP_200_OK)

        display_name = ""
        if v.get("include_name"):
            display_name = f"{request.user.first_name} {request.user.last_name}".strip()
            if not display_name:
                display_name = getattr(request.user, "email", "Student")

        pk_key = v["period_kind"] if v["period_kind"] in ("7d", "30d", "90d", "all") else "30d"
        overview_data = selectors.get_overview(request.user.id, pk_key)
        readiness_data = asdict(selectors.get_readiness_data(request.user.id))

        rep = Report.objects.create(
            user_id=request.user.id,
            client_id=client_id,
            status=Report.Status.READY,  # Instantly freeze for R1/R2 data representation
            period_kind=v["period_kind"],
            from_date=from_date,
            to_date=to_date,
            subject_keys=v.get("subject_keys", []),
            include_name=v.get("include_name", True),
            include_mistakes=v.get("include_mistakes", False),
            include_time=v.get("include_time", True),
            display_name=display_name,
            finished_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=7),
            data={
                "student_name": display_name if v.get("include_name") else None,
                "overview": overview_data,
                "readiness": readiness_data,
            },
        )
        return Response({"id": str(rep.id), "status": rep.status}, status=status.HTTP_201_CREATED)


class ShareCreateView(APIView):
    """R2 shareable report links."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        _check_flag(request)
        serializer = CreateShareSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        v = serializer.validated_data

        try:
            rep = Report.objects.get(id=v["report_id"], user_id=request.user.id)
        except Report.DoesNotExist:
            return Response({"detail": "Report not found."}, status=status.HTTP_404_NOT_FOUND)

        raw_token = uuid.uuid4().hex
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        expires_at = timezone.now() + timedelta(days=v.get("expires_in_days", 30))

        Share.objects.create(
            user_id=request.user.id,
            report=rep,
            token_hash=token_hash,
            scopes=v.get("scopes", []),
            consent_version=v.get("consent_version", "v1"),
            expires_at=expires_at,
        )

        return Response({
            "token": raw_token,
            "public_url": f"/app/analytics/share/{raw_token}",
            "scopes": v.get("scopes", []),
            "expires_at": expires_at.isoformat(),
        }, status=status.HTTP_201_CREATED)


class PublicShareDetailView(APIView):
    """R2 read-only view of a shared progress report."""
    permission_classes = [permissions.AllowAny]

    def get(self, request, token):
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        share = Share.objects.filter(token_hash=token_hash, revoked_at__isnull=True).select_related("report").first()

        if not share or share.expires_at < timezone.now() or not share.report:
            return Response({"detail": "Shared report not found or expired."}, status=status.HTTP_404_NOT_FOUND)

        share.view_count += 1
        share.last_viewed_at = timezone.now()
        if not share.first_viewed_at:
            share.first_viewed_at = timezone.now()
        share.save(update_fields=["view_count", "first_viewed_at", "last_viewed_at"])

        rep = share.report
        report_data = rep.data or {}
        overview_data = report_data.get("overview") or selectors.get_overview(rep.user_id, rep.period_kind if rep.period_kind in ("7d", "30d", "90d", "all") else "30d")
        readiness_data = report_data.get("readiness") or asdict(selectors.get_readiness_data(rep.user_id))
        student_name = rep.display_name if rep.include_name else None

        return Response({
            "student_name": student_name,
            "period_kind": rep.period_kind,
            "from_date": rep.from_date.isoformat(),
            "to_date": rep.to_date.isoformat(),
            "created_at": rep.requested_at.isoformat(),
            "data": report_data,
            "overview": overview_data,
            "readiness": readiness_data,
            "scopes": share.scopes,
        })
