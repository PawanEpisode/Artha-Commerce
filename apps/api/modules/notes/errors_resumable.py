"""Errors of resumable upload (flag `notes_ai`)."""

from rest_framework import status

from core.errors import CodedError, Conflict


class ResumableUnavailable(CodedError):
    """503 `resumable_unavailable`: this deployment has no S3 credentials, so uploads are a single PUT."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Resumable upload is not available."
    default_code = "resumable_unavailable"


class NotResumable(Conflict):
    """409 `not_resumable`: only a reserved upload that has not expired can be sent in parts."""

    default_detail = "This upload is not waiting for its file."
    default_code = "not_resumable"


class PartsIncomplete(CodedError):
    """422 `parts_incomplete`: the list of parts does not cover the whole file."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "Some parts of the file have not been sent."
    default_code = "parts_incomplete"
