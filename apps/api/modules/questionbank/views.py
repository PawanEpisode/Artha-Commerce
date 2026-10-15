"""
API views for Question Bank (F-06 ERD 3.2, 5, 6.4, 7).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import uuid

from django.http import Http404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.feature_flags import flag_enabled

from .domain.filters import parse_filter_params
from .permissions import IsEditor
from .selectors import (
    can_view,
    facets,
    get_playable,
    get_review_view,
    list_published,
)
from .serializers import (
    CreateDraftSerializer,
    DecideReviewSerializer,
    MergeDuplicateSerializer,
    PublishVersionSerializer,
    ReportErrorSerializer,
    SaveLiveSerializer,
    VerifySerializer,
)
from .services import (
    ChecksFailed,
    create_draft,
    decide_review,
    merge_duplicate,
    publish_version,
    report_error,
    save_live,
    submit_for_review,
    verify,
)


def _check_qb_flag(request) -> None:
    user_id = request.user.id if getattr(request.user, "is_authenticated", False) else None
    if not flag_enabled("question_bank", user_id, strict=True):
        raise Http404("Question bank feature is not enabled.")


class QuestionBankBaseView(APIView):
    throttle_classes = [ScopedRateThrottle]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        _check_qb_flag(request)


# ---- Public Endpoints ------------------------------------------------------------------------


class PublicQuestionsView(QuestionBankBaseView):
    permission_classes = [AllowAny]
    throttle_scope = "qb_read"

    def get(self, request):
        flt = parse_filter_params(request.query_params.dict())
        order = request.query_params.get("order", "newest")
        cursor = request.query_params.get("cursor")
        limit = min(int(request.query_params.get("limit", 20)), 100)

        page = list_published(None, flt, order=order, cursor=cursor, limit=limit)
        items_data = [dataclasses.asdict(card) for card in page.items]

        data = {
            "items": items_data,
            "next_cursor": page.next_cursor,
        }
        res = Response(data)
        res["Cache-Control"] = "public, s-maxage=300, stale-while-revalidate=3600"
        etag_seed = hashlib.md5(json.dumps([c["id"] for c in items_data], default=str).encode()).hexdigest()
        res["ETag"] = f'W/"{etag_seed}"'
        return res


class PublicQuestionDetailView(QuestionBankBaseView):
    permission_classes = [AllowAny]
    throttle_scope = "qb_read"

    def get(self, request, pk):
        try:
            playable = get_playable(pk)
        except Exception:
            raise Http404("Question not found.") from None

        if not can_view(None, pk):
            raise Http404("Question not found.")

        data = dataclasses.asdict(playable)
        res = Response(data)
        res["Cache-Control"] = "public, s-maxage=300, stale-while-revalidate=3600"
        return res


class PublicFacetsView(QuestionBankBaseView):
    permission_classes = [AllowAny]
    throttle_scope = "qb_read"

    def get(self, request):
        flt = parse_filter_params(request.query_params.dict())
        dims = request.query_params.get("dims", "kind,difficulty,source_year").split(",")
        dims = [d.strip() for d in dims if d.strip()]

        facet_data = facets(None, flt, dims)
        res_data = {dim: [dataclasses.asdict(fc) for fc in counts] for dim, counts in facet_data.items()}

        res = Response(res_data)
        res["Cache-Control"] = "public, s-maxage=300, stale-while-revalidate=3600"
        return res


# ---- Authenticated Question Endpoints --------------------------------------------------------


class QuestionPlayableView(QuestionBankBaseView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "qb_read"

    def get(self, request, pk):
        token = request.query_params.get("token")
        if not can_view(request.user.id, pk, token=token):
            raise Http404("Question not found.")

        version_id = request.query_params.get("version_id")
        v_uuid = uuid.UUID(version_id) if version_id else None

        try:
            playable = get_playable(pk, version_id=v_uuid)
        except Exception:
            raise Http404("Question not found.") from None

        return Response(dataclasses.asdict(playable))


class QuestionReviewView(QuestionBankBaseView):
    permission_classes = [IsAuthenticated]

    @property
    def throttle_scope(self) -> str:
        if getattr(self, "request", None) and self.request.method.upper() == "POST":
            return "qb_write"
        return "qb_read"

    def get(self, request, pk):
        token = request.query_params.get("token")
        if not can_view(request.user.id, pk, token=token):
            raise Http404("Question not found.")

        version_id = request.query_params.get("version_id")
        if not version_id:
            playable = get_playable(pk)
            version_id = str(playable.version_id)

        try:
            rev_view = get_review_view(pk, uuid.UUID(version_id))
        except Exception:
            raise Http404("Question review not found.") from None

        return Response(dataclasses.asdict(rev_view))

    def post(self, request, pk):
        try:
            review = submit_for_review(request.user.id, pk)
        except PermissionError:
            raise Http404("Question not found.") from None
        except ChecksFailed as e:
            return Response(
                {"error": {"code": "checks_failed", "message": str(e), "details": e.checks}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({"review_id": review.id, "status": review.status})


class CreateDraftView(QuestionBankBaseView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "qb_write"

    def post(self, request):
        serializer = CreateDraftSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        client_id = data.pop("client_id", None)
        try:
            question = create_draft(request.user.id, data, client_id=client_id)
        except ChecksFailed as e:
            return Response(
                {"error": {"code": "validation_failed", "message": str(e), "details": e.checks}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "question_id": question.id,
                "public_id": question.public_id,
                "kind": question.kind,
                "status": question.status,
                "visibility": question.visibility,
            },
            status=status.HTTP_201_CREATED,
        )


class SaveLiveView(QuestionBankBaseView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "qb_write"

    def put(self, request, pk):
        serializer = SaveLiveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            version = save_live(request.user.id, pk, serializer.validated_data["visibility"])
        except PermissionError:
            raise Http404("Question not found.") from None
        except ValueError as e:
            return Response(
                {"error": {"code": "invalid_operation", "message": str(e)}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({"version_id": version.id, "state": version.state})


class ReportErrorView(QuestionBankBaseView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "qb_report"

    def post(self, request, pk):
        serializer = ReportErrorSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        report = report_error(
            user_id=request.user.id,
            question_id=pk,
            version_id=data["version_id"],
            kind=data["kind"],
            message=data["message"],
            proposed_option_ids=data["proposed_option_ids"],
        )
        return Response({"report_id": report.id, "status": report.status})


# ---- Editor / Admin Endpoints ----------------------------------------------------------------


class DecideReviewView(QuestionBankBaseView):
    permission_classes = [IsAuthenticated, IsEditor]
    throttle_scope = "qb_write"

    def post(self, request, pk):
        serializer = DecideReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        review = decide_review(
            editor_id=request.user.id,
            review_id=pk,
            decision=data["decision"],
            code=data["code"],
            note=data["note"],
            field_comments=data["field_comments"],
        )
        return Response({"review_id": review.id, "status": review.status})


class PublishVersionView(QuestionBankBaseView):
    permission_classes = [IsAuthenticated, IsEditor]
    throttle_scope = "qb_write"

    def post(self, request, pk):
        serializer = PublishVersionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        version = publish_version(
            editor_id=request.user.id,
            version_id=pk,
            visibility=serializer.validated_data["visibility"],
        )
        return Response({"version_id": version.id, "state": version.state})


class VerifyView(QuestionBankBaseView):
    permission_classes = [IsAuthenticated, IsEditor]
    throttle_scope = "qb_write"

    def post(self, request):
        serializer = VerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        ver = verify(
            editor_id=request.user.id,
            version_id=data["version_id"],
            level=data["level"],
            source_label=data["source_label"],
            source_url=data["source_url"],
        )
        return Response({"verification_id": ver.id, "level": ver.level})


class MergeDuplicateView(QuestionBankBaseView):
    permission_classes = [IsAuthenticated, IsEditor]
    throttle_scope = "qb_write"

    def post(self, request):
        serializer = MergeDuplicateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        merge_duplicate(
            editor_id=request.user.id,
            loser_id=data["loser_id"],
            canonical_id=data["canonical_id"],
        )
        return Response({"status": "merged"})
