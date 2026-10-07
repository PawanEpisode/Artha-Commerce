"""Small helpers to turn model rows into JSON-safe dicts (account export, admin tooling)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.db.models import Model


def json_value(value: Any) -> Any:
    """A JSON-safe copy of one column value: dates become ISO strings, UUIDs and decimals become strings."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (uuid.UUID, Decimal)):
        return str(value)
    return value


def row_to_dict(obj: Model, *, exclude: frozenset[str] = frozenset()) -> dict[str, Any]:
    """Every concrete column of `obj` by its attribute name (`user_id`, not `user`), JSON-safe. Search vectors never leave."""
    return {
        f.attname: json_value(getattr(obj, f.attname))
        for f in obj._meta.concrete_fields
        if f.attname not in exclude and f.get_internal_type() != "SearchVectorField"
    }
