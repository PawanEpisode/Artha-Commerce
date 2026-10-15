"""
API views for PYQ module (F-09 ERD 3.2, 7).
"""

from __future__ import annotations

import uuid

from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.feature_flags import flag_enabled

from .domain.importer import SchemaError
from .permissions import IsEditor
from .selectors import get_paper_detail, list_chapter_pyqs, list_papers
from .serializers import (
    ImportPaperSerializer,
    StartChapterPracticeSerializer,
    StartPaperPracticeSerializer,
    WithdrawPaperSerializer,
)
from .services import import_paper, publish_paper, start_chapter_session, start_paper_session, withdraw_paper


def _check_pyq_flags(request) -> None:
    user_id = request.user.id if getattr(request.user, "is_authenticated", False) else None
    if not flag_enabled("question_bank", user_id, strict=True):
        raise PermissionDenied("Feature disabled: question_bank")
    if not flag_enabled("pyq_bank", user_id, strict=True):
        raise PermissionDenied("Feature disabled: pyq_bank")


class PyqBaseView(APIView):
    throttle_classes = [ScopedRateThrottle]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        _check_pyq_flags(request)


# ---- Public / Student Endpoints -------------------------------------------------------------


class PapersListView(PyqBaseView):
    permission_classes = [AllowAny]
    throttle_scope = "qb_read"

    def get(self, request):
        course = request.query_params.get("course")
        level = request.query_params.get("level")
        subject = request.query_params.get("subject")
        term = request.query_params.get("term")

        user_id = request.user.id if getattr(request.user, "is_authenticated", False) else None
        papers = list_papers(
            course_code=course,
            level_code=level,
            subject_key=subject,
            term_code=term,
            user_id=user_id,
        )
        return Response({"items": papers})


class PaperDetailView(PyqBaseView):
    permission_classes = [AllowAny]
    throttle_scope = "qb_read"

    def get(self, request, pk):
        user_id = request.user.id if getattr(request.user, "is_authenticated", False) else None
        paper = get_paper_detail(pk, user_id=user_id)
        if not paper:
            raise Http404("Past paper not found.")
        return Response(paper)


class PaperPracticeStartView(PyqBaseView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "qb_write"

    def post(self, request, pk):
        serializer = StartPaperPracticeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            val_uuid = uuid.UUID(str(pk))
        except ValueError:
            raise Http404("Invalid paper id") from None

        try:
            result = start_paper_session(
                user_id=request.user.id,
                paper_id=val_uuid,
                mode=data["mode"],
                client_id=data.get("client_id"),
            )
        except ValueError as e:
            return Response(
                {"error": {"code": "invalid_operation", "message": str(e)}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(result, status=status.HTTP_201_CREATED)


class ChapterPyqsView(PyqBaseView):
    permission_classes = [AllowAny]
    throttle_scope = "qb_read"

    def get(self, request, chapter_id):
        try:
            val_uuid = uuid.UUID(str(chapter_id))
        except ValueError:
            raise Http404("Invalid chapter id") from None

        user_id = request.user.id if getattr(request.user, "is_authenticated", False) else None
        term_range = request.query_params.get("term_range")
        scheme_relation = request.query_params.get("scheme_relation")

        items = list_chapter_pyqs(
            val_uuid,
            user_id=user_id,
            term_range=term_range,
            scheme_relation=scheme_relation,
        )
        return Response({"items": items})


class ChapterPracticeStartView(PyqBaseView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "qb_write"

    def post(self, request, chapter_id):
        serializer = StartChapterPracticeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            val_uuid = uuid.UUID(str(chapter_id))
        except ValueError:
            raise Http404("Invalid chapter id") from None

        try:
            result = start_chapter_session(
                user_id=request.user.id,
                chapter_id=val_uuid,
                count=data["count"],
                client_id=data.get("client_id"),
            )
        except ValueError as e:
            return Response(
                {"error": {"code": "invalid_operation", "message": str(e)}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(result, status=status.HTTP_201_CREATED)


# ---- Editor Endpoints ------------------------------------------------------------------------


class EditorImportPaperView(PyqBaseView):
    permission_classes = [IsAuthenticated, IsEditor]
    throttle_scope = "qb_write"

    def post(self, request):
        serializer = ImportPaperSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            report = import_paper(
                editor_id=request.user.id,
                payload=data["payload"],
                dry_run=data["dry_run"],
            )
        except SchemaError as e:
            return Response(
                {"error": {"code": "schema_error", "message": str(e), "details": e.issues}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "paper_id": str(report.paper.id) if report.paper else None,
                "external_ref": report.paper.external_ref if report.paper else data["payload"].get("external_ref"),
                "created_questions": report.created_questions,
                "is_valid": report.is_valid,
            },
            status=status.HTTP_201_CREATED,
        )


class EditorPublishPaperView(PyqBaseView):
    permission_classes = [IsAuthenticated, IsEditor]
    throttle_scope = "qb_write"

    def post(self, request, pk):
        try:
            val_uuid = uuid.UUID(str(pk))
        except ValueError:
            raise Http404("Invalid paper id") from None

        try:
            paper = publish_paper(editor_id=request.user.id, paper_id=val_uuid)
        except ValueError as e:
            return Response(
                {"error": {"code": "publish_rejected", "message": str(e)}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "paper_id": str(paper.id),
                "status": paper.status,
                "published_at": paper.published_at.isoformat() if paper.published_at else None,
            }
        )


class EditorWithdrawPaperView(PyqBaseView):
    permission_classes = [IsAuthenticated, IsEditor]
    throttle_scope = "qb_write"

    def post(self, request, pk):
        serializer = WithdrawPaperSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            val_uuid = uuid.UUID(str(pk))
        except ValueError:
            raise Http404("Invalid paper id") from None

        paper = withdraw_paper(
            actor_id=request.user.id,
            paper_id=val_uuid,
            reason=data["reason"],
            replaced_by=data.get("replaced_by"),
        )
        return Response({"paper_id": str(paper.id), "status": paper.status})
