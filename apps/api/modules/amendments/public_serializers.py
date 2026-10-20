"""
Allow-list serializers for public amendment endpoints (ERD Section 8, Security).
These serializers strictly control what fields leave the public API.
Under NO circumstances may evidence_quote, anchor, or internal ingestion provenance be leaked.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

FORBIDDEN_FIELDS = {
    "evidence_quote",
    "evidence_hash",
    "anchor",
    "ingestion_item_id",
    "ingestion_item_version_id",
    "provenance_snapshot_id",
    "reviewed_by",
    "released_by",
    "checks",
    "extraction",
    "diff_summary",
}


def assert_no_leaks(data: Any) -> None:
    """
    Recursively scans any serialized dict/list to ensure no forbidden field is present.
    """
    if isinstance(data, dict):
        for k, v in data.items():
            if k in FORBIDDEN_FIELDS:
                raise ValueError(f"CRITICAL PRIVACY LEAK: Forbidden field '{k}' found in public response.")
            assert_no_leaks(v)
    elif isinstance(data, list):
        for item in data:
            assert_no_leaks(item)


class PublicDocumentSummarySerializer(serializers.Serializer):
    slug = serializers.CharField()
    title = serializers.CharField()
    issuer_label = serializers.CharField()
    official_url = serializers.URLField()
    issued_on = serializers.CharField(allow_null=True)


class PublicTermSerializer(serializers.Serializer):
    term_code = serializers.CharField()
    applicability = serializers.CharField()
    cutoff_date = serializers.CharField(allow_null=True)
    cutoff_note = serializers.CharField(required=False, default="")


class PublicChapterMappingSerializer(serializers.Serializer):
    subject_key = serializers.CharField()
    chapter_key = serializers.CharField()
    is_primary = serializers.BooleanField()


class PublicCardDetailSerializer(serializers.Serializer):
    public_id = serializers.CharField()
    card_key = serializers.CharField()
    tombstone = serializers.BooleanField(default=False)
    status = serializers.CharField()
    message = serializers.CharField(required=False)
    change_type = serializers.CharField(required=False)
    law_label = serializers.CharField(required=False)
    law_key = serializers.CharField(required=False)
    provision_label = serializers.CharField(required=False)
    title = serializers.CharField(required=False)
    summary_old = serializers.CharField(allow_null=True, required=False)
    summary_new = serializers.CharField(allow_null=True, required=False)
    effective_text = serializers.CharField(required=False)
    effective_from_term_code = serializers.CharField(allow_null=True, required=False)
    source_page = serializers.IntegerField(required=False)
    materiality = serializers.CharField(required=False)
    document = PublicDocumentSummarySerializer(required=False)
    terms = serializers.ListField(child=PublicTermSerializer(), required=False)
    chapters = serializers.ListField(child=PublicChapterMappingSerializer(), required=False)
    notice = serializers.CharField(required=False)

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        assert_no_leaks(ret)
        return ret
