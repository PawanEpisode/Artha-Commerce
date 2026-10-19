"""
API views for Level Transition, Student Progression, Articleship, and Vault (F-18).
"""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import selectors, services
from .errors import ProgressionError, to_api_exception
from .serializers import (
    ArticleshipInputSerializer,
    RollbackRequestSerializer,
    TransitionRequestSerializer,
)


class ProgressionStatusView(APIView):
    """
    Returns active enrollment status, articleship configuration, exemptions,
    available transitions, and term result prompt eligibility.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = selectors.get_progression_status(request.user.id)
        return Response(data)


class TransitionView(APIView):
    """
    Executes a level graduation, group clearance, or paper exemption transition.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = TransitionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            result = services.execute_transition(
                user_id=request.user.id,
                transition_type=data["transition_type"],
                target_course_code=data.get("target_course_code"),
                target_level_code=data.get("target_level_code"),
                target_scheme_id=data.get("target_scheme_id"),
                target_term_id=data.get("target_term_id"),
                cleared_group_keys=data.get("cleared_group_keys"),
                paper_results=data.get("paper_results"),
                articleship_data=data.get("articleship"),
                trigger=data.get("trigger", "user_initiated"),
                metadata=data.get("metadata"),
            )
            return Response(result, status=status.HTTP_201_CREATED)
        except ProgressionError as err:
            raise to_api_exception(err) from err


class TransitionRollbackView(APIView):
    """
    Undoes an applied level transition within the 48-hour safety window.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RollbackRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = services.rollback_transition(
                user_id=request.user.id,
                transition_id=serializer.validated_data["transition_id"],
            )
            return Response(result, status=status.HTTP_200_OK)
        except ProgressionError as err:
            raise to_api_exception(err) from err


class ArticleshipView(APIView):
    """
    Read or update practical training (articleship) profile and study schedules.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = selectors.get_articleship_profile(request.user.id)
        return Response(selectors.articleship_dict(profile))

    def put(self, request):
        serializer = ArticleshipInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = services.upsert_articleship(request.user.id, serializer.validated_data)
        return Response(selectors.articleship_dict(profile), status=status.HTTP_200_OK)

    def patch(self, request):
        serializer = ArticleshipInputSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        profile = services.upsert_articleship(request.user.id, serializer.validated_data)
        return Response(selectors.articleship_dict(profile), status=status.HTTP_200_OK)


class VaultEnrollmentsView(APIView):
    """
    Lists archived enrollments with their subjects, documents, and past notes counts.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        vault_list = selectors.get_vault_enrollments(request.user.id)
        return Response({"enrollments": vault_list})


class TransitionHistoryView(APIView):
    """
    Returns student transition history audit ledger with rollback eligibility.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        history = selectors.get_transition_history(request.user.id)
        return Response({"history": history})
