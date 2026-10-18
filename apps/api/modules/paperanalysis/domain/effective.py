"""
Effective marks and nature classification for F-11.
Reference: ERD 3.5.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def calculate_effective_marks(
    marks: Decimal,
    pick_n: int | None = None,
    of_m: int | None = None,
) -> Decimal:
    """
    Computes effective marks: `round_half_up(marks * pick_n / of_m, 2)` if in a choice group,
    else `marks`.
    """
    if pick_n is not None and of_m is not None:
        if of_m <= 0 or pick_n <= 0 or pick_n > of_m:
            raise ValueError(f"Invalid choice group values: pick_n={pick_n}, of_m={of_m}")
        ratio = Decimal(pick_n) / Decimal(of_m)
        raw = marks * ratio
        return raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return marks


def is_practical_format_or_nature(format: str, nature: str | None = None) -> bool:
    """
    Classifies a question as practical vs theory:
    practical if format == 'practical' or nature in ('practical', 'application'),
    else theory.
    """
    if format == "practical":
        return True
    if nature and nature.lower() in ("practical", "application"):
        return True
    return False


def calculate_choice_group_attemptable(
    pick_n: int,
    of_m: int,
    question_marks: list[Decimal],
) -> Decimal:
    """
    Computes attemptable marks for a choice group:
    pick_n * marks_each if equal, or sum of pick_n largest members if marks differ.
    """
    if not question_marks:
        return Decimal("0.0")
    if pick_n <= 0 or pick_n > len(question_marks):
        return sum(question_marks)

    sorted_marks = sorted(question_marks, reverse=True)
    return sum(sorted_marks[:pick_n])
