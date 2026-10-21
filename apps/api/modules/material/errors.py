"""
Exceptions for F-12 Institute Study Material (MAT).
"""

from rest_framework import status
from rest_framework.exceptions import APIException


class MaterialError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "A study material error occurred."
    default_code = "material_error"


class FeatureDisabled(MaterialError):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Study material is currently disabled."
    default_code = "feature_disabled"


class RightsBlocked(MaterialError):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Rights not available for this operation."
    default_code = "rights_blocked"


class StaleEditionError(MaterialError):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Edition was modified concurrently or is stale."
    default_code = "stale_edition"


class MappingIncompleteError(MaterialError):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "All units and items must have confirmed chapter mappings before publishing."
    default_code = "mapping_incomplete"


class WorkNotFound(MaterialError):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Study material work not found."
    default_code = "work_not_found"


class ItemNotFound(MaterialError):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Study material item not found."
    default_code = "item_not_found"


class EditionNotFound(MaterialError):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Edition not found."
    default_code = "edition_not_found"


class QuotaExceeded(MaterialError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "Quota exceeded for private works or custom providers."
    default_code = "quota_exceeded"


class InvalidTermRange(MaterialError):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Invalid term range for edition."
    default_code = "invalid_term_range"


class NoHostedItems(MaterialError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "No hosted items available for practice in this chapter."
    default_code = "no_hosted_items"


class QuestionBankDisabled(MaterialError):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Question bank feature is disabled."
    default_code = "question_bank_disabled"
