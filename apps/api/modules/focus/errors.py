"""Focus reuses the tracking error types (same JSON shape); only the feature-flag message differs."""

from modules.tracking.errors import (  # noqa: F401 - re-exported for the rest of the module
    ConflictError,
    FeatureDisabled,
    InvalidInput,
    NotFoundError,
    TrackingError,
    to_api_exception,
)


class FocusFeatureDisabled(FeatureDisabled):
    default_detail = "The focus timer is not available yet."
