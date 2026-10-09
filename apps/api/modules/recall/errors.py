"""Errors of the recall module. Shared ones come from `core.errors`; nothing is copied per module."""

from rest_framework import status

from core.errors import CodedError, Conflict, FeatureDisabled, QuotaExceeded

__all__ = [
    "BadCursor",
    "BulkTooLarge",
    "CardDeleted",
    "CodedError",
    "Conflict",
    "DuplicateCard",
    "EditConflict",
    "FeatureDisabled",
    "BatchTooLarge",
    "InvalidFields",
    "InvalidSetting",
    "NotUndoable",
    "QuotaExceeded",
    "RecallFeatureDisabled",
    "UndoExpired",
    "UnknownChapter",
    "UnknownKind",
]


class RecallFeatureDisabled(FeatureDisabled):
    default_detail = "Recall is not available yet."


class InvalidFields(CodedError):
    """422: a field breaks a rule of its kind or of the `card` Markdown profile. `details` `{errors: [{field, code, message}]}`."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "This card cannot be saved as it is."
    default_code = "invalid_fields"


class UnknownKind(CodedError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "That card kind does not exist."
    default_code = "unknown_kind"


class UnknownChapter(CodedError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "That chapter is not in your syllabus."
    default_code = "unknown_chapter"


class BulkTooLarge(CodedError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "A bulk change takes at most 200 cards."
    default_code = "bulk_too_large"


class DuplicateCard(Conflict):
    """409 with `details` `{card_id, item_id}` of the card she already has; send `force` to keep both."""

    default_detail = "You already have a card with this text."
    default_code = "duplicate_card"


class EditConflict(Conflict):
    """409 with `details` `{server_fields, rev}`: the card changed elsewhere. Nothing was written."""

    default_detail = "This card was changed somewhere else."
    default_code = "edit_conflict"


class CardDeleted(CodedError):
    status_code = status.HTTP_410_GONE
    default_detail = "This card was deleted."
    default_code = "card_deleted"


class NotUndoable(Conflict):
    """409: only the last 10 reviews of a session, received less than 30 minutes ago, can be undone (once)."""

    default_detail = "That review can no longer be undone."
    default_code = "not_undoable"


class BatchTooLarge(CodedError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "A batch takes at most 100 reviews."
    default_code = "batch_too_large"


class InvalidSetting(CodedError):
    """422 with `details` `{errors: [{field, code, message}]}`."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "That setting is not valid."
    default_code = "invalid_setting"


class UndoExpired(CodedError):
    status_code = status.HTTP_410_GONE
    default_detail = "It is too late to undo that."
    default_code = "undo_expired"


class BadCursor(CodedError):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "That cursor is not valid."
    default_code = "bad_cursor"
