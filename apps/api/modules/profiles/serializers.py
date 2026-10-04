from rest_framework import serializers

from .models import Profile


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ["id", "email", "full_name", "avatar_url", "course", "level", "exam_date", "created_at", "updated_at"]
        read_only_fields = ["id", "email", "created_at", "updated_at"]
