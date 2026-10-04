from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers as drf_serializers
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.authentication import SupabaseJWTAuthentication

from . import selectors, services
from .permissions import IsSyllabusEditor
from .serializers import (
    ChapterDetailSerializer,
    CourseSerializer,
    ExamTermSerializer,
    GroupSerializer,
    LevelSerializer,
    ReportCreateSerializer,
    SchemeSerializer,
    SubjectDetailSerializer,
    SubjectSerializer,
)

PUBLIC_CACHE = "public, s-maxage=300, stale-while-revalidate=3600"


class PublicView(APIView):
    """Unauthenticated, CDN-cacheable reads. A stray bearer token is ignored rather than rejected."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        if request.method == "GET" and response.status_code == 200:
            response["Cache-Control"] = PUBLIC_CACHE
        return response


class CourseListView(PublicView):
    def get(self, request):
        return Response(CourseSerializer(selectors.list_courses(), many=True).data)


class LevelDetailView(PublicView):
    """The level with its current published scheme, groups and subjects. `scheme` is null while the level is not curated."""

    def get(self, request, course, level):
        level_obj = selectors.get_level(course, level)
        if not level_obj:
            raise NotFound("Level not found.")
        scheme = selectors.get_current_scheme(level_obj)
        schemes = selectors.list_published_schemes(level_obj)
        body = {
            **LevelSerializer(level_obj).data,
            "course": {
                "code": level_obj.course.code,
                "name": level_obj.course.name,
                "institute_name": level_obj.course.institute_name,
                "institute_url": level_obj.course.institute_url,
            },
            "scheme": SchemeSerializer(scheme).data if scheme else None,
            "schemes": SchemeSerializer(schemes, many=True).data,
            "groups": GroupSerializer(selectors.list_groups(scheme), many=True).data if scheme else [],
            "subjects": SubjectSerializer(selectors.list_subjects(scheme), many=True).data if scheme else [],
        }
        return Response(body)


class SubjectDetailView(PublicView):
    def get(self, request, subject_id):
        subject = selectors.get_published_subject(subject_id)
        if not subject:
            raise NotFound("Subject not found.")
        return Response(SubjectDetailSerializer(subject).data)


class SubjectByKeyView(PublicView):
    """Resolves /courses/ca/intermediate/taxation for server-rendered pages."""

    def get(self, request, course, level, subject):
        obj = selectors.get_subject_by_keys(course, level, subject)
        if not obj:
            raise NotFound("Subject not found.")
        return Response(SubjectDetailSerializer(obj).data)


class ChapterDetailView(PublicView):
    def get(self, request, chapter_id):
        chapter = selectors.get_published_chapter(chapter_id)
        if not chapter:
            raise NotFound("Chapter not found.")
        return Response(ChapterDetailSerializer(chapter).data)


class ChapterByKeyView(PublicView):
    def get(self, request, course, level, subject, chapter):
        obj = selectors.get_chapter_by_keys(course, level, subject, chapter)
        if not obj:
            raise NotFound("Chapter not found.")
        return Response(ChapterDetailSerializer(obj).data)


class TermListView(PublicView):
    def get(self, request):
        return Response(ExamTermSerializer(selectors.list_terms(request.query_params.get("course")), many=True).data)


class SitemapPathsView(PublicView):
    def get(self, request):
        return Response({"paths": selectors.sitemap_paths()})


class ReportView(APIView):
    """POST /syllabus/reports/: anonymous or signed-in, rate limited."""

    authentication_classes = [SupabaseJWTAuthentication]
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "syllabus_report"

    def post(self, request):
        serializer = ReportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        user_id = user.id if user and getattr(user, "is_authenticated", False) else None
        try:
            report = services.create_report(user_id=user_id, **serializer.validated_data)
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError({"node_id": exc.messages}) from exc
        return Response({"id": str(report.id), "status": report.status}, status=201)


class SchemeStateView(APIView):
    """Editor-only publish and retire (the admin console arrives later)."""

    permission_classes = [IsSyllabusEditor]
    action = "publish"

    def post(self, request, scheme_id):
        scheme = selectors.get_scheme(scheme_id)
        if not scheme:
            raise NotFound("Scheme not found.")
        operation = services.publish_scheme if self.action == "publish" else services.retire_scheme
        try:
            scheme = operation(scheme)
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError({"detail": exc.messages}) from exc
        return Response(SchemeSerializer(scheme).data)
