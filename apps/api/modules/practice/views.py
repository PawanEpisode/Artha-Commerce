"""
API views for Practice Engine (F-06 ERD 3.2, 5, 6, 7, E-F06-1).
"""

from __future__ import annotations

import dataclasses
import uuid

from django.http import Http404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.feature_flags import flag_enabled

from . import selectors, services
from .serializers import (
    CheckAnswerSerializer,
    CreateSessionFromItemsSerializer,
    CreateSessionSerializer,
    MistakeReasonSerializer,
    QuestionStateUpdateSerializer,
    RetakeSessionSerializer,
    SaveAnswerSerializer,
)


def _check_qb_flag(request) -> None:
    user_id = request.user.id if getattr(request.user, "is_authenticated", False) else None
    if not flag_enabled("question_bank", user_id, strict=True):
        raise Http404("Question bank feature is not enabled.")


class PracticeBaseView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        _check_qb_flag(request)


class SessionListCreateView(PracticeBaseView):
    def get_throttled_scope(self):
        return "qb_read" if self.request.method == "GET" else "qb_write"

    @property
    def throttle_scope(self) -> str:
        return self.get_throttled_scope()

    def get(self, request):
        cursor = request.query_params.get("cursor")
        limit = min(int(request.query_params.get("limit", 20)), 100)
        status_filter = request.query_params.get("status")
        mode_filter = request.query_params.get("mode")
        origin_filter = request.query_params.get("origin")

        page = selectors.list_sessions(
            user_id=request.user.id,
            cursor=cursor,
            limit=limit,
            status=status_filter,
            mode=mode_filter,
            origin=origin_filter,
        )

        return Response(
            {
                "items": [dataclasses.asdict(item) for item in page.items],
                "next_cursor": page.next_cursor,
                "total": page.total,
            }
        )

    def post(self, request):
        if "items" in request.data:
            serializer = CreateSessionFromItemsSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data

            try:
                session = services.create_session_from_items(
                    user_id=request.user.id,
                    items=data["items"],
                    origin=data["origin"],
                    mode=data["mode"],
                    title=data.get("title", ""),
                    config=data.get("config", {}),
                    client_id=data.get("client_id"),
                )
            except services.UnsupportedOrigin as e:
                return Response(
                    {"error": {"code": "unsupported_origin", "detail": str(e)}}, status=status.HTTP_400_BAD_REQUEST
                )
            except services.ModeNotAllowed as e:
                return Response(
                    {"error": {"code": "mode_not_allowed", "detail": str(e)}}, status=status.HTTP_400_BAD_REQUEST
                )
        else:
            serializer = CreateSessionSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data

            try:
                session = services.create_session(
                    user_id=request.user.id,
                    origin=data["origin"],
                    mode=data["mode"],
                    title=data.get("title", ""),
                    picker=data["picker"],
                    picker_params=data["picker_params"],
                    feedback_policy=data.get("feedback_policy"),
                    config=data.get("config", {}),
                    client_id=data.get("client_id"),
                )
            except services.PickerEmpty as e:
                return Response(
                    {"error": {"code": "picker_empty", "detail": str(e)}}, status=status.HTTP_422_UNPROCESSABLE_ENTITY
                )
            except services.UnsupportedOrigin as e:
                return Response(
                    {"error": {"code": "unsupported_origin", "detail": str(e)}}, status=status.HTTP_400_BAD_REQUEST
                )
            except services.ModeNotAllowed as e:
                return Response(
                    {"error": {"code": "mode_not_allowed", "detail": str(e)}}, status=status.HTTP_400_BAD_REQUEST
                )

        view = selectors.get_session(request.user.id, session.session_id)
        return Response(dataclasses.asdict(view), status=status.HTTP_201_CREATED)


class SessionDetailView(PracticeBaseView):
    throttle_scope = "qb_read"

    def get(self, request, session_id: uuid.UUID):
        try:
            view = selectors.get_session(request.user.id, session_id)
        except ValueError:
            raise Http404("Session not found.") from None
        return Response(dataclasses.asdict(view))


class SaveAnswerView(PracticeBaseView):
    throttle_scope = "qb_write"

    def post(self, request, session_id: uuid.UUID, item_id: uuid.UUID):
        serializer = SaveAnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            ans = services.save_answer(
                session_id=session_id,
                user_id=request.user.id,
                question_id=item_id,
                answer_json=data.get("answer_json", {}),
                client_ts=data.get("client_ts", ""),
                time_spent_ms=data.get("time_spent_ms", 0),
                confidence=data.get("confidence", "sure"),
                flagged=data.get("flagged", False),
                notes_md=data.get("notes_md", ""),
            )
        except services.SessionNotFound:
            raise Http404("Session not found.") from None
        except services.SessionClosed:
            return Response(
                {"error": {"code": "session_closed", "detail": "Session is already submitted or closed."}},
                status=status.HTTP_409_CONFLICT,
            )
        except services.AnswerLocked:
            return Response(
                {"error": {"code": "answer_locked", "detail": "Answer has already been checked and locked."}},
                status=status.HTTP_409_CONFLICT,
            )
        except ValueError as e:
            return Response({"error": {"code": "invalid_item", "detail": str(e)}}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"status": "saved", "answer_id": str(ans.id)})


class CheckAnswerView(PracticeBaseView):
    throttle_scope = "qb_write"

    def post(self, request, session_id: uuid.UUID, item_id: uuid.UUID):
        serializer = CheckAnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            feedback = services.check_answer(
                session_id=session_id,
                user_id=request.user.id,
                question_id=item_id,
                answer_json=data.get("answer_json", {}),
            )
        except services.SessionNotFound:
            raise Http404("Session not found.") from None
        except services.SessionClosed:
            return Response(
                {"error": {"code": "session_closed", "detail": "Session is already submitted or closed."}},
                status=status.HTTP_409_CONFLICT,
            )
        except services.InstantFeedbackDisabled:
            return Response(
                {
                    "error": {
                        "code": "feedback_disabled",
                        "detail": "Instant feedback is not permitted for this session.",
                    }
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        except ValueError as e:
            return Response({"error": {"code": "invalid_item", "detail": str(e)}}, status=status.HTTP_400_BAD_REQUEST)

        return Response(dataclasses.asdict(feedback))


class PauseSessionView(PracticeBaseView):
    throttle_scope = "qb_write"

    def post(self, request, session_id: uuid.UUID):
        try:
            services.pause_session(session_id=session_id, user_id=request.user.id)
        except services.SessionNotFound:
            raise Http404("Session not found.") from None
        except services.SessionClosed:
            return Response(
                {"error": {"code": "session_closed", "detail": "Session cannot be paused in its current state."}},
                status=status.HTTP_409_CONFLICT,
            )
        except services.PauseNotAllowed:
            return Response(
                {"error": {"code": "pause_not_allowed", "detail": "Pausing is not allowed for this session."}},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response({"status": "paused"})


class ResumeSessionView(PracticeBaseView):
    throttle_scope = "qb_write"

    def post(self, request, session_id: uuid.UUID):
        try:
            services.resume_session(session_id=session_id, user_id=request.user.id)
        except services.SessionNotFound:
            raise Http404("Session not found.") from None
        except services.SessionClosed:
            return Response(
                {"error": {"code": "session_closed", "detail": "Session is not paused."}},
                status=status.HTTP_409_CONFLICT,
            )

        return Response({"status": "in_progress"})


class SubmitSessionView(PracticeBaseView):
    throttle_scope = "qb_write"

    def post(self, request, session_id: uuid.UUID):
        try:
            session = services.submit_session(session_id=session_id, user_id=request.user.id)
        except services.SessionNotFound:
            raise Http404("Session not found.") from None
        except services.SessionClosed:
            return Response(
                {"error": {"code": "session_closed", "detail": "Session is already submitted."}},
                status=status.HTTP_409_CONFLICT,
            )

        view = selectors.get_session(request.user.id, session.session_id)
        return Response(dataclasses.asdict(view))


class RetakeSessionView(PracticeBaseView):
    throttle_scope = "qb_write"

    def post(self, request, session_id: uuid.UUID):
        serializer = RetakeSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        scope = serializer.validated_data.get("scope", "all")

        try:
            new_session = services.retake(session_id=session_id, user_id=request.user.id, scope=scope)
        except services.SessionNotFound:
            raise Http404("Session not found.") from None
        except services.ForbiddenRetake:
            return Response(
                {"error": {"code": "retake_forbidden", "detail": "Retake is not permitted for this session."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        except services.PickerEmpty:
            return Response(
                {"error": {"code": "no_items_in_scope", "detail": f"No questions match scope {scope}."}},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        view = selectors.get_session(request.user.id, new_session.session_id)
        return Response(dataclasses.asdict(view), status=status.HTTP_201_CREATED)


class MistakeReasonView(PracticeBaseView):
    throttle_scope = "qb_write"

    def post(self, request, session_id: uuid.UUID, item_id: uuid.UUID):
        serializer = MistakeReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data["mistake_reason"]

        try:
            services.set_mistake_reason(
                session_id=session_id,
                user_id=request.user.id,
                question_id=item_id,
                mistake_reason=reason,
            )
        except services.SessionNotFound:
            raise Http404("Session or attempt answer not found.") from None

        return Response({"status": "updated", "mistake_reason": reason})


class QuestionStateUpdateView(PracticeBaseView):
    throttle_scope = "qb_write"

    def post(self, request, question_id: uuid.UUID):
        serializer = QuestionStateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        services.set_question_state(
            user_id=request.user.id,
            question_id=question_id,
            bookmarked=data.get("bookmarked"),
            notes=data.get("notes"),
        )
        return Response({"status": "updated"})


class ProgressByChapterView(PracticeBaseView):
    throttle_scope = "qb_read"

    def get(self, request, chapter_id: uuid.UUID | None = None):
        if chapter_id:
            ch_ids = [chapter_id]
        else:
            raw_ids = request.query_params.get("chapter_ids", "")
            if not raw_ids:
                return Response({"progress": {}})
            try:
                ch_ids = [uuid.UUID(x.strip()) for x in raw_ids.split(",") if x.strip()]
            except ValueError:
                return Response({"error": {"code": "invalid_chapter_ids"}}, status=status.HTTP_400_BAD_REQUEST)

        stamp = selectors.state_stamp(request.user.id)
        if request.headers.get("If-None-Match") == f'"{stamp}"':
            return Response(status=status.HTTP_304_NOT_MODIFIED)

        progress = selectors.progress_by_chapter(request.user.id, ch_ids)
        resp_data = {
            "progress": {str(k): dataclasses.asdict(v) for k, v in progress.items()},
        }
        resp = Response(resp_data)
        resp["ETag"] = f'"{stamp}"'
        return resp


class BookmarksListView(PracticeBaseView):
    throttle_scope = "qb_read"

    def get(self, request):
        cursor = request.query_params.get("cursor")
        limit = min(int(request.query_params.get("limit", 20)), 100)

        page = selectors.list_bookmarks(request.user.id, cursor=cursor, limit=limit)
        return Response(
            {
                "items": [dataclasses.asdict(item) for item in page.items],
                "next_cursor": page.next_cursor,
            }
        )


class MistakesListView(PracticeBaseView):
    throttle_scope = "qb_read"

    def get(self, request):
        cursor = request.query_params.get("cursor")
        limit = min(int(request.query_params.get("limit", 20)), 100)
        ch_str = request.query_params.get("chapter_id")
        chapter_id = uuid.UUID(ch_str) if ch_str else None

        page = selectors.list_mistakes(request.user.id, chapter_id=chapter_id, cursor=cursor, limit=limit)
        return Response(
            {
                "items": [dataclasses.asdict(item) for item in page.items],
                "next_cursor": page.next_cursor,
            }
        )
