"""Errors of the notes module. All carry a machine-readable `code` and optional `details` (see `core.errors`)."""

from rest_framework import status

from core.errors import CodedError, Conflict, FeatureDisabled


class NotesFeatureDisabled(FeatureDisabled):
    default_detail = "Notes are not available yet."


class QuotaExceeded(CodedError):
    """429 with `details` `{kind, used, limit, plan}`. Quotas are database facts; a throttle is only politeness."""

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "You have reached a limit of your plan."
    default_code = "quota_exceeded"


class InvalidBody(CodedError):
    """422: the Markdown breaks a rule of the `note` profile. `details` `{errors: [{code, message, line}]}`."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "This note cannot be saved as it is."
    default_code = "invalid_body"


class UnknownChapter(CodedError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "That chapter is not in your syllabus."
    default_code = "unknown_chapter"


class UnknownTag(CodedError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "One of those tags does not exist."
    default_code = "unknown_tag"


class TagExists(Conflict):
    default_detail = "You already have a tag with that name."
    default_code = "tag_exists"


class NoteConflict(Conflict):
    """
    409: the note changed elsewhere in a way that cannot be merged. `details` `{theirs, mine, merged}`: the stored note,
    what the client tried to write, and a best-effort merge (stored conflicts resolved to theirs) or null. Nothing was written.
    """

    default_detail = "This note was changed somewhere else."
    default_code = "note_conflict"


class BadCursor(CodedError):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "That cursor is not valid."
    default_code = "bad_cursor"
