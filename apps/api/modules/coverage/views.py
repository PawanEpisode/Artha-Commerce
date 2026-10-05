from __future__ import annotations

from django.utils import timezone
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from modules.syllabus import selectors as syllabus

from . import selectors, serializers, services
from .domain.formula import Weights
from .errors import CoverageError, to_api_exception
from .models import CoverageEvent


class CoverageView(APIView):
    """Authenticated, student-scoped. Domain errors become the API's standard error shape."""

    def handle_exception(self, exc):
        if isinstance(exc, CoverageError):
            exc = to_api_exception(exc)
        return super().handle_exception(exc)

    def today(self, request):
        s = serializers.TodaySerializer(data=request.query_params)
        s.is_valid(raise_exception=True)
        return s.validated_data.get("today") or timezone.now().date()

    def active_enrollment(self, request):
        enrollment = selectors.get_active_enrollment(request.user.id)
        if not enrollment:
            raise NotFound("No active enrolment. Choose your course and level first.")
        return enrollment


class WriteView(CoverageView):
    throttle_classes = [UserRateThrottle, ScopedRateThrottle]
    throttle_scope = "coverage_write"


def _chapter_state(user_id, chapter_id) -> dict:
    """Chapter row plus the roll-ups it feeds, so one response updates the whole screen."""
    progress = selectors.get_chapter_progress(user_id, chapter_id)
    chapter = progress.chapter
    counts = selectors.topic_counts(user_id, [chapter.id])[chapter.id]
    rollups = selectors.rollups_for_enrollment(progress.enrollment)
    return {
        "chapter": serializers.chapter_row(chapter, progress, counts),
        "subject": serializers.rollup_dict(rollups.get(("subject", chapter.subject_id))),
        "level": serializers.rollup_dict(rollups.get(("level", progress.enrollment.scheme.level_id))),
    }


class EnrollmentListView(CoverageView):
    def get(self, request):
        today = self.today(request)
        items = [serializers.enrollment_dict(e, today) for e in selectors.list_enrollments(request.user.id)]
        return Response({"results": items})

    def post(self, request):
        s = serializers.EnrollmentCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        enrollment = services.create_enrollment(
            request.user.id,
            scheme_id=d["scheme"],
            target_term_id=d.get("target_term"),
            exam_date=d.get("exam_date"),
            daily_hours=d.get("daily_hours"),
            electives=d.get("electives"),
        )
        enrollment = selectors.get_enrollment(request.user.id, enrollment.id)
        return Response(serializers.enrollment_dict(enrollment), status=201)


class EnrollmentDetailView(CoverageView):
    def patch(self, request, enrollment_id):
        enrollment = selectors.get_enrollment(request.user.id, enrollment_id)
        if not enrollment:
            raise NotFound("Enrolment not found.")
        s = serializers.EnrollmentPatchSerializer(data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        data = dict(s.validated_data)
        new_scheme = data.pop("scheme", None)
        summary = None
        if new_scheme:
            term = data.get("target_term")
            enrollment, summary = services.switch_scheme(
                request.user.id, enrollment, new_scheme, target_term_id=term.id if term else None
            )
            data.pop("target_term", None)
        if data:
            enrollment = services.update_enrollment(enrollment, data=data)
        enrollment = selectors.get_enrollment(request.user.id, enrollment.id)
        body = serializers.enrollment_dict(enrollment)
        if summary:
            body["switch_summary"] = summary
        return Response(body)


class EnrollmentElectivesView(WriteView):
    """PUT {"choices": {"<slot key>": "<subject id>" | null}}: sets the elective of each slot named and re-counts coverage."""

    def put(self, request, enrollment_id):
        enrollment = selectors.get_enrollment(request.user.id, enrollment_id)
        if not enrollment:
            raise NotFound("Enrolment not found.")
        s = serializers.ElectivesSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.set_electives(enrollment, s.validated_data["choices"])
        enrollment = selectors.get_enrollment(request.user.id, enrollment.id)
        settings = services.get_or_create_settings(request.user.id)
        return Response(
            {
                "electives": serializers.electives_list(enrollment),
                "overview": serializers.overview_dict(enrollment, settings, self.today(request)),
            }
        )


class OverviewView(CoverageView):
    def get(self, request):
        enrollment = self.active_enrollment(request)
        settings = services.get_or_create_settings(request.user.id)
        return Response(serializers.overview_dict(enrollment, settings, self.today(request)))


class SubjectCoverageView(CoverageView):
    def get(self, request, subject_id):
        enrollment = self.active_enrollment(request)
        subject = enrollment.scheme.subjects.filter(pk=subject_id, is_active=True).select_related("group").first()
        if not subject:
            raise NotFound("Subject not found in your syllabus.")
        rows = selectors.subject_chapter_rows(enrollment, subject.id)
        rollup = selectors.rollups_for_enrollment(enrollment).get(("subject", subject.id))
        return Response(
            {
                "subject": {
                    "id": str(subject.id),
                    "key": subject.key,
                    "name": subject.name,
                    "paper_number": subject.paper_number,
                    "total_marks": subject.total_marks,
                    "group_key": subject.group.key if subject.group_id else None,
                    **serializers.rollup_dict(rollup),
                },
                "chapters": [serializers.chapter_row(c, p, counts) for c, p, counts in rows],
            }
        )


class ChapterCoverageView(CoverageView):
    def get(self, request, chapter_id):
        enrollment = self.active_enrollment(request)
        chapter = syllabus.get_chapter(chapter_id)
        if not chapter or chapter.subject.scheme_id != enrollment.scheme_id:
            raise NotFound("Chapter not found in your syllabus.")
        progress = selectors.get_chapter_progress(request.user.id, chapter.id)
        counts = selectors.topic_counts(request.user.id, [chapter.id])[chapter.id]
        states = selectors.topic_states(request.user.id, chapter.id)
        topics = [
            {"id": str(t.id), "key": t.key, "name": t.name, "kind": t.kind, "is_done": states.get(t.id, False)}
            for t in syllabus.list_topics(chapter)
        ]
        prev_chapter, next_chapter = syllabus.neighbour_chapters(chapter)
        return Response(
            {
                "chapter": serializers.chapter_row(chapter, progress, counts),
                "subject": {"id": str(chapter.subject_id), "key": chapter.subject.key, "name": chapter.subject.name},
                "prev_chapter": {"id": str(prev_chapter.id), "name": prev_chapter.name} if prev_chapter else None,
                "next_chapter": {"id": str(next_chapter.id), "name": next_chapter.name} if next_chapter else None,
                "topics": topics,
                "events": [serializers.event_dict(e) for e in selectors.chapter_events(request.user.id, chapter.id)],
                "revision_history": [
                    serializers.event_dict(e) for e in selectors.revision_history(request.user.id, chapter.id)
                ],
            }
        )


class TopicTickView(WriteView):
    def put(self, request, topic_id):
        s = serializers.TickSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        progress = services.tick_topic(
            request.user.id, topic_id, done=d["done"], client_id=d.get("client_id"), occurred_at=d.get("occurred_at")
        )
        return Response(_chapter_state(request.user.id, progress.chapter_id))


class ChapterReadView(WriteView):
    """Tick a chapter that has no topics."""

    def put(self, request, chapter_id):
        s = serializers.TickSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        progress = services.tick_chapter(
            request.user.id, chapter_id, done=d["done"], client_id=d.get("client_id"), occurred_at=d.get("occurred_at")
        )
        return Response(_chapter_state(request.user.id, progress.chapter_id))


class CatchupView(WriteView):
    def post(self, request):
        s = serializers.CatchupSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        result = services.catchup(
            request.user.id, d["chapter_ids"], also_revised=d["also_revised"], client_id=d.get("client_id")
        )
        enrollment = self.active_enrollment(request)
        settings = services.get_or_create_settings(request.user.id)
        return Response({**result, "overview": serializers.overview_dict(enrollment, settings, self.today(request))})


class EventView(WriteView):
    def post(self, request):
        s = serializers.EventCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        services.record_event(
            request.user.id,
            d["chapter_id"],
            d["type"],
            d.get("value"),
            CoverageEvent.Source.MANUAL,
            d.get("client_id"),
            occurred_at=d.get("occurred_at"),
        )
        return Response(_chapter_state(request.user.id, d["chapter_id"]), status=201)


class ConfidenceView(WriteView):
    def put(self, request, chapter_id):
        s = serializers.ConfidenceSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.set_confidence(request.user.id, chapter_id, s.validated_data["confidence"])
        return Response(_chapter_state(request.user.id, chapter_id))


class ChapterExclusionView(WriteView):
    def put(self, request, chapter_id):
        s = serializers.ExclusionSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.set_exclusion(request.user.id, chapter_id, s.validated_data["excluded"])
        return Response(_chapter_state(request.user.id, chapter_id))


class SubjectExclusionView(WriteView):
    def put(self, request, subject_id):
        s = serializers.ExclusionSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        changed = services.set_subject_exclusion(request.user.id, subject_id, s.validated_data["excluded"])
        enrollment = self.active_enrollment(request)
        settings = services.get_or_create_settings(request.user.id)
        return Response(
            {"changed": changed, "overview": serializers.overview_dict(enrollment, settings, self.today(request))}
        )


class DueView(CoverageView):
    def get(self, request):
        enrollment = self.active_enrollment(request)
        today = self.today(request)
        rows = selectors.due_for_revision(enrollment, today)
        counts = selectors.topic_counts(request.user.id, [p.chapter_id for p in rows])
        return Response(
            {
                "today": today.isoformat(),
                "results": [
                    {
                        **serializers.chapter_row(p.chapter, p, counts[p.chapter_id]),
                        "subject": {
                            "id": str(p.chapter.subject_id),
                            "key": p.chapter.subject.key,
                            "name": p.chapter.subject.name,
                        },
                        "overdue_days": (today - p.next_revision_due).days,
                    }
                    for p in rows
                ],
            }
        )


class SettingsView(CoverageView):
    def get(self, request):
        return Response(serializers.settings_dict(services.get_or_create_settings(request.user.id)))

    def put(self, request):
        s = serializers.SettingsSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        settings = services.update_settings(
            request.user.id,
            weights=Weights(d["w_read"], d["w_practice"], d["w_revise"], d["w_mock"]),
            revision_days=d["revision_days"],
            weighted_default=d["weighted_default"],
        )
        return Response(serializers.settings_dict(settings))

    def delete(self, request):
        """Reset to defaults."""
        return Response(serializers.settings_dict(services.reset_settings(request.user.id)))


class DataView(CoverageView):
    """GET exports everything coverage stores about the student; DELETE removes it (FR-29)."""

    def get(self, request):
        return Response(selectors.export_all(request.user.id))

    def delete(self, request):
        services.delete_all_for_user(request.user.id)
        return Response(status=204)
