"""Thin views: authenticate, parse, call a service or selector, present. No business rules here."""

from __future__ import annotations

import time

from core.authentication import BeaconBodyAuthentication, SupabaseJWTAuthentication
from core.feature_flags import flag_enabled
from core.http import tagged_response
from core.parsers import PlainTextJSONParser
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from . import registry, selectors, serializers, services
from .avatar_urls import avatar_summary
from .domain.images import MAX_INPUT_BYTES
from .domain.names import InvalidName
from .errors import (
    AvatarUploadDisabled,
    BodyTooLarge,
    FieldReadOnly,
    InvalidImage,
    PayloadTooLarge,
    PersonalizationDisabled,
    StepNotFound,
)

PERSONALIZATION_FLAG = "personalization"
AVATAR_FLAG = "profile_avatar"
#: Multipart framing on top of the file itself.
MULTIPART_OVERHEAD = 4_096


class ScopedView(APIView):
    """Authenticated, student-scoped writes with a per-scope throttle (set `throttle_scope`)."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle, ScopedRateThrottle]


class PersonalizationView(ScopedView):
    """Onboarding and last-visit writes sit behind the `personalization` flag. Reading `/me/` never does."""

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not flag_enabled(PERSONALIZATION_FLAG, request.user.id):
            raise PersonalizationDisabled


class MeView(ScopedView):
    """GET the bootstrap (profile, avatar, onboarding summary, course, last visit); PATCH the name; DELETE the account."""

    @property
    def throttle_scope(self):
        # Reads are not part of any write budget (no scope, no throttle).
        return {"PATCH": "profile_write", "DELETE": "account_delete"}.get(self.request.method)

    def get(self, request):
        profile, onboarding = services.ensure_student(request.user)
        bootstrap = selectors.bootstrap(profile, onboarding)
        return tagged_response(request, serializers.bootstrap_dict(bootstrap, request.user))

    def patch(self, request):
        stale = [f for f in serializers.MePatchSerializer.DEPRECATED_FIELDS if f in request.data]
        if stale:
            raise FieldReadOnly(extra={"fields": stale})
        s = serializers.MePatchSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.ensure_student(request.user)
        try:
            services.update_name(request.user.id, s.validated_data["full_name"])
        except InvalidName as exc:
            return Response(
                {"error": {"code": "invalid", "message": str(exc), "details": {"full_name": [str(exc)]}}}, status=400
            )
        profile, onboarding = services.ensure_student(request.user)
        return Response(serializers.bootstrap_dict(selectors.bootstrap(profile, onboarding), request.user))

    def delete(self, request):
        s = serializers.DeleteAccountSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.delete_account(request.user, confirm=s.validated_data["confirm"], now=time.time())
        return Response(status=204)


class ExportView(ScopedView):
    throttle_scope = "account_export"

    def get(self, request):
        return Response(services.export_account(request.user.id))


class OnboardingView(ScopedView):
    """GET the state and the step list."""

    def get_throttles(self):
        return []

    def get(self, request):
        profile, row = services.ensure_student(request.user)
        return Response(serializers.steps_dict(selectors.onboarding_resolution(profile, row)))


class OnboardingStepView(PersonalizationView):
    throttle_scope = "onboarding_write"

    def put(self, request, key):
        handler = registry.get_handler(key)
        if handler is None:
            raise StepNotFound
        services.ensure_student(request.user)
        s = handler.serializer(data=request.data)
        s.is_valid(raise_exception=True)
        resolution = services.save_step(request.user, key, s.validated_data)
        return Response(serializers.steps_dict(resolution))


class OnboardingSkipView(PersonalizationView):
    throttle_scope = "onboarding_write"

    def post(self, request, key):
        services.ensure_student(request.user)
        return Response(serializers.steps_dict(services.skip_step(request.user.id, key)))


class OnboardingCompleteView(PersonalizationView):
    throttle_scope = "onboarding_write"

    def post(self, request):
        services.ensure_student(request.user)
        resolution = services.complete_onboarding(request.user.id)
        # The server's default; the web applies its own precedence (gate, deep link, last visit) after the celebration.
        return Response({"state": serializers.steps_dict(resolution), "destination": "/app"})


class AvatarView(ScopedView):
    """POST uploads the cropped photo (behind `profile_avatar`); DELETE goes back to initials (always allowed)."""

    parser_classes = [MultiPartParser]

    @property
    def throttle_scope(self):
        return "avatar_write" if self.request.method == "POST" else "profile_write"

    def post(self, request):
        if not flag_enabled(AVATAR_FLAG, request.user.id):
            raise AvatarUploadDisabled
        # Refuse oversized bodies before parsing them.
        declared = int(request.META.get("CONTENT_LENGTH") or 0)
        if declared > MAX_INPUT_BYTES + MULTIPART_OVERHEAD:
            raise PayloadTooLarge
        services.ensure_student(request.user)
        upload = request.FILES.get("file")
        if upload is None:
            raise InvalidImage
        if upload.size > MAX_INPUT_BYTES:
            raise PayloadTooLarge
        profile = services.set_upload(request.user.id, upload.read())
        return Response(avatar_summary(profile), status=201)

    def delete(self, request):
        services.ensure_student(request.user)
        return Response(avatar_summary(services.remove_avatar(request.user.id)))


class AvatarPresetView(ScopedView):
    throttle_scope = "profile_write"

    def put(self, request):
        s = serializers.PresetSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.ensure_student(request.user)
        return Response(avatar_summary(services.set_preset(request.user.id, s.validated_data["key"])))


#: A last-visit body is a path and a query string; the token in a beacon adds a JWT. Anything bigger is not ours.
LAST_VISIT_MAX_BODY = 1_024


class LastVisitView(PersonalizationView):
    """
    Remembers the page the student left on. Called when the tab is hidden, usually by `navigator.sendBeacon`, which
    can only send a body: so the token may travel in it (`BeaconBodyAuthentication`), here and nowhere else.
    """

    throttle_scope = "lastvisit_write"
    authentication_classes = [SupabaseJWTAuthentication, BeaconBodyAuthentication]
    parser_classes = [JSONParser, PlainTextJSONParser]

    def initial(self, request, *args, **kwargs):
        # Before anything reads the body.
        declared = request.META.get("CONTENT_LENGTH")
        if not declared or int(declared) > LAST_VISIT_MAX_BODY:
            raise BodyTooLarge
        super().initial(request, *args, **kwargs)

    def post(self, request):
        data = serializers.LastVisitSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.record_visit(request.user.id, data.validated_data["path"], data.validated_data["search"])
        return Response(status=204)

    put = post
