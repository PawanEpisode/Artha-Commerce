"""
Merging concurrent edits (ERD 3.6). Two pure pieces:

`merge3_text(base, mine, theirs)`: a 3-way text merge on character edits. Both sides are diffed against `base` (with
diff-match-patch); edits that touch different parts of the text are both applied, edits that overlap are a conflict. Why not
`patch_apply`: it matches fuzzily, so it can apply a hunk in the wrong place and lose or duplicate text silently. Here a
clean result contains every edit from both sides and a conflict is always reported, never guessed.

`merge_fields(base, mine, theirs)`: field-level compare-and-set for scalar fields. A field is accepted when the stored value
still equals the value the client saw (`base`) or already equals the new one; otherwise the later write wins and the field
is reported as overwritten, so the client can say so quietly.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from diff_match_patch import diff_match_patch

BOTH_SEPARATOR = "\n\n---\n\n"


@dataclass(frozen=True)
class Edit:
    start: int  # in `base`
    end: int
    text: str  # what replaces base[start:end]

    def touches(self, other: Edit) -> bool:
        """Overlap or adjacency (inclusive): neighbouring edits are treated as one disagreement, the safe reading."""
        return self.start <= other.end and other.start <= self.end


@dataclass(frozen=True)
class MergeResult:
    text: str  # clean: the merge. conflict: the merge with every conflicting region resolved to `theirs`
    clean: bool
    conflicts: int = 0


def _dmp() -> diff_match_patch:
    d = diff_match_patch()
    d.Diff_Timeout = 1.0  # a timeout still returns a valid diff, only a coarser one
    return d


def edits_between(base: str, other: str) -> list[Edit]:
    """The edits that turn `base` into `other`, in order, with a delete and the insert next to it merged into one."""
    d = _dmp()
    diffs = d.diff_main(base, other)
    d.diff_cleanupSemantic(diffs)
    edits: list[Edit] = []
    pos = 0
    for op, data in diffs:
        if op == d.DIFF_EQUAL:
            pos += len(data)
        elif op == d.DIFF_DELETE:
            edits.append(Edit(pos, pos + len(data), ""))
            pos += len(data)
        else:
            last = edits[-1] if edits else None
            if last and last.end == pos and last.text == "":  # insert right after a delete: one replacement
                edits[-1] = Edit(last.start, last.end, data)
            else:
                edits.append(Edit(pos, pos, data))
    return edits


def _apply(base: str, edits: list[Edit]) -> str:
    out, pos = [], 0
    for e in sorted(edits, key=lambda e: (e.start, e.end)):
        out.append(base[pos : e.start])
        out.append(e.text)
        pos = e.end
    out.append(base[pos:])
    return "".join(out)


def merge3_text(base: str, mine: str, theirs: str) -> MergeResult:
    """Merge `mine` and `theirs`, both derived from `base`. Identical edits count once. See the module docstring."""
    if mine == theirs or base == theirs:
        return MergeResult(mine, True)
    if base == mine:
        return MergeResult(theirs, True)
    mine_edits, their_edits = edits_between(base, mine), edits_between(base, theirs)
    chosen: list[Edit] = list(their_edits)  # theirs always stands; mine is added where it does not touch theirs
    conflicts = 0
    for m in mine_edits:
        clashing = [t for t in their_edits if m.touches(t)]
        if not clashing:
            chosen.append(m)
        elif not all(t == m for t in clashing):
            conflicts += 1
    return MergeResult(_apply(base, chosen), conflicts == 0, conflicts)


def both(theirs: str, mine: str) -> str:
    """Keep both: theirs, a rule, then mine. Nothing is lost whatever the overlap."""
    if not mine.strip():
        return theirs
    if not theirs.strip():
        return mine
    return f"{theirs}{BOTH_SEPARATOR}{mine}"


@dataclass(frozen=True)
class FieldMerge:
    values: dict[str, Any]  # fields to write
    overwritten: list[str]  # fields where another device's newer value was replaced


def merge_fields(base: Mapping[str, Any], mine: Mapping[str, Any], theirs: Mapping[str, Any]) -> FieldMerge:
    """
    `mine` is what the client wants to write, `base` the values it last saw, `theirs` what is stored now. A field with no
    `base` entry is a plain write (nothing to compare), so it never counts as overwritten.
    """
    values, overwritten = {}, []
    for field, value in mine.items():
        values[field] = value
        if field in base and theirs.get(field) != base[field] and theirs.get(field) != value:
            overwritten.append(field)
    return FieldMerge(values, sorted(overwritten))
