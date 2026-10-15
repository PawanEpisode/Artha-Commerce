"""
Numeric parsing for Indian accounting and finance inputs (F-06 ERD 3.5).
Mirrored in TypeScript with a parity test.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation


def parse_indian_number(text: str) -> Decimal | None:
    """
    Parses an Indian or international formatted number string into Decimal.

    Rules:
    - Removes spaces, Rs, Rs., INR, ₹.
    - Accepts Indian grouping (e.g. 1,25,000) and international grouping (e.g. 125,000).
    - Parentheses (500) and leading '-' mean negative.
    - Trailing '%' is dropped.
    - Words like lakh, crore, million, billion are not accepted.
    - More than 6 decimals rejected.
    - Returns None for anything else (invalid).
    """
    if not text or not isinstance(text, str):
        return None

    s = text.strip()
    if not s:
        return None

    # Reject words like lakh, crore, million, billion, etc.
    if re.search(r"\b(lakh|crore|million|billion|thousand|k)\b", s, re.IGNORECASE):
        return None

    # Check parenthesis negative: (500)
    is_paren_negative = False
    if s.startswith("(") and s.endswith(")"):
        is_paren_negative = True
        s = s[1:-1].strip()

    # Drop currency tokens at start or end
    s = re.sub(r"^(?:₹|inr|rs\.?)\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*(?:₹|inr|rs\.?)$", "", s, flags=re.IGNORECASE)

    # Drop trailing %
    s = re.sub(r"\s*%$", "", s)

    # Strip all remaining whitespace
    s = s.replace(" ", "")
    if not s:
        return None

    # Sign handling
    is_minus = False
    if s.startswith("-"):
        if is_paren_negative:
            # Cannot have both ( -500 )
            return None
        is_minus = True
        s = s[1:]
    elif s.startswith("+"):
        if is_paren_negative:
            return None
        s = s[1:]

    if is_paren_negative:
        is_minus = True

    if not s:
        return None

    # Split into integer and decimal components
    parts = s.split(".")
    if len(parts) > 2:
        return None

    integer_part = parts[0]
    decimal_part = parts[1] if len(parts) == 2 else None

    if decimal_part is not None:
        if len(decimal_part) > 6:
            return None
        if not re.fullmatch(r"\d+", decimal_part):
            return None

    # Check grouping in integer part
    if integer_part:
        if "," in integer_part:
            # Indian grouping: e.g. 1,25,000 or 1,25,00,000
            # International grouping: e.g. 125,000 or 1,125,000
            is_indian = bool(re.fullmatch(r"\d{1,2}(,\d{2})*,\d{3}", integer_part))
            is_intl = bool(re.fullmatch(r"\d{1,3}(,\d{3})+", integer_part))
            if not (is_indian or is_intl):
                return None
            integer_clean = integer_part.replace(",", "")
        else:
            if not re.fullmatch(r"\d+", integer_part):
                return None
            integer_clean = integer_part
    else:
        if decimal_part is None:
            return None
        integer_clean = "0"

    clean_str = ("-" if is_minus else "") + integer_clean + (f".{decimal_part}" if decimal_part is not None else "")

    try:
        val = Decimal(clean_str)
        if val == 0:
            return Decimal("0")
        return val
    except InvalidOperation:
        return None
