"""One-click unsubscribe (X-01.1 W3.5): a signed link switches one category's email off, with no login. Idempotent."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from django.conf import settings

from ..domain import unsubscribe as tokens
from ..domain.catalogue import UnknownSwitch, category_label, validate_switch
from ..domain.enums import Channel
from ..errors import InvalidUnsubscribeLink
from . import preferences


@dataclass(frozen=True)
class Target:
    user_id: uuid.UUID
    category: str
    label: str


def read(token: str) -> Target:
    """Who and what a link is for. Raises `InvalidUnsubscribeLink` for anything that is not a link we signed."""
    parsed = tokens.read_token(settings.SECRET_KEY, token or "")
    if parsed is None:
        raise InvalidUnsubscribeLink
    raw_user, category = parsed
    try:
        user_id = uuid.UUID(raw_user)
        validate_switch(category, Channel.EMAIL.value)
    except (ValueError, UnknownSwitch):
        raise InvalidUnsubscribeLink from None
    return Target(user_id, category, category_label(category))


def unsubscribe(token: str) -> Target:
    target = read(token)
    preferences.set_preferences(target.user_id, [(target.category, Channel.EMAIL.value, False)])
    return target
