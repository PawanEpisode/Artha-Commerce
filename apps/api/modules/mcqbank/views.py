"""
API views for MCQ Bank (F-05 ERD 3.2, 5, 7).
Strict feature flag enforcement: fail-closed under 'question_bank' and 'mcq_bank'.
"""

from __future__ import annotations

import datetime
import uuid

from django.http import Http404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.feature_flags import flag_enabled
from modules.practice import services as practice_services

from .models import McqSet
from .permissions import IsEditor
from .selectors import (
    chapter_detail,
    chapter_tiles,
    enrolled_course_level,
    external_log,
    get_set,
    home,
    list_presets,
    list_sets,
    preview_blueprint,
    reference_sources,
    resolve_pattern,
    suggest_quick_set,
)
from .serializers import (
    AdaptiveStartSerializer,
    BlueprintPreviewSerializer,
    ExternalLogCreateSerializer,
    SavePresetSerializer,
    StartQuickPracticeSerializer,
    WithdrawSetSerializer,
)
from .services import (
    delete_external_log,
    delete_preset,
    log_external_result,
    next_round,
    publish_set,
    record_click,
    save_preset,
    start_adaptive,
    stop_adaptive,
    use_preset,
    verify_pattern,
    withdraw_set,
)


def _check_mcq_flags(request) -> None:
    user_id = request.user.id if getattr(request.user, "is_authenticated", False) else None
    if not flag_enabled("question_bank", user_id, strict=True):
        raise PermissionDenied("Feature disabled: question_bank")
    if not flag_enabled("mcq_bank", user_id, strict=True):
        raise PermissionDenied("Feature disabled: mcq_bank")


def _check_adaptive_flags(request) -> None:
    _check_mcq_flags(request)
    user_id = request.user.id if getattr(request.user, "is_authenticated", False) else None
    if not flag_enabled("mcq_adaptive", user_id, strict=True):
        raise PermissionDenied("Feature disabled: mcq_adaptive")


class McqBaseView(APIView):
    throttle_classes = [ScopedRateThrottle]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        _check_mcq_flags(request)


# --- Student Endpoints ------------------------------------------------------------------------


def _course_level(request) -> tuple[str, str]:
    """`?course=&level=` when given, otherwise what the student is enrolled in (a Final student must not get Intermediate)."""
    enrolled_course, enrolled_level = enrolled_course_level(request.user.id)
    return (
        request.query_params.get("course") or enrolled_course,
        request.query_params.get("level") or enrolled_level,
    )


class McqHomeView(McqBaseView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "qb_read"

    def get(self, request):
        data = home(request.user.id)
        return Response(data)


class SubjectTilesView(McqBaseView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "qb_read"

    def get(self, request, subject_key: str):
        course, level = _course_level(request)
        tiles = chapter_tiles(request.user.id, subject_key, course=course, level=level)
        return Response(tiles)


class ChapterDetailView(McqBaseView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "qb_read"

    def get(self, request, subject_key: str, chapter_key: str):
        course, level = _course_level(request)
        data = chapter_detail(request.user.id, subject_key, chapter_key, course=course, level=level)
        return Response(data)


class QuickStartView(McqBaseView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "qb_write"

    def post(self, request):
        ser = StartQuickPracticeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        cd = ser.validated_data

        chapter_id = cd.get("chapter_id")
        subject_key = cd.get("subject_key")
        count = cd["count"]
        mode = cd["mode"]
        client_id = cd["client_id"]

        if chapter_id:
            spec = {
                "v": 1,
                "chapters": [{"chapter_id": str(chapter_id), "n": count}],
                "count": count,
                "mix": "smart",
            }
            picker = "mcq_blueprint"
        elif subject_key:
            spec = {
                "v": 1,
                "subject_key": subject_key,
                "count": count,
                "mix": "smart",
            }
            picker = "mcq_blueprint"
        else:
            sugg = suggest_quick_set(request.user.id, count=count)
            if not sugg:
                raise ValidationError("No questions available for quick practice.")
            spec = sugg["spec"]
            picker = "mcq_blueprint"

        session = practice_services.create_session(
            user_id=request.user.id,
            mode=mode,
            picker=picker,
            spec=spec,
            origin_module="mcq_bank",
            origin_ref="quick_start",
            client_id=client_id,
        )
        return Response({"session_id": str(session.id)}, status=status.HTTP_201_CREATED)


class SetsListView(McqBaseView):
    permission_classes = [AllowAny]
    throttle_scope = "qb_read"

    def get(self, request):
        subject_key = request.query_params.get("subject_key")
        chapter_key = request.query_params.get("chapter_key")
        kind = request.query_params.get("kind")
        term_code = request.query_params.get("term_code")
        delivery = request.query_params.get("delivery")
        user_id = request.user.id if getattr(request.user, "is_authenticated", False) else None

        data = list_sets(
            viewer_id=user_id,
            subject_key=subject_key,
            chapter_key=chapter_key,
            kind=kind,
            term_code=term_code,
            delivery=delivery,
        )
        return Response(data)


class SetDetailView(McqBaseView):
    permission_classes = [AllowAny]
    throttle_scope = "qb_read"

    def get(self, request, slug: str):
        user_id = request.user.id if getattr(request.user, "is_authenticated", False) else None
        try:
            data = get_set(user_id, slug)
        except McqSet.DoesNotExist:
            raise Http404("Set not found") from None
        return Response(data)


class SetPracticeStartView(McqBaseView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "qb_write"

    def post(self, request, slug: str):
        try:
            mcq_set = McqSet.objects.get(slug=slug, status=McqSet.Status.PUBLISHED)
        except McqSet.DoesNotExist:
            raise Http404("Set not found") from None

        if mcq_set.delivery != McqSet.Delivery.HOSTED:
            raise ValidationError("Cannot launch hosted practice on a link-out set.")

        spec = {
            "v": 1,
            "set_id": str(mcq_set.id),
            "order": "set",
        }
        client_id = uuid.uuid4()
        session = practice_services.create_session(
            user_id=request.user.id,
            mode="chapter_quiz",
            picker="mcq_set",
            spec=spec,
            origin_module="mcq_bank",
            origin_ref=f"set:{mcq_set.id}",
            client_id=client_id,
        )
        return Response({"session_id": str(session.id)}, status=status.HTTP_201_CREATED)


class SetClickView(McqBaseView):
    permission_classes = [AllowAny]
    throttle_scope = "qb_read"

    def post(self, request, slug: str):
        try:
            mcq_set = McqSet.objects.get(slug=slug, status=McqSet.Status.PUBLISHED)
        except McqSet.DoesNotExist:
            raise Http404("Set not found") from None

        user_id = request.user.id if getattr(request.user, "is_authenticated", False) else uuid.uuid4()
        record_click(user_id, mcq_set.id)
        return Response({"status": "recorded"})


class ExternalLogListView(McqBaseView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "qb_write"

    def get(self, request):
        logs = external_log(request.user.id)
        return Response(logs)

    def post(self, request):
        ser = ExternalLogCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        cd = ser.validated_data

        log = log_external_result(
            user_id=request.user.id,
            set_id=cd["set_id"],
            score=cd["score"],
            max_score=cd["max_score"],
            taken_on=cd["taken_on"],
            client_id=cd["client_id"],
        )
        return Response({"id": str(log.id), "score_pct": float(log.score_pct)}, status=status.HTTP_201_CREATED)


class ExternalLogDetailView(McqBaseView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "qb_write"

    def delete(self, request, log_id: uuid.UUID):
        delete_external_log(request.user.id, log_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PresetsListView(McqBaseView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "qb_write"

    def get(self, request):
        presets = list_presets(request.user.id)
        return Response(presets)

    def post(self, request):
        ser = SavePresetSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        cd = ser.validated_data

        preset = save_preset(
            user_id=request.user.id,
            name=cd["name"],
            kind=cd["kind"],
            mode=cd["mode"],
            picker=cd["picker"],
            spec=cd["spec"],
            time_limit_seconds=cd.get("time_limit_seconds"),
            scoring_profile=cd.get("scoring_profile", "practice"),
            pattern_id=cd.get("pattern_id"),
            client_id=cd.get("client_id"),
        )
        return Response({"id": str(preset.id), "name": preset.name}, status=status.HTTP_201_CREATED)


class PresetUseView(McqBaseView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "qb_write"

    def post(self, request, preset_id: uuid.UUID):
        session_args = use_preset(request.user.id, preset_id)
        session = practice_services.create_session(
            user_id=request.user.id,
            mode=session_args["mode"],
            picker=session_args["picker"],
            spec=session_args["spec"],
            time_limit_seconds=session_args.get("time_limit_seconds"),
            scoring_profile=session_args.get("scoring_profile", "practice"),
            origin_module=session_args["origin_module"],
            origin_ref=session_args["origin_ref"],
            client_id=uuid.uuid4(),
        )
        return Response({"session_id": str(session.id)}, status=status.HTTP_201_CREATED)


class PresetDetailView(McqBaseView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "qb_write"

    def delete(self, request, preset_id: uuid.UUID):
        delete_preset(request.user.id, preset_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PatternResolveView(McqBaseView):
    permission_classes = [AllowAny]
    throttle_scope = "qb_read"

    def get(self, request):
        course = request.query_params.get("course", "cma")
        level = request.query_params.get("level", "intermediate")
        subject = request.query_params.get("subject", "")
        on_str = request.query_params.get("date")

        target_date = datetime.date.fromisoformat(on_str) if on_str else timezone.now().date()
        p = resolve_pattern(course, level, subject, target_date)
        if not p:
            return Response(None)
        return Response(
            {
                "id": str(p.id),
                "mcq_count": p.mcq_count,
                "mcq_total_marks": str(p.mcq_total_marks),
                "marks_per_mcq": str(p.marks_per_mcq) if p.marks_per_mcq else None,
                "minutes": p.minutes,
                "format": p.format,
                "verified": p.verified,
            }
        )


class BlueprintPreviewView(McqBaseView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "qb_read"

    def post(self, request):
        ser = BlueprintPreviewSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        preview = preview_blueprint(request.user.id, ser.validated_data["spec"])
        return Response(preview)


class ReferenceSourcesView(McqBaseView):
    permission_classes = [AllowAny]
    throttle_scope = "qb_read"

    def get(self, request):
        refs = reference_sources()
        return Response(refs)


# --- Adaptive Endpoints (R3) ------------------------------------------------------------------


class AdaptiveStartView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "qb_write"
    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        _check_adaptive_flags(request)

    def post(self, request):
        ser = AdaptiveStartSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        cd = ser.validated_data

        run = start_adaptive(
            user_id=request.user.id,
            scope_type=cd["scope_type"],
            scope_id=cd["scope_id"],
            subject_key=cd["subject_key"],
            chapter_key=cd.get("chapter_key", ""),
            client_id=cd["client_id"],
        )
        return Response(
            {"run_id": str(run.id), "status": run.status, "rounds_started": run.rounds_started},
            status=status.HTTP_201_CREATED,
        )


class AdaptiveNextRoundView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "qb_write"
    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        _check_adaptive_flags(request)

    def post(self, request, run_id: uuid.UUID):
        round_no = int(request.data.get("round_no", 1))
        data = next_round(request.user.id, run_id, round_no=round_no)
        return Response(data, status=status.HTTP_201_CREATED)


class AdaptiveStopView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "qb_write"
    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        _check_adaptive_flags(request)

    def post(self, request, run_id: uuid.UUID):
        stop_adaptive(request.user.id, run_id)
        return Response({"status": "stopped"})


# --- Staff / Editor Endpoints -----------------------------------------------------------------


class SetPublishView(McqBaseView):
    permission_classes = [IsEditor]
    throttle_scope = "qb_write"

    def post(self, request, set_id: uuid.UUID):
        mcq_set = publish_set(request.user.id, set_id)
        return Response({"id": str(mcq_set.id), "status": mcq_set.status})


class SetWithdrawView(McqBaseView):
    permission_classes = [IsEditor]
    throttle_scope = "qb_write"

    def post(self, request, set_id: uuid.UUID):
        ser = WithdrawSetSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        withdraw_set(request.user.id, set_id, reason=ser.validated_data["reason"])
        return Response({"status": "withdrawn"})


class PatternVerifyView(McqBaseView):
    permission_classes = [IsEditor]
    throttle_scope = "qb_write"

    def post(self, request, pattern_id: uuid.UUID):
        pattern = verify_pattern(request.user.id, pattern_id)
        return Response({"id": str(pattern.id), "verified": pattern.verified, "status": pattern.status})
