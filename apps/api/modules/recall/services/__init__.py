"""Write paths of the recall module. Views call these; they never call views. Services are added wave by wave."""

from . import (
    cards,
    catchup,
    decks,
    engine,
    erasure,
    log_guard,
    preferences,
    quota,
    reports,
    reviews,
    rollups,
    sessions,
    student,
    subscriptions,
)

__all__ = [
    "cards",
    "catchup",
    "decks",
    "engine",
    "erasure",
    "log_guard",
    "preferences",
    "quota",
    "reports",
    "reviews",
    "rollups",
    "sessions",
    "student",
    "subscriptions",
]
