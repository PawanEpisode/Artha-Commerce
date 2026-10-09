"""
Profiles adapter: the platform role of a staff login, through `modules.profiles.selectors` only. Django admin accounts are not
Supabase users, so a staff user is matched to a profile by e-mail address (D44); the profile's role then gives the recall scopes.
"""

from __future__ import annotations

from modules.profiles import selectors as profiles


def role_of_email(email: str) -> str | None:
    return profiles.role_for_email(email)
