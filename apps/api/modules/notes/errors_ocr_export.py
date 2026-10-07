"""Errors of OCR and export requests (contract R2). `details` carry numbers and keys only, never text of the student's."""

from rest_framework import status

from core.errors import CodedError, Conflict


class Locked(Conflict):
    default_detail = "This file is locked. Open it with its password first."
    default_code = "locked"


class NotReady(Conflict):
    default_detail = "This file is still being prepared."
    default_code = "not_ready"


class NotScannedOrNoPages(CodedError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "There are no pages here that need OCR."
    default_code = "not_scanned_or_no_pages"


class OcrNotAllowed(CodedError):
    """The file marks its text as not copyable (PRD 5.5), so it is not read by OCR either."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "This file does not allow its text to be copied, so OCR is not available."
    default_code = "ocr_not_allowed"


class InvalidPages(CodedError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "That page selection is not valid for this file."
    default_code = "invalid_pages"


class InvalidOptions(CodedError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "Those export options are not valid."
    default_code = "invalid_options"


class ExportNotAllowed(CodedError):
    """`details` `{reason: "restricted" | "locked" | "not_ready"}`."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "This file cannot be exported."
    default_code = "export_not_allowed"
