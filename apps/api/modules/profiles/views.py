from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import ProfileSerializer
from .services import get_or_create_profile, update_profile


class MeView(APIView):
    """GET/PATCH /api/v1/me/: the signed-in student's profile."""

    def get(self, request):
        profile = get_or_create_profile(request.user)
        return Response(ProfileSerializer(profile).data)

    def patch(self, request):
        profile = get_or_create_profile(request.user)
        serializer = ProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        profile = update_profile(profile, serializer.validated_data)
        return Response(ProfileSerializer(profile).data)
