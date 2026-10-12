"""The recall flag. Fails closed: recall is off for everyone until PostHog says it is on for the student."""

from core.permissions import flag_required

from .errors import RecallAiFeatureDisabled, RecallFeatureDisabled

RECALL_FLAG = "recall_system"
RecallFlagEnabled = flag_required(RECALL_FLAG, RecallFeatureDisabled, strict=True)

RECALL_AI_FLAG = "recall_ai"
RecallAiFlagEnabled = flag_required(
    RECALL_AI_FLAG, RecallAiFeatureDisabled, strict=True
)  # costs money, sends text to Google
