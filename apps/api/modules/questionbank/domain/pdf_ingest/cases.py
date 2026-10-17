"""
Case-scenario MCQs: a paper prints one scenario (often with a data table) and then several questions that all refer to it.
The Institute's transcription repeats the scenario in each question's stem (or, worse, only in the first). The importer shows
one question at a time, so every question of the group must carry the scenario, and the student must be told which
questions share it. `format_case_groups` finds each group (consecutive MCQs of one question whose stems open with the same
text) and rewrites every stem as

    > **Case scenario** · questions (xi) to (xv)
    >
    > <the scenario, with its tables>

    <this question's own text>

Pure; operates on the leaf dicts of `pyq.build_paper`.
"""

from __future__ import annotations

import re
from typing import Any

from .text import fix_pipeless_tables

MIN_SHARED_CHARS = 120
_LABEL = re.compile(
    r"^\s*(\*\*)?(case\s+(scenario|study)|scenario|question\s+nos?\.?)[^\n:*]*?(\*\*)?\s*:(\*\*)?\s*", re.I
)


def _lines(text: str) -> list[str]:
    return [ln.rstrip() for ln in text.strip().split("\n")]


def shared_prefix(stems: list[str]) -> str:
    """The leading lines that every stem has in common (line-aligned), '' when none."""
    split = [_lines(s) for s in stems]
    common: list[str] = []
    for lines in zip(*split, strict=False):
        if all(ln == lines[0] for ln in lines):
            common.append(lines[0])
        else:
            break
    if any(len(x) <= len(common) for x in split):
        return ""
    # every stem must keep at least one non-blank line of its own
    while common and any(not "".join(x[len(common) :]).strip() for x in split):
        common.pop()
    while common and not common[-1].strip():
        common.pop()
    return "\n".join(common)


def _tail(number_label: str) -> str:
    return re.sub(r"^\d+", "", number_label) or number_label


def quote(md: str) -> str:
    return "\n".join(("> " + line) if line.strip() else ">" for line in md.split("\n"))


def format_case(case_md: str, first: str, last: str) -> str:
    body = fix_pipeless_tables(_LABEL.sub("", case_md.strip(), count=1)).strip()
    head = f"**Case scenario** · questions {first} to {last}"
    return quote(head + "\n\n" + body)


def groups(leaves: list[dict[str, Any]]) -> list[tuple[list[dict[str, Any]], str]]:
    """Consecutive MCQ leaves of one parent that share an opening of at least MIN_SHARED_CHARS."""
    found: list[tuple[list[dict[str, Any]], str]] = []
    i = 0
    while i < len(leaves):
        if not leaves[i]["kind"].startswith("mcq"):
            i += 1
            continue
        best: tuple[int, str] = (i, "")
        j = i + 1
        while (
            j < len(leaves)
            and leaves[j]["kind"].startswith("mcq")
            and leaves[j].get("parent_ref") == leaves[i].get("parent_ref")
        ):
            prefix = shared_prefix([x["stem_md"] for x in leaves[i : j + 1]])
            if len(prefix) < MIN_SHARED_CHARS:
                break
            best = (j, prefix)
            j += 1
        if best[0] > i:
            found.append((leaves[i : best[0] + 1], best[1]))
            i = best[0] + 1
        else:
            i += 1
    return found


def format_case_groups(leaves: list[dict[str, Any]]) -> list[str]:
    """Rewrites the stems in place; returns the labels of the leaves that were grouped."""
    by_parent: dict[Any, list[dict[str, Any]]] = {}
    for leaf in leaves:
        by_parent.setdefault(leaf.get("parent_ref") or leaf["ref"], []).append(leaf)
    touched: list[str] = []
    for siblings in by_parent.values():
        for members, prefix in groups(siblings):
            block = format_case(prefix, _tail(members[0]["number_label"]), _tail(members[-1]["number_label"]))
            for leaf in members:
                rest = leaf["stem_md"].strip()[len(prefix.strip()) :].strip()
                leaf["stem_md"] = block + "\n\n" + rest
                leaf["case_group"] = f"{members[0]['number_label']}-{members[-1]['number_label']}"
                touched.append(leaf["number_label"])
    return touched
