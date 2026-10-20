class AmendmentError(Exception):
    """Base exception for amendments module."""

    pass


class RevisionNotOpenError(AmendmentError):
    """Raised when an action requires an open (staged/in_review) revision."""

    pass


class OpenRevisionExistsError(AmendmentError):
    """Raised when attempting to create a new revision while an open one exists."""

    pass


class ReleaseChecklistFailedError(AmendmentError):
    """Raised when release validation fails."""

    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


class RevisionNotLiveError(AmendmentError):
    """Raised when an operation requires a live revision."""

    pass


class ChangeNotFoundError(AmendmentError):
    """Raised when a change card with given identifier is not found."""

    pass
