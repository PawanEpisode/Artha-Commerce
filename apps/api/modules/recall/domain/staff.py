"""Who may do what in the recall admin (D44). Pure: a role (or superuser) in, a set of scopes out."""

from __future__ import annotations

AUTHOR = "recall.deck.author"
PUBLISH = "recall.deck.publish"

#: `profiles.role` to scopes. A student has none. An editor writes items and draft versions; an admin also publishes.
SCOPES_BY_ROLE: dict[str, frozenset[str]] = {
    "student": frozenset(),
    "editor": frozenset({AUTHOR}),
    "admin": frozenset({AUTHOR, PUBLISH}),
}


def scopes_for(role: str | None, *, is_superuser: bool = False) -> frozenset[str]:
    if is_superuser:
        return frozenset({AUTHOR, PUBLISH})
    return SCOPES_BY_ROLE.get(role or "", frozenset())
