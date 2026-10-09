"""The recall flag. Fails closed: recall is off for everyone until PostHog says it is on for the student."""

from core.permissions import flag_required

from .errors import RecallFeatureDisabled

RECALL_FLAG = "recall_system"
RecallFlagEnabled = flag_required(RECALL_FLAG, RecallFeatureDisabled, strict=True)
