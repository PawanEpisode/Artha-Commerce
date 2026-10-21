"""
API views for F-12 Institute Study Material (MAT).
"""

from __future__ import annotations

import uuid
from typing import Any

from rest_framework import permissions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from . import errors, selectors, services
from .models import Provider, UserProvider, Work
from .permissions import IsMaterialEditor, check_material_flag, check_material_mine_flag
from .serializers import (
    CourseBoughtCreateSerializer,
    DraftEditionCreateSerializer,
    FollowedProviderSerializer,
    FollowedProviderUpdateSerializer,
    IndexImportSerializer,
    MatchDecisionSerializer,
    PrivateWorkCreateSerializer,
    ProgressBatchSerializer,
    ProgressUpdateSerializer,
    ProviderCreateSerializer,
    ProviderSerializer,
    ReportCreateSerializer,
    UserEditionUpdateSerializer,
    WorkCreateSerializer,
)


# ==========================================
# Public Endpoints
# ==========================================

class PublicSubjectMaterialView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request: Request, course: str, level: str, subject: str) -> Response:
        data = selectors.public_subject_material(course, level, subject)
        return Response(data)


# ==========================================
# Student Works & Chapters
# ==========================================

class WorkListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request) -> Response:
        check_material_flag(request)
        subject_key = request.query_params.get("subject")
        provider_slug = request.query_params.get("provider")
        data = selectors.list_works(
            request.user.id,
            subject_key=subject_key,
            provider_slug=provider_slug,
        )
        return Response({"works": data})


class WorkDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request, work_key: str) -> Response:
        check_material_flag(request)
        ed_id_param = request.query_params.get("edition")
        edition_id = uuid.UUID(ed_id_param) if ed_id_param else None

        data = selectors.get_work(request.user.id, work_key, edition_id=edition_id)
        if not data:
            raise errors.WorkNotFound()
        return Response(data)


class ChapterItemsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request, work_key: str, chapter_key: str) -> Response:
        check_material_flag(request)
        ed_id_param = request.query_params.get("edition")
        edition_id = uuid.UUID(ed_id_param) if ed_id_param else None

        kind = request.query_params.get("kind")
        state = request.query_params.get("state")
        q = request.query_params.get("q")

        items = selectors.items_for_chapter(
            request.user.id,
            work_key,
            chapter_key,
            edition_id=edition_id,
            kind=kind,
            state=state,
            q=q,
        )
        return Response({"items": items})


class ChapterSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request, chapter_id: str) -> Response:
        check_material_flag(request)
        try:
            ch_uuid = uuid.UUID(chapter_id)
        except ValueError:
            raise errors.MaterialError("Invalid chapter_id format.")

        data = selectors.chapter_summary(request.user.id, ch_uuid)
        return Response(data)


class EditionChangesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request, work_key: str) -> Response:
        check_material_flag(request)
        from_id_param = request.query_params.get("from")
        to_id_param = request.query_params.get("to")
        if not from_id_param or not to_id_param:
            raise errors.MaterialError("Both 'from' and 'to' edition IDs are required.")

        chapter_key = request.query_params.get("chapter")
        changes = selectors.compare_editions(
            work_key,
            uuid.UUID(from_id_param),
            uuid.UUID(to_id_param),
            chapter_key=chapter_key,
        )
        return Response({"changes": changes})


# ==========================================
# Items
# ==========================================

class ItemDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request, item_id: str) -> Response:
        check_material_flag(request)
        try:
            i_uuid = uuid.UUID(item_id)
        except ValueError:
            raise errors.ItemNotFound()

        ed_id_param = request.query_params.get("edition")
        edition_id = uuid.UUID(ed_id_param) if ed_id_param else None

        data = selectors.get_item(request.user.id, i_uuid, edition_id=edition_id)
        if not data:
            raise errors.ItemNotFound()
        return Response(data)


class ItemReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request, item_id: str) -> Response:
        check_material_flag(request)
        serializer = ReportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            i_uuid = uuid.UUID(item_id)
        except ValueError:
            raise errors.ItemNotFound()

        rep = services.submit_report(
            user_id=request.user.id,
            item_id=i_uuid,
            edition_id=data["edition_id"],
            kind=data["kind"],
            message=data.get("message", ""),
        )
        return Response({"id": str(rep.id), "status": rep.status}, status=status.HTTP_201_CREATED)


# ==========================================
# Student Progress & Registry
# ==========================================

class ProgressUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def put(self, request: Request, item_id: str) -> Response:
        check_material_flag(request)
        serializer = ProgressUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            i_uuid = uuid.UUID(item_id)
        except ValueError:
            raise errors.ItemNotFound()

        prog = services.set_progress(
            user_id=request.user.id,
            item_id=i_uuid,
            edition_id=data["edition_id"],
            state=data["state"],
            note=data.get("note", ""),
            client_ts=data.get("client_ts"),
            self_declared=data.get("self_declared", False),
        )
        return Response({"item_id": str(prog.item_id), "state": prog.state, "note": prog.note})


class ProgressBatchView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request) -> Response:
        check_material_flag(request)
        serializer = ProgressBatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        res = services.set_progress_batch(
            user_id=request.user.id,
            items=serializer.validated_data["items"],
        )
        return Response({"results": res})


class UserEditionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def put(self, request: Request, work_key: str) -> Response:
        check_material_flag(request)
        serializer = UserEditionUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        work = Work.objects.filter(work_key=work_key).first()
        if not work:
            raise errors.WorkNotFound()

        user_ed = services.set_user_edition(
            user_id=request.user.id,
            work_id=work.id,
            edition_id=serializer.validated_data["edition_id"],
        )
        return Response({
            "work_key": work_key,
            "edition_id": str(user_ed.edition_id) if user_ed.edition_id else None,
        })


class UserBannerDismissView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request, work_key: str) -> Response:
        check_material_flag(request)
        work = Work.objects.filter(work_key=work_key).first()
        if not work:
            raise errors.WorkNotFound()

        edition_id_str = request.data.get("edition_id")
        if not edition_id_str:
            raise errors.MaterialError("edition_id is required.")

        services.dismiss_banner(
            user_id=request.user.id,
            work_id=work.id,
            edition_id=uuid.UUID(edition_id_str),
        )
        return Response({"status": "dismissed"})


class ProviderListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request) -> Response:
        check_material_flag(request)
        q = request.query_params.get("q", "").strip()
        qs = Provider.objects.filter(status__in=[Provider.Status.ACTIVE, Provider.Status.PENDING])
        if q:
            qs = qs.filter(name__icontains=q)
        serializer = ProviderSerializer(qs[:30], many=True)
        return Response({"providers": serializer.data})

    def post(self, request: Request) -> Response:
        check_material_flag(request)
        serializer = ProviderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        prov = services.create_provider(
            actor_id=request.user.id,
            payload=serializer.validated_data,
        )
        return Response(ProviderSerializer(prov).data, status=status.HTTP_201_CREATED)


class UserProviderListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request) -> Response:
        check_material_flag(request)
        data = selectors.followed_providers(request.user.id)
        return Response({"providers": data})

    def post(self, request: Request) -> Response:
        check_material_flag(request)
        # Supports updating followed providers list OR adding a course bought
        if "relation" in request.data and request.data["relation"] == "bought_course":
            serializer = CourseBoughtCreateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            d = serializer.validated_data
            provider = Provider.objects.get(id=d["provider_id"])
            up = UserProvider.objects.create(
                user_id=request.user.id,
                provider=provider,
                relation=UserProvider.Relation.BOUGHT_COURSE,
                course_title=d["course_title"],
                batch_label=d.get("batch_label", ""),
                purchased_on=d.get("purchased_on"),
                valid_until=d.get("valid_until"),
                subject_keys=d.get("subject_keys", []),
                created_via="settings",
            )
            return Response(FollowedProviderSerializer(up).data, status=status.HTTP_201_CREATED)
        else:
            serializer = FollowedProviderUpdateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            d = serializer.validated_data
            followed = services.set_followed_providers(
                user_id=request.user.id,
                provider_ids=d.get("provider_ids", []),
                custom_names=d.get("custom_names", []),
            )
            return Response({"followed": ProviderSerializer(followed, many=True).data})


class UserProviderDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request: Request, pk: str) -> Response:
        check_material_flag(request)
        UserProvider.objects.filter(id=pk, user_id=request.user.id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PrivateWorkListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request) -> Response:
        check_material_mine_flag(request)
        works = Work.objects.filter(owner_user_id=request.user.id, status=Work.Status.ACTIVE)
        res = selectors.list_works(request.user.id, include_private=True)
        private_only = [w for w in res if w.get("visibility") == "private"]
        return Response({"works": private_only})

    def post(self, request: Request) -> Response:
        check_material_mine_flag(request)
        serializer = PrivateWorkCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        work = services.create_private_work(request.user.id, serializer.validated_data)
        return Response({"id": str(work.id), "work_key": work.work_key, "title": work.title}, status=status.HTTP_201_CREATED)


class UserDataExportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request) -> Response:
        data = services.export_for_user(request.user.id)
        return Response(data)


class UserDataDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request: Request) -> Response:
        report = services.delete_all_for_user(request.user.id)
        return Response({"deleted": report})


# ==========================================
# Admin Endpoints
# ==========================================

class AdminProviderMergeView(APIView):
    permission_classes = [IsMaterialEditor]

    def post(self, request: Request, pk: str) -> Response:
        target_id_str = request.data.get("target_provider_id")
        if not target_id_str:
            raise errors.MaterialError("target_provider_id is required.")
        target = services.merge_provider(request.user.id, uuid.UUID(pk), uuid.UUID(target_id_str))
        return Response(ProviderSerializer(target).data)


class AdminWorkCreateView(APIView):
    permission_classes = [IsMaterialEditor]

    def post(self, request: Request) -> Response:
        serializer = WorkCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        work = services.create_work(request.user.id, serializer.validated_data)
        return Response({"id": str(work.id), "work_key": work.work_key}, status=status.HTTP_201_CREATED)


class AdminEditionCreateView(APIView):
    permission_classes = [IsMaterialEditor]

    def post(self, request: Request, work_id: str) -> Response:
        serializer = DraftEditionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        edition = services.create_draft_edition(
            request.user.id, uuid.UUID(work_id), serializer.validated_data
        )
        return Response({"id": str(edition.id), "label": edition.label, "status": edition.status}, status=status.HTTP_201_CREATED)


class AdminEditionImportView(APIView):
    permission_classes = [IsMaterialEditor]

    def post(self, request: Request, pk: str) -> Response:
        serializer = IndexImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        job = services.import_index(
            actor_id=request.user.id,
            edition_id=uuid.UUID(pk),
            items_data=serializer.validated_data["items_data"],
            units_data=serializer.validated_data.get("units_data"),
        )
        return Response({"job_id": str(job.id), "status": job.status, "counts": job.counts}, status=status.HTTP_201_CREATED)


class AdminEditionMatchView(APIView):
    permission_classes = [IsMaterialEditor]

    def post(self, request: Request, pk: str) -> Response:
        counts = services.run_matching(request.user.id, uuid.UUID(pk))
        return Response({"counts": counts})


class AdminMatchDecisionView(APIView):
    permission_classes = [IsMaterialEditor]

    def put(self, request: Request, pk: str) -> Response:
        serializer = MatchDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        row = services.decide_match(
            actor_id=request.user.id,
            edition_item_id=uuid.UUID(pk),
            decision=d["decision"],
            target_item_id=d.get("target_item_id"),
        )
        return Response({"id": str(row.id), "change_kind": row.change_kind, "match_status": row.match_status})


class AdminEditionPublishView(APIView):
    permission_classes = [IsMaterialEditor]

    def post(self, request: Request, pk: str) -> Response:
        edition = services.publish_edition(request.user.id, uuid.UUID(pk))
        return Response({"id": str(edition.id), "status": edition.status, "level": edition.level_at_publish})


class AdminEditionWithdrawView(APIView):
    permission_classes = [IsMaterialEditor]

    def post(self, request: Request, pk: str) -> Response:
        reason = request.data.get("reason", "editorial")
        edition = services.withdraw_edition(request.user.id, uuid.UUID(pk), reason=reason)
        return Response({"id": str(edition.id), "status": edition.status, "withdraw_reason": edition.withdraw_reason})


class AdminEditionRestoreView(APIView):
    permission_classes = [IsMaterialEditor]

    def post(self, request: Request, pk: str) -> Response:
        edition = services.restore_edition(request.user.id, uuid.UUID(pk))
        return Response({"id": str(edition.id), "status": edition.status})
