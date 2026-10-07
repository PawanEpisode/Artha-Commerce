"""Thin views for /api/v1/media/: parse, call a service, serialise. The kinds a student may upload come from the registry."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from core.permissions import ParsedAPIView

from . import services
from .serializers import CreateUploadSerializer, attachment_dict


class MediaView(ParsedAPIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]


class UploadCreateView(MediaView):
    throttle_scope = "media_upload"

    def post(self, request):
        d = self.parse(CreateUploadSerializer, request.data).validated_data
        upload = services.create_upload(request.user.id, d["kind"], mime=d["mime"], bytes=d["bytes"])
        return Response(
            {
                "attachment": attachment_dict(upload.attachment),
                "upload": {
                    "url": upload.url,
                    "method": "PUT",
                    "headers": upload.headers,
                    "expires_at": upload.expires_at,
                },
            },
            status=201,
        )


class UploadCompleteView(MediaView):
    throttle_scope = "media_upload"

    def post(self, request, attachment_id):
        return Response({"attachment": attachment_dict(services.complete_upload(request.user.id, attachment_id))})


class AttachmentUrlView(MediaView):
    throttle_scope = "media_read"

    def get(self, request, attachment_id):
        signed = services.signed_url(request.user.id, attachment_id)
        return Response({"url": signed.url, "expires_at": signed.expires_at})
