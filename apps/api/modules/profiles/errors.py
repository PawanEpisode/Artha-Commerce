"""Errors of the profiles module. Each class carries the `default_code` the web branches on."""

from core.errors import CodedError, Conflict, FeatureDisabled
from rest_framework import status
from rest_framework.exceptions import APIException, NotFound


class StepMandatory(Conflict):
    default_detail = "This step is required."
    default_code = "step_mandatory"


class OnboardingIncomplete(Conflict):
    default_detail = "Finish the required steps first."
    default_code = "onboarding_incomplete"


class StepNotFound(NotFound):
    default_detail = "That onboarding step does not exist."
    default_code = "not_found"


class FieldReadOnly(CodedError):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "This field can no longer be changed here."
    default_code = "field_read_only"


class ConfirmationRequired(CodedError):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Type DELETE to confirm."
    default_code = "confirmation_required"


class ReauthRequired(CodedError):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "Confirm it is you with a new code first."
    default_code = "reauth_required"


class DeletionIncomplete(APIException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = "We could not finish deleting your account. Try again."
    default_code = "deletion_incomplete"

    def __init__(self, done: list[str], failed: str):
        super().__init__()
        self.extra = {"done": done, "failed": failed}


class PersonalizationDisabled(FeatureDisabled):
    default_detail = "Personalised setup is not available yet."


class UnknownPreset(CodedError):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "That avatar does not exist."
    default_code = "unknown_preset"


class InvalidImage(CodedError):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Use a JPG, PNG or WebP image."
    default_code = "invalid_image"


class ImageTooLarge(CodedError):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "That photo has too many pixels. Choose a smaller one."
    default_code = "image_too_large"


class ImageTooSmall(CodedError):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Choose a photo at least 128 by 128 pixels."
    default_code = "image_too_small"


class PayloadTooLarge(CodedError):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    default_detail = "That photo is too large."
    default_code = "payload_too_large"


class BodyTooLarge(PayloadTooLarge):
    default_detail = "That request is too large."


class StorageUnavailable(CodedError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "We could not save your photo. Try again."
    default_code = "storage_unavailable"


class AvatarUploadDisabled(FeatureDisabled):
    default_detail = "Photo upload is not available yet."


class PathNotRestorable(CodedError):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "That page is not remembered."
    default_code = "path_not_restorable"
