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


# --- R2: documents ---------------------------------------------------------------------------------------------------------
class TooManyPages(CodedError):
    """422 `too_many_pages`, details `{limit}`: more pages than the plan allows, refused before any bytes move."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "That PDF has more pages than your plan allows."
    default_code = "too_many_pages"


class DocumentConflict(Conflict):
    """409 `document_conflict`: the document's metadata changed elsewhere. The view adds `details.theirs` (the stored Document)."""

    default_detail = "This document was changed somewhere else."
    default_code = "document_conflict"


class RangesOverlap(Conflict):
    default_detail = "Two page ranges cover the same page."
    default_code = "ranges_overlap"


class InvalidRange(CodedError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "That page range is not valid."
    default_code = "invalid_range"


class NotUploaded(Conflict):
    default_detail = "The file has not arrived in storage yet. Upload it, then confirm."
    default_code = "not_uploaded"


class NotAbortable(Conflict):
    default_detail = "This upload can no longer be cancelled."
    default_code = "not_abortable"


# --- R2: annotations and recall ---------------------------------------------------------------------------------------------
class AnnotationConflict(Conflict):
    """
    409 `annotation_conflict`: the mark's comment was edited elsewhere and the two edits overlap. Nothing was written. Carries
    the stored row (`theirs`) and what the client tried to write (`mine`); the view turns them into the response `details`
    (`{mine, theirs, device_label, theirs_updated_at}`) because the Annotation shape is built above the services.
    """

    default_detail = "This mark was changed somewhere else."
    default_code = "annotation_conflict"

    def __init__(self, theirs, mine: dict):
        super().__init__()
        self.theirs, self.mine = theirs, mine


class InvalidGeometry(CodedError):
    """422 `invalid_geometry`, details `{errors: [{code, message}]}` from `domain.geometry`."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "That shape is not valid for this kind of mark."
    default_code = "invalid_geometry"


class InvalidMark(CodedError):
    """422: a field of a mark breaks a rule the serializer cannot see (a page outside the document, an unknown kind change)."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "That mark cannot be saved as it is."
    default_code = "invalid_mark"


class BatchTooLarge(CodedError):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    default_detail = "Send at most 100 changes at a time."
    default_code = "batch_too_large"


class RecallUnavailable(CodedError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Flashcards are not available yet."
    default_code = "recall_unavailable"


class NoText(CodedError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "This mark has no text to make a card from."
    default_code = "no_text"


class NotTrashable(Conflict):
    default_detail = "Cancel this upload instead of deleting it."
    default_code = "not_trashable"
