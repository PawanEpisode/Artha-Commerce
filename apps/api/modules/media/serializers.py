from rest_framework import serializers

from .models import Attachment
from .registry import kind_names


class CreateUploadSerializer(serializers.Serializer):
    kind = serializers.CharField(max_length=32)
    mime = serializers.CharField(max_length=100)
    bytes = serializers.IntegerField(min_value=1)

    def validate_kind(self, value):
        if value not in kind_names():
            raise serializers.ValidationError("Unknown kind.")
        return value


def attachment_dict(a: Attachment) -> dict:
    return {"id": str(a.id), "kind": a.kind, "status": a.status, "bytes": a.bytes, "mime": a.mime}
