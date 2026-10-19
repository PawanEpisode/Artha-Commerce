"""
REST API views for F-11 Paper Analysis and Recommendations.
"""

from __future__ import annotations

from dataclasses import asdict
from uuid import UUID

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core import jobs as core_jobs
from core.permissions import ParsedAPIView, flag_required
from modules.syllabus.models import Chapter, Subject

from .domain.types import AllocationIn
from .jobs import JOB_BACKTEST, JOB_SUGGEST, check_ai_budget
from .models import BacktestRun, Paper, WeightSet
from .permissions import IsAdmin, IsEditor, PaperAnalysisFlag, PaperAnalysisPlannerFlag
from .selectors import (
    asked_summary,
    chapter_history,
    chapter_priority,
    chapter_stats,
    get_or_create_settings,
    my_active_plan,
    patterns,
    subject_statuses,
)
from .serializers import (
    ConfirmQuestionSerializer,
    FlagCreateSerializer,
    PaperCreateSerializer,
    PaperDetailSerializer,
    PaperListSerializer,
    PaperPublishSerializer,
    PaperQuestionSerializer,
    PaperUnpublishSerializer,
    PlanAdoptSerializer,
    PlanItemSerializer,
    PlanItemUpdateSerializer,
    PlanPreviewRequestSerializer,
    PlanReplanSerializer,
    PlanSerializer,
    QaDecisionSerializer,
    SetAllocationsSerializer,
    SettingsSerializer,
    SkeletonImportSerializer,
    SuggestSerializer,
)
from .services import (
    adopt_plan,
    confirm_question,
    create_paper,
    decide_qa,
    end_plan,
    flag,
    import_skeleton_csv,
    preview_plan,
    publish_paper,
    replan,
    set_allocations,
    unpublish_paper,
    update_plan_item,
)

PublicAnalysisFlag = flag_required("paper_analysis_public", strict=True)


# --- Student Recommendation Views ---

class RecommendationsView(APIView):
    permission_classes = [IsAuthenticated, PaperAnalysisFlag]

    def get(self, request) -> Response:
        subject_key = request.query_params.get("subject_key")
        enrollment_id_str = request.query_params.get("enrollment_id")
        enrollment_id = UUID(enrollment_id_str) if enrollment_id_str else None
        force_refresh = request.query_params.get("refresh", "false").lower() in ("true", "1")

        priority_view = chapter_priority(
            user_id=request.user.id,
            enrollment_id=enrollment_id,
            subject_key=subject_key,
            force_refresh=force_refresh,
        )

        # Convert frozen dataclass to dict
        data = asdict(priority_view)
        # Format UUIDs as strings
        data["snapshot_id"] = str(data["snapshot_id"])
        data["weightset_id"] = str(data["weightset_id"])
        for s in data["subjects"]:
            for ch in s["chapters"]:
                ch["chapter_id"] = str(ch["chapter_id"])

        return Response(data)


class SubjectStatusesView(APIView):
    permission_classes = [IsAuthenticated, PaperAnalysisFlag]

    def get(self, request) -> Response:
        enrollment_id_str = request.query_params.get("enrollment_id")
        enrollment_id = UUID(enrollment_id_str) if enrollment_id_str else None
        statuses = subject_statuses(request.user.id, enrollment_id=enrollment_id)
        return Response({"subjects": statuses})


class ChapterStatsView(APIView):
    permission_classes = [IsAuthenticated, PaperAnalysisFlag]

    def get(self, request, subject_key: str) -> Response:
        from modules.coverage.selectors import exam_context

        ctx = exam_context(request.user.id)
        subject = None
        if ctx and ctx.scheme_id:
            subject = Subject.objects.filter(scheme_id=ctx.scheme_id, key=subject_key).first()
        if not subject:
            subject = Subject.objects.filter(key=subject_key).first()

        window = int(request.query_params.get("window", 6))
        if not subject:
            return Response({"subject_key": subject_key, "window": window, "chapters": []})

        stats = chapter_stats(subject.id, window=window)
        return Response({"subject_key": subject_key, "window": window, "chapters": stats})


class PatternsView(APIView):
    permission_classes = [IsAuthenticated, PaperAnalysisFlag]

    def get(self, request, subject_key: str) -> Response:
        from modules.coverage.selectors import exam_context

        ctx = exam_context(request.user.id)
        subject = None
        if ctx and ctx.scheme_id:
            subject = Subject.objects.filter(scheme_id=ctx.scheme_id, key=subject_key).first()
        if not subject:
            subject = Subject.objects.filter(key=subject_key).first()

        window = int(request.query_params.get("window", 6))
        if not subject:
            return Response({
                "papers_considered": 0,
                "avg_total_marks": 0.0,
                "avg_attemptable_marks": 0.0,
                "avg_optional_marks": 0.0,
                "formats": {},
                "sections": [],
            })

        pat = patterns(subject.id, window=window)
        return Response(pat)


class ChapterHistoryView(APIView):
    permission_classes = [IsAuthenticated, PaperAnalysisFlag]

    def get(self, request, chapter_key: str) -> Response:
        chapter = Chapter.objects.filter(key=chapter_key).first()
        window = int(request.query_params.get("window", 12))
        if not chapter:
            return Response({"chapter_key": chapter_key, "history": []})
        history = chapter_history(chapter.id, window=window)
        return Response({"chapter_key": chapter_key, "history": history})


class AskedSummaryView(APIView):
    permission_classes = [IsAuthenticated, PaperAnalysisFlag]

    def get(self, request) -> Response:
        q_ids = request.query_params.getlist("question_ids")
        if not q_ids:
            raw_ids = request.query_params.get("question_ids", "")
            q_ids = [s.strip() for s in raw_ids.split(",") if s.strip()]

        uuid_ids = [UUID(qid) for qid in q_ids]
        summaries = asked_summary(uuid_ids)

        out = {}
        for qid, summ in summaries.items():
            out[str(qid)] = asdict(summ) if summ else None

        return Response({"summaries": out})


class StudentSettingsView(APIView):
    permission_classes = [IsAuthenticated, PaperAnalysisFlag]

    def get(self, request) -> Response:
        settings = get_or_create_settings(request.user.id)
        return Response(SettingsSerializer(settings).data)

    def put(self, request) -> Response:
        settings = get_or_create_settings(request.user.id)
        serializer = SettingsSerializer(settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


# --- Plan Views ---

class PlanPreviewView(ParsedAPIView):
    permission_classes = [IsAuthenticated, PaperAnalysisFlag, PaperAnalysisPlannerFlag]

    def post(self, request) -> Response:
        ser = self.parse(PlanPreviewRequestSerializer, request.data)
        data = ser.validated_data

        preview = preview_plan(
            user_id=request.user.id,
            days=data["days"],
            hours_per_day=data["hours_per_day"],
            subject_keys=data.get("subject_keys"),
            balance_subjects=data.get("balance_subjects", False),
        )

        res = asdict(preview)
        if res.get("snapshot_id"):
            res["snapshot_id"] = str(res["snapshot_id"])
        for it in res.get("items", []):
            it["chapter_id"] = str(it["chapter_id"])

        return Response(res)


class ActivePlanView(APIView):
    permission_classes = [IsAuthenticated, PaperAnalysisFlag, PaperAnalysisPlannerFlag]

    def get(self, request) -> Response:
        plan = my_active_plan(request.user.id)
        if not plan:
            return Response({"plan": None})
        return Response({"plan": PlanSerializer(plan).data})

    def delete(self, request) -> Response:
        plan = my_active_plan(request.user.id)
        if not plan:
            return Response({"status": "no_active_plan"}, status=status.HTTP_404_NOT_FOUND)
        end_plan(request.user.id, plan.id)
        return Response({"status": "ended"})


class PlanAdoptView(ParsedAPIView):
    permission_classes = [IsAuthenticated, PaperAnalysisFlag, PaperAnalysisPlannerFlag]

    def post(self, request) -> Response:
        ser = self.parse(PlanAdoptSerializer, request.data)
        data = ser.validated_data

        plan = adopt_plan(
            user_id=request.user.id,
            client_id=data["client_id"],
            days=data["days"],
            hours_per_day=data["hours_per_day"],
            subject_keys=data.get("subject_keys"),
            balance_subjects=data.get("balance_subjects", False),
            start_date=data.get("start_date"),
        )
        return Response(PlanSerializer(plan).data, status=status.HTTP_201_CREATED)


class PlanReplanView(ParsedAPIView):
    permission_classes = [IsAuthenticated, PaperAnalysisFlag, PaperAnalysisPlannerFlag]

    def post(self, request) -> Response:
        ser = self.parse(PlanReplanSerializer, request.data)
        data = ser.validated_data

        active = my_active_plan(request.user.id)
        if not active:
            return Response({"error": "no_active_plan"}, status=status.HTTP_404_NOT_FOUND)

        new_plan = replan(
            user_id=request.user.id,
            plan_id=active.id,
            days_remaining=data["days_remaining"],
            hours_per_day=data["hours_per_day"],
        )
        return Response(PlanSerializer(new_plan).data)


class PlanItemDetailView(ParsedAPIView):
    permission_classes = [IsAuthenticated, PaperAnalysisFlag, PaperAnalysisPlannerFlag]

    def patch(self, request, item_id: str) -> Response:
        ser = self.parse(PlanItemUpdateSerializer, request.data)
        data = ser.validated_data

        item = update_plan_item(
            user_id=request.user.id,
            item_id=UUID(item_id),
            state=data["state"],
            planned_date=data.get("planned_date"),
        )
        return Response(PlanItemSerializer(item).data)


# --- Flag View ---

class FlagCreateView(ParsedAPIView):
    permission_classes = [IsAuthenticated, PaperAnalysisFlag]

    def post(self, request) -> Response:
        ser = self.parse(FlagCreateSerializer, request.data)
        data = ser.validated_data

        flg = flag(
            user_id=request.user.id,
            target_type=data["target_type"],
            target_id=data["target_id"],
            note=data["note"],
            source="student",
        )
        return Response({"id": str(flg.id), "status": "flagged"}, status=status.HTTP_201_CREATED)


# --- Editorial/Admin Views ---

class PaperListCreateView(ParsedAPIView):
    permission_classes = [IsAuthenticated, PaperAnalysisFlag, IsEditor]

    def get(self, request) -> Response:
        qs = Paper.objects.all().order_by("-updated_at")
        subject_key = request.query_params.get("subject_key")
        if subject_key:
            qs = qs.filter(subject_key=subject_key)
        stat = request.query_params.get("status")
        if stat:
            qs = qs.filter(status=stat)

        return Response(PaperListSerializer(qs[:100], many=True).data)

    def post(self, request) -> Response:
        ser = self.parse(PaperCreateSerializer, request.data)
        data = ser.validated_data

        paper = create_paper(
            editor_id=request.user.id,
            subject_id=data["subject_id"],
            term_code=data["term_code"],
            paper_kind=data["paper_kind"],
            series=data["series"],
            total_marks=data["total_marks"],
            duration_minutes=data.get("duration_minutes"),
            source_url=data.get("source_url"),
        )
        return Response(PaperDetailSerializer(paper).data, status=status.HTTP_201_CREATED)


class PaperDetailView(APIView):
    permission_classes = [IsAuthenticated, PaperAnalysisFlag, IsEditor]

    def get(self, request, paper_id: str) -> Response:
        paper = get_object_or_404(
            Paper.objects.prefetch_related("questions__allocations", "choice_groups"),
            pk=UUID(paper_id),
        )
        return Response(PaperDetailSerializer(paper).data)


class PaperImportView(ParsedAPIView):
    permission_classes = [IsAuthenticated, PaperAnalysisFlag, IsEditor]

    def post(self, request, paper_id: str) -> Response:
        ser = self.parse(SkeletonImportSerializer, request.data)
        data = ser.validated_data

        report = import_skeleton_csv(
            editor_id=request.user.id,
            paper_id=UUID(paper_id),
            csv_content=data["csv_content"],
            dry_run=data["dry_run"],
        )
        return Response({
            "is_valid": len(report.errors) == 0,
            "total_rows": report.total_rows,
            "questions_created": report.questions_created,
            "allocations_created": report.allocations_created,
            "errors": report.errors,
            "dry_run": report.dry_run,
        })


class PaperSuggestView(ParsedAPIView):
    permission_classes = [IsAuthenticated, PaperAnalysisFlag, IsEditor]

    def post(self, request, paper_id: str) -> Response:
        ser = self.parse(SuggestSerializer, request.data)
        p_uuid = UUID(paper_id)
        get_object_or_404(Paper, pk=p_uuid)

        # Check budget before queueing
        check_ai_budget(increment=0)

        q_ids = [str(qid) for qid in ser.validated_data.get("question_ids", [])]

        core_jobs.enqueue(
            JOB_SUGGEST,
            {"paper_id": str(p_uuid), "question_ids": q_ids},
            dedupe_key=f"{JOB_SUGGEST}:{p_uuid}",
        )
        return Response({"status": "queued"}, status=status.HTTP_202_ACCEPTED)


class PaperPublishView(ParsedAPIView):
    permission_classes = [IsAuthenticated, PaperAnalysisFlag, IsEditor]

    def post(self, request, paper_id: str) -> Response:
        ser = self.parse(PaperPublishSerializer, request.data)
        data = ser.validated_data

        paper = publish_paper(
            editor_id=request.user.id,
            paper_id=UUID(paper_id),
            rev=data["rev"],
            exception_note=data.get("exception_note"),
        )
        return Response(PaperDetailSerializer(paper).data)


class PaperUnpublishView(ParsedAPIView):
    permission_classes = [IsAuthenticated, PaperAnalysisFlag, IsEditor]

    def post(self, request, paper_id: str) -> Response:
        ser = self.parse(PaperUnpublishSerializer, request.data)
        data = ser.validated_data

        paper = unpublish_paper(
            editor_id=request.user.id,
            paper_id=UUID(paper_id),
            reason=data["reason"],
        )
        return Response(PaperDetailSerializer(paper).data)


class QuestionAllocationsView(ParsedAPIView):
    permission_classes = [IsAuthenticated, PaperAnalysisFlag, IsEditor]

    def post(self, request, question_id: str) -> Response:
        ser = self.parse(SetAllocationsSerializer, request.data)
        data = ser.validated_data

        # Map to domain types
        alloc_ins = [
            AllocationIn(
                chapter_id=a["chapter_id"],
                marks=a["marks"],
                topic_id=a.get("topic_id"),
                rationale=a.get("rationale", ""),
            )
            for a in data["allocations"]
        ]

        pq = set_allocations(
            editor_id=request.user.id,
            paper_question_id=UUID(question_id),
            rows=alloc_ins,
            rev=data["rev"],
        )
        return Response(PaperQuestionSerializer(pq).data)


class QuestionConfirmView(ParsedAPIView):
    permission_classes = [IsAuthenticated, PaperAnalysisFlag, IsEditor]

    def post(self, request, question_id: str) -> Response:
        ser = self.parse(ConfirmQuestionSerializer, request.data)
        data = ser.validated_data

        pq = confirm_question(
            editor_id=request.user.id,
            paper_question_id=UUID(question_id),
            rev=data["rev"],
        )
        return Response(PaperQuestionSerializer(pq).data)


class QuestionQaView(ParsedAPIView):
    permission_classes = [IsAuthenticated, PaperAnalysisFlag, IsEditor]

    def post(self, request, question_id: str) -> Response:
        ser = self.parse(QaDecisionSerializer, request.data)
        data = ser.validated_data

        pq = decide_qa(
            qa_id=request.user.id,
            paper_question_id=UUID(question_id),
            decision=data["qa_state"],
            note=data.get("note", ""),
        )
        return Response(PaperQuestionSerializer(pq).data)


class BacktestCreateView(APIView):
    permission_classes = [IsAuthenticated, PaperAnalysisFlag, IsAdmin]

    def post(self, request) -> Response:
        subject_id = request.data.get("subject_id")
        if not subject_id:
            return Response({"error": "subject_id_required"}, status=status.HTTP_400_BAD_REQUEST)

        subject = get_object_or_404(Subject, pk=UUID(str(subject_id)))
        active_ws = WeightSet.objects.filter(is_active=True).first()

        bt = BacktestRun.objects.create(
            subject=subject,
            scheme=subject.scheme,
            weightset=active_ws,
            created_by=request.user.id,
            status=BacktestRun.Status.QUEUED,
        )

        core_jobs.enqueue(
            JOB_BACKTEST,
            {"backtest_id": str(bt.id)},
            dedupe_key=f"{JOB_BACKTEST}:{bt.id}",
        )

        return Response({"id": str(bt.id), "status": "queued"}, status=status.HTTP_202_ACCEPTED)


# --- Public SEO View ---

class PublicAnalysisView(APIView):
    permission_classes = [AllowAny, PublicAnalysisFlag]

    def get(self, request, course: str, level: str, subject_key: str) -> Response:
        subject = get_object_or_404(Subject, key=subject_key)
        stats = chapter_stats(subject.id, window=6)
        pat = patterns(subject.id, window=6)
        return Response({
            "course": course,
            "level": level,
            "subject_key": subject_key,
            "subject_name": subject.name,
            "chapters": stats,
            "patterns": pat,
        })
