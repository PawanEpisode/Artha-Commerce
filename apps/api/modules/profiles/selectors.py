"""Read-only queries. No side effects."""

from .models import Profile


def get_profile(user_id: str) -> Profile | None:
    return Profile.objects.filter(pk=user_id).first()
