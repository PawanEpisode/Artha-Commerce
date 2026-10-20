"""
API views for F-14 Amendments (ERD Section 3.2, PRD Section 7).
Strictly separates authenticated student workspace from public indexable endpoints.
Gated by PostHog feature flag 'amendments' for student views (403 feature_disabled).
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

from rest_framework import permissions, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core import feature_flags

from . import selectors, services
from .errors import ChangeNotFoundError
from .public_serializers import assert_no_leaks
from .serializers import (
    BulkReviewSerializer,
    ReportCardSerializer,
    ReviewCardSerializer,
    SaveCardSerializer,
)


class FeatureDisabled(PermissionDenied):
    default_code = "feature_disabled"
    default_detail = "Amendments feature is disabled."


def check_amendments_flag(user_id: uuid.UUID) -> None:
    """
    Ensures the student has the 'amendments' flag enabled.
    Fails closed when PostHog explicitly returns false.
    """
    if not feature_flags.flag_enabled("amendments", user_id):
        raise FeatureDisabled()


def make_anon_key(request) -> str:
    """
    Computes a daily salted hash of the client's IP and user agent for rate/abuse prevention.
    """
    ip = request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", ""))
    ua = request.META.get("HTTP_USER_AGENT", "")
    return hashlib.sha256(f"{ip}:{ua}".encode()).hexdigest()[:32]


# ---------------------------------------------------------------------------
# Student Workspace Views (Authenticated & Flag-Guarded)
# ---------------------------------------------------------------------------


class MySummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "amendments_read"

    def get(self, request):
        check_amendments_flag(request.user.id)
        viewer = selectors.get_viewer_context(request.user.id)
        if not viewer:
            return Response(
                {
                    "target_term": None,
                    "total_cards_count": 0,
                    "reviewed_count": 0,
                    "saved_count": 0,
                    "breakdown_by_paper": [],
                    "breakdown_by_type": {},
                }
            )
        data = selectors.my_summary(viewer)
        return Response(data)


class MyChangesView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "amendments_read"

    def get(self, request):
        check_amendments_flag(request.user.id)
        viewer = selectors.get_viewer_context(request.user.id)
        if not viewer:
            return Response({"cards": [], "total_count": 0, "has_more": False})

        flt: dict[str, Any] = {
            "applies": request.query_params.get("applies", "mine"),
            "subject": request.query_params.get("subject"),
            "type": request.query_params.get("type"),
            "state": request.query_params.get("state"),
            "term": request.query_params.get("term"),
            "q": request.query_params.get("q", ""),
        }
        cursor = request.query_params.get("cursor")
        limit = int(request.query_params.get("limit", 20))

        data = selectors.my_changes(viewer, flt, cursor=cursor, limit=limit)
        return Response(data)


class MyChangeDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "amendments_read"

    def get(self, request, public_id: str):
        check_amendments_flag(request.user.id)
        viewer = selectors.get_viewer_context(request.user.id)
        if not viewer:
            raise NotFound({"code": "not_found", "message": "Enrollment context not found."})

        card = selectors.my_change(viewer, public_id)
        if not card:
            raise NotFound({"code": "not_found", "message": f"Change card '{public_id}' not found in your scope."})

        return Response(card)


class CardReviewedView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "amendments_state"

    def post(self, request, public_id: str):
        check_amendments_flag(request.user.id)
        serializer = ReviewCardSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            services.set_card_state(
                user_id=request.user.id,
                public_id=public_id,
                reviewed=serializer.validated_data["reviewed"],
                client_id=serializer.validated_data.get("client_id"),
                client_ts=serializer.validated_data.get("client_ts"),
            )
        except ChangeNotFoundError:
            raise NotFound({"code": "not_found", "message": f"Card '{public_id}' not found."}) from None

        return Response({"status": "ok", "public_id": public_id, "reviewed": serializer.validated_data["reviewed"]})


class CardSavedView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "amendments_state"

    def post(self, request, public_id: str):
        check_amendments_flag(request.user.id)
        serializer = SaveCardSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            services.set_card_state(
                user_id=request.user.id,
                public_id=public_id,
                saved=serializer.validated_data["saved"],
                client_id=serializer.validated_data.get("client_id"),
                client_ts=serializer.validated_data.get("client_ts"),
            )
        except ChangeNotFoundError:
            raise NotFound({"code": "not_found", "message": f"Card '{public_id}' not found."}) from None

        return Response({"status": "ok", "public_id": public_id, "saved": serializer.validated_data["saved"]})


class BulkReviewedView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "amendments_bulk"

    def post(self, request):
        check_amendments_flag(request.user.id)
        serializer = BulkReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = services.bulk_set_reviewed(
            user_id=request.user.id,
            public_ids=serializer.validated_data["public_ids"],
            reviewed=serializer.validated_data["reviewed"],
            client_id=serializer.validated_data.get("client_id"),
        )
        return Response(result)


class CardReportView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "amendments_report"

    def post(self, request, public_id: str):
        serializer = ReportCardSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_id = request.user.id if request.user and request.user.is_authenticated else None
        anon_key = make_anon_key(request) if user_id is None else None

        try:
            result = services.file_report(
                user_id=user_id,
                anon_key=anon_key,
                public_id=public_id,
                kind=serializer.validated_data["kind"],
                message=serializer.validated_data["message"],
            )
        except ChangeNotFoundError:
            raise NotFound({"code": "not_found", "message": f"Card '{public_id}' not found."}) from None

        return Response(result, status=status.HTTP_201_CREATED)


class MyArchiveView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "amendments_read"

    def get(self, request):
        check_amendments_flag(request.user.id)
        viewer = selectors.get_viewer_context(request.user.id)
        if not viewer:
            return Response([])

        data = selectors.my_archive(viewer)
        return Response(data)


class ChapterAmendmentsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "amendments_read"

    def get(self, request, chapter_id: uuid.UUID):
        check_amendments_flag(request.user.id)
        viewer = selectors.get_viewer_context(request.user.id)
        cards = selectors.changes_for_chapters(viewer, [chapter_id])
        return Response(cards.get(str(chapter_id), []))


class UserDataDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request):
        # Always allowed even if amendments feature flag is off (DPDP erasure)
        result = services.delete_all_for_user(request.user.id)
        return Response(result)


class UserDataExportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Always allowed even if amendments feature flag is off (DPDP export)
        result = services.export_for_user(request.user.id)
        return Response(result)


# ---------------------------------------------------------------------------
# Public Indexable Views (Unauthenticated & Strict Allow-list)
# ---------------------------------------------------------------------------


class PublicHubView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "amendments_public"

    def get(self, request):
        docs = selectors.latest_documents()
        assert_no_leaks(docs)
        response = Response({"documents": docs})
        response["Cache-Control"] = "public, s-maxage=120"
        return response


class PublicLevelView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "amendments_public"

    def get(self, request, course_code: str, level_code: str):
        data = selectors.public_level(course_code, level_code)
        if not data:
            raise NotFound({"code": "not_found", "message": f"Level '{course_code}/{level_code}' not found."})

        assert_no_leaks(data)
        response = Response(data)
        response["Cache-Control"] = "public, s-maxage=120"
        return response


class PublicTermView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "amendments_public"

    def get(self, request, course_code: str, level_code: str, term_code: str):
        data = selectors.public_term(course_code, level_code, term_code)
        if not data:
            raise NotFound(
                {
                    "code": "not_found",
                    "message": f"Term '{term_code}' for '{course_code}/{level_code}' not found.",
                }
            )

        assert_no_leaks(data)
        response = Response(data)
        response["Cache-Control"] = "public, s-maxage=120"
        return response


class PublicPaperView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "amendments_public"

    def get(self, request, course_code: str, level_code: str, term_code: str, subject_key: str):
        change_type = request.query_params.get("type")
        data = selectors.public_paper(course_code, level_code, term_code, subject_key, change_type=change_type)
        if not data:
            raise NotFound(
                {
                    "code": "not_found",
                    "message": f"Paper '{subject_key}' for '{course_code}/{level_code}/{term_code}' not found.",
                }
            )

        assert_no_leaks(data)
        response = Response(data)
        response["Cache-Control"] = "public, s-maxage=120"
        return response


class PublicDocumentView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "amendments_public"

    def get(self, request, slug: str):
        data = selectors.public_document(slug)
        if not data:
            raise NotFound({"code": "not_found", "message": f"Document '{slug}' not found."})

        assert_no_leaks(data)
        response = Response(data)
        response["Cache-Control"] = "public, s-maxage=120"
        return response


class PublicCardView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "amendments_public"

    def get(self, request, public_id: str):
        data = selectors.public_change(public_id)
        if not data:
            raise NotFound({"code": "not_found", "message": f"Card '{public_id}' not found."})

        assert_no_leaks(data)
        response = Response(data)
        response["Cache-Control"] = "public, s-maxage=120"
        return response


class PublicSitemapView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "amendments_public"

    def get(self, request):
        paths = selectors.sitemap_paths()
        assert_no_leaks(paths)
        response = Response({"paths": paths})
        response["Cache-Control"] = "public, s-maxage=3600"
        return response
