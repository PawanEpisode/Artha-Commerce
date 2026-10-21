"""
API Views for F-08 Mock Tests and MTP.
"""

from __future__ import annotations

import uuid
from typing import Any

from rest_framework import permissions, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from . import errors, permissions as mock_perms, selectors, services
from .serializers import (
    AcquireLeaseSerializer,
    BuilderGenerateSerializer,
    BuilderPreviewSerializer,
    CloseSectionSerializer,
    HeartbeatSerializer,
    KeyStringParseSerializer,
    SaveAnswersBulkSerializer,
    SaveAnswerSingleSerializer,
    SettingsPatchSerializer,
    StartAttemptSerializer,
)


# ---------------------------------------------------------------------------
# Public Endpoints (SEO & Read-Only)
# ---------------------------------------------------------------------------


class PublicSeriesListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        level_id = request.query_params.get("level_id")
        uuid_level = uuid.UUID(level_id) if level_id else None
        data = selectors.list_series(level_id=uuid_level)
        return Response(data)


class PublicSeriesDetailView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, slug: str):
        data = selectors.get_series(slug)
        if not data:
            raise NotFound("Series not found.")
        return Response(data)


class PublicPaperDetailView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, public_id: str):
        data = selectors.get_paper(None, public_id)
        if not data or data["visibility"] != "public":
            raise NotFound("Paper not found.")
        return Response(data)


# ---------------------------------------------------------------------------
# Authenticated Papers Catalogue & Blueprint
# ---------------------------------------------------------------------------


class PaperListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        mock_perms.check_mock_flag(request.user.id)
        params = request.query_params
        flt = {
            "course": params.get("course"),
            "level": params.get("level"),
            "subject_key": params.get("subject_key"),
            "series_slug": params.get("series"),
            "source_tags": params.getlist("source") or None,
            "kinds": params.getlist("kind") or None,
            "key_status": params.get("key"),
            "scope": params.get("scope", "public"),
            "q": params.get("q"),
        }
        order = params.get("order", "newest")
        data = selectors.list_papers(request.user.id, flt, order=order)
        return Response(data)


class PaperDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, paper_id_or_public_id: str):
        mock_perms.check_mock_flag(request.user.id)
        version_no = request.query_params.get("version")
        v_num = int(version_no) if version_no and version_no.isdigit() else None
        data = selectors.get_paper(request.user.id, paper_id_or_public_id, version_no=v_num)
        if not data:
            raise NotFound("Paper not found.")
        return Response(data)


class PaperCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        mock_perms.check_mock_contrib_flag(request.user.id)
        paper = services.create_paper_draft(request.user.id, request.data)
        return Response({"id": str(paper.id), "public_id": paper.public_id}, status=status.HTTP_201_CREATED)


class PaperBlueprintView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def put(self, request, id: str):
        mock_perms.check_mock_contrib_flag(request.user.id)
        version_id = uuid.UUID(id)
        sections = request.data.get("sections", [])
        items = request.data.get("items", [])
        choice_groups = request.data.get("choice_groups", [])

        ok, problems = services.set_blueprint(
            actor_id=request.user.id,
            version_id=version_id,
            sections_data=sections,
            items_data=items,
            choice_groups_data=choice_groups,
        )
        return Response({"status": "ok", "problems": problems})


class PaperKeyStringParseView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = KeyStringParseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        results = keystring.parse_key_string(serializer.validated_data["text"])
        return Response({"parsed": results, "count": len(results)})


class PaperOverlayView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        ids = request.query_params.get("ids", "").split(",")
        uuids = []
        for i in ids:
            try:
                uuids.append(uuid.UUID(i.strip()))
            except ValueError:
                continue

        from .models import Attempt
        atts = Attempt.objects.filter(user_id=request.user.id, paper_id__in=uuids).order_by("-created_at")
        mapping = {}
        for a in atts:
            if str(a.paper_id) not in mapping:
                mapping[str(a.paper_id)] = {
                    "last_attempt_id": str(a.id),
                    "last_phase": a.phase,
                    "last_score": float(a.score) if a.score is not None else None,
                    "last_percent": float(a.percent) if a.percent is not None else None,
                }
        return Response(mapping)


# ---------------------------------------------------------------------------
# Test Builder
# ---------------------------------------------------------------------------


class BuilderPreviewView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        mock_perms.check_mock_contrib_flag(request.user.id)
        serializer = BuilderPreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = services.preview_blueprint_fill(request.user.id, serializer.validated_data)
        return Response(data)


class BuilderGenerateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        mock_perms.check_mock_contrib_flag(request.user.id)
        serializer = BuilderGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data
        result = services.generate_paper(
            user_id=request.user.id,
            spec=vd,
            start=vd.get("start", False),
            run_mode=vd.get("run_mode", "relaxed"),
        )
        return Response(result, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Attempts Lifecycle & Player
# ---------------------------------------------------------------------------


class AttemptListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        mock_perms.check_mock_flag(request.user.id)
        paper_id = request.query_params.get("paper_id")
        p_uuid = uuid.UUID(paper_id) if paper_id else None
        p_status = request.query_params.get("status")
        data = selectors.list_attempts(request.user.id, status=p_status, paper_id=p_uuid)
        return Response(data)

    def post(self, request):
        mock_perms.check_mock_flag(request.user.id)
        serializer = StartAttemptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data
        attempt = services.start_attempt(
            user_id=request.user.id,
            paper_id=vd["paper_id"],
            version_id=vd.get("version_id"),
            run_mode=vd["run_mode"],
            section_scope=vd.get("section_scope"),
            client_id=vd.get("client_id"),
            tz=vd["tz"],
        )
        return Response(
            {
                "id": str(attempt.id),
                "phase": attempt.phase,
                "session_id": str(attempt.session_id),
                "run_mode": attempt.run_mode,
            },
            status=status.HTTP_201_CREATED,
        )


class AttemptStateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, id: str):
        mock_perms.check_mock_flag(request.user.id)
        att_uuid = uuid.UUID(id)
        data = selectors.attempt_state(request.user.id, att_uuid)
        if not data:
            raise NotFound("Attempt not found.")
        return Response(data)


class AttemptBundleView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, id: str):
        mock_perms.check_mock_flag(request.user.id)
        att_uuid = uuid.UUID(id)
        from .models import Attempt
        attempt = Attempt.objects.filter(id=att_uuid, user_id=request.user.id).select_related("paper_version").first()
        if not attempt:
            raise NotFound("Attempt not found.")

        # Bundle includes playable items without answers/keys
        from modules.questionbank.selectors import get_playables
        q_ids = [uuid.UUID(it["item_id"]) for it in attempt.layout if it.get("item_id")]
        # Fetch question IDs of paper items
        it_objs = Item.objects.filter(version=attempt.paper_version).values_list("question_id", flat=True)
        playables = get_playables(list(it_objs))

        return Response({
            "attempt_id": str(attempt.id),
            "layout": attempt.layout,
            "playables": playables,
        })


class AttemptClockView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, id: str):
        att_uuid = uuid.UUID(id)
        data = selectors.attempt_state(request.user.id, att_uuid)
        if not data:
            raise NotFound("Attempt not found.")
        return Response({
            "server_time": data["server_time"],
            "phase": data["phase"],
            "remaining_ms": data["remaining_ms"],
            "section_remaining_ms": data["section_remaining_ms"],
            "active_section_key": data["active_section_key"],
        })


class AttemptAcceptInstructionsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id: str):
        mock_perms.check_mock_flag(request.user.id)
        att_uuid = uuid.UUID(id)
        attempt = services.accept_instructions(request.user.id, att_uuid)
        return Response({"phase": attempt.phase})


class AttemptStartWritingView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id: str):
        mock_perms.check_mock_flag(request.user.id)
        att_uuid = uuid.UUID(id)
        attempt = services.start_writing(request.user.id, att_uuid)
        return Response({"phase": attempt.phase})


class AttemptLeaseView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id: str):
        mock_perms.check_mock_flag(request.user.id)
        serializer = AcquireLeaseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data
        result = services.acquire_lease(
            user_id=request.user.id,
            attempt_id=uuid.UUID(id),
            tab_id=vd["tab_id"],
            label=vd["label"],
            takeover=vd["takeover"],
        )
        return Response(result)


class AttemptHeartbeatView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id: str):
        serializer = HeartbeatSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data
        res = services.heartbeat(
            user_id=request.user.id,
            attempt_id=uuid.UUID(id),
            epoch=vd["epoch"],
            position=vd.get("position"),
            section=vd.get("section"),
            events_data=vd.get("events"),
        )
        return Response(res)


class AttemptAnswersBulkView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def put(self, request, id: str):
        serializer = SaveAnswersBulkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data
        results = services.save_answers(
            user_id=request.user.id,
            attempt_id=uuid.UUID(id),
            epoch=vd["epoch"],
            items=vd["items"],
        )
        return Response({"results": results})


class AttemptAnswerSingleView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def put(self, request, id: str, position: int):
        serializer = SaveAnswerSingleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data
        results = services.save_answers(
            user_id=request.user.id,
            attempt_id=uuid.UUID(id),
            epoch=vd["epoch"],
            items=[{"position": position, "answer": vd.get("answer"), "flags": vd.get("flags")}],
        )
        return Response(results[0] if results else {"status": "saved"})


class AttemptCloseSectionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id: str, key: str):
        serializer = CloseSectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        res = services.close_section(
            user_id=request.user.id,
            attempt_id=uuid.UUID(id),
            section_key=key,
            epoch=serializer.validated_data["epoch"],
        )
        return Response(res)


class AttemptPauseView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id: str):
        # Relaxed attempts only
        return Response({"status": "paused"})


class AttemptResumeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id: str):
        return Response({"status": "resumed"})


class AttemptSubmitView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id: str):
        mock_perms.check_mock_flag(request.user.id)
        att_uuid = uuid.UUID(id)
        epoch = request.data.get("epoch")
        attempt = services.submit_attempt(request.user.id, att_uuid, epoch=epoch)
        return Response({
            "id": str(attempt.id),
            "phase": attempt.phase,
            "score": float(attempt.score) if attempt.score is not None else None,
            "max_score": float(attempt.max_score) if attempt.max_score is not None else None,
            "percent": float(attempt.percent) if attempt.percent is not None else None,
            "score_status": attempt.score_status,
        })


class AttemptResultView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, id: str):
        mock_perms.check_mock_flag(request.user.id)
        att_uuid = uuid.UUID(id)
        data = selectors.result(request.user.id, att_uuid)
        if not data:
            raise NotFound("Result not found.")
        return Response(data)


class AttemptReviewView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, id: str):
        mock_perms.check_mock_flag(request.user.id)
        att_uuid = uuid.UUID(id)
        flt = request.query_params.get("filter")
        data = selectors.review(request.user.id, att_uuid, filter_by=flt)
        if not data:
            raise NotFound("Review not available.")
        return Response(data)


class AttemptEventsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id: str):
        events = request.data.get("events", [])
        return Response({"saved": len(events)})


class AttemptRetakeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id: str):
        mock_perms.check_mock_flag(request.user.id)
        att_uuid = uuid.UUID(id)
        from .models import Attempt
        prev_att = Attempt.objects.get(id=att_uuid, user_id=request.user.id)
        new_att = services.start_attempt(
            user_id=request.user.id,
            paper_id=prev_att.paper_id,
            run_mode=request.data.get("run_mode", prev_att.run_mode),
        )
        return Response({"id": str(new_att.id)}, status=status.HTTP_201_CREATED)


class AttemptPagesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id: str):
        # Attach photo pages during upload window
        return Response({"status": "attached"})


class AttemptPercentileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, id: str):
        mock_perms.check_mock_flag(request.user.id)
        att_uuid = uuid.UUID(id)
        data = selectors.percentile_for(request.user.id, att_uuid)
        return Response(data)


class AttemptCompareView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        mock_perms.check_mock_flag(request.user.id)
        paper_id = request.query_params.get("paper_id")
        p_uuid = uuid.UUID(paper_id) if paper_id else None
        data = selectors.compare_attempts(request.user.id, paper_id=p_uuid)
        return Response(data)


# ---------------------------------------------------------------------------
# Settings & Reference Data
# ---------------------------------------------------------------------------


class SettingsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        settings_obj = services.get_or_create_settings(request.user.id)
        return Response({
            "time_extension_pct": settings_obj.time_extension_pct,
            "default_run_mode": settings_obj.default_run_mode,
            "focus_reminders": settings_obj.focus_reminders,
            "keyboard_shortcuts": settings_obj.keyboard_shortcuts,
            "percentile_optin": settings_obj.percentile_optin,
            "tz": settings_obj.tz,
        })

    def put(self, request):
        serializer = SettingsPatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = services.set_settings(request.user.id, serializer.validated_data)
        return Response({
            "time_extension_pct": updated.time_extension_pct,
            "default_run_mode": updated.default_run_mode,
            "focus_reminders": updated.focus_reminders,
            "keyboard_shortcuts": updated.keyboard_shortcuts,
            "percentile_optin": updated.percentile_optin,
            "tz": updated.tz,
        })


class SeriesListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        data = selectors.list_series()
        return Response(data)


class SeriesDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, slug: str):
        data = selectors.get_series(slug)
        if not data:
            raise NotFound("Series not found.")
        return Response(data)


class ExamFormatListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        data = selectors.list_formats()
        return Response(data)


# ---------------------------------------------------------------------------
# Admin Endpoints (Editors Only)
# ---------------------------------------------------------------------------


class AdminPaperPublishView(APIView):
    permission_classes = [mock_perms.IsMockEditor]

    def post(self, request, id: str):
        version_id = uuid.UUID(id)
        visibility = request.data.get("visibility", Paper.Visibility.PUBLIC)
        version = services.publish_version(request.user.id, version_id, visibility=visibility)
        return Response({"status": "published", "version_no": version.version_no})


class AdminPaperReviseView(APIView):
    permission_classes = [mock_perms.IsMockEditor]

    def post(self, request, id: str):
        paper_id = uuid.UUID(id)
        paper = Paper.objects.get(id=paper_id)
        latest_v = paper.versions.order_by("-version_no").first()
        new_v = PaperVersion.objects.create(
            paper=paper,
            version_no=(latest_v.version_no + 1) if latest_v else 2,
            state=PaperVersion.State.DRAFT,
            total_marks=latest_v.total_marks if latest_v else Decimal("100.00"),
            duration_seconds=latest_v.duration_seconds if latest_v else 10800,
            created_by=request.user.id,
        )
        return Response({"new_version_id": str(new_v.id), "version_no": new_v.version_no}, status=status.HTTP_201_CREATED)


class AdminPaperKeyReleaseView(APIView):
    permission_classes = [mock_perms.IsMockEditor]

    def post(self, request, id: str):
        paper_id = uuid.UUID(id)
        res = services.release_key(request.user.id, paper_id)
        return Response(res)
