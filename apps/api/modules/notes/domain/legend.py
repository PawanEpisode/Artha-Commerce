"""The colour legend (ERD 2.11): five fixed colour keys, names chosen by the student. Pure validation, no database."""

from __future__ import annotations

COLOR_KEYS = ("y", "g", "b", "p", "o")
DEFAULT_LEGEND = {"y": "Important", "g": "Formula", "b": "Section or rule", "p": "Doubt", "o": "Example"}
MAX_NAME = 24


def default_legend() -> dict[str, str]:
    """A fresh copy per row (a model default must be a named function so migrations can refer to it)."""
    return dict(DEFAULT_LEGEND)


def legend_problems(legend: object) -> dict[str, str]:
    """Field to message for everything wrong with a legend; empty means valid. Names are 1 to 24 characters, unique."""
    if not isinstance(legend, dict):
        return {"color_legend": "Must be an object of colour keys to names."}
    problems: dict[str, str] = {}
    unknown = sorted(set(legend) - set(COLOR_KEYS))
    missing = [k for k in COLOR_KEYS if k not in legend]
    if unknown or missing:
        problems["color_legend"] = f"Use exactly the keys {', '.join(COLOR_KEYS)}."
        return problems
    seen: dict[str, str] = {}
    for key in COLOR_KEYS:
        name = legend[key]
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= MAX_NAME:
            problems[f"color_legend.{key}"] = f"Names are 1 to {MAX_NAME} characters."
            continue
        folded = " ".join(name.split()).casefold()
        if folded in seen:
            problems[f"color_legend.{key}"] = f"Already used for {seen[folded]}."
        seen[folded] = key
    return problems


def cleaned_legend(legend: dict[str, str]) -> dict[str, str]:
    return {key: " ".join(legend[key].split()) for key in COLOR_KEYS}
