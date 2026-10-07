from rest_framework import status

from core.errors import CodedError, Conflict


class UnsupportedType(CodedError):
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    default_detail = "That file type is not allowed."
    default_code = "unsupported_type"


class FileTooLarge(CodedError):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    default_detail = "That file is too large."
    default_code = "file_too_large"


class UploadMissing(Conflict):
    default_detail = "The file has not arrived in storage yet. Upload it, then confirm."
    default_code = "upload_missing"


class NotReady(Conflict):
    default_detail = "That file is not ready to use yet."
    default_code = "attachment_not_ready"


class StorageUnavailable(CodedError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "We could not reach file storage. Try again."
    default_code = "storage_unavailable"
