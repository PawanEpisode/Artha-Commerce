"""
Merging concurrent edits (ERD 3.6). Two pure pieces:

`merge3_text(base, mine, theirs)`: a 3-way text merge on character edits. Both sides are diffed against `base` (with
diff-match-patch); edits that touch different parts of the text are both applied, edits that overlap are a conflict. Why not
`patch_apply`: it matches fuzzily, so it can apply a hunk in the wrong place and lose or duplicate text silently. Here a
clean result contains every edit from both sides and a conflict is always reported, never guessed.

`merge_fields(base, mine, theirs)`: field-level compare-and-set for scalar fields (see also `reconcile_fields` below, the whole write). A field is accepted when the stored value
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


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def merge3_stable(base: str, mine: str, theirs: str) -> MergeResult:
    """
    `merge3_text`, but a merge counts as clean only when it is stable: replaying either side's write on the merged text
    changes nothing. Why: a retrying client resends an old write after another device's edit was merged on top. With edits
    that a diff can align two ways (the same characters inserted at the same spot) the replay would insert them twice. In
    those rare cases the student chooses (mine, theirs, both) instead of getting duplicated text.
    """
    result = merge3_text(base, mine, theirs)
    if not result.clean or mine == theirs or base in (mine, theirs):
        return result
    for side in (mine, theirs):
        replay = merge3_text(base, side, result.text)
        if not (replay.clean and replay.text == result.text):
            return MergeResult(theirs, False, 1)
    return result


def reconcile_fields(
    stored: Mapping[str, Any],
    base: Mapping[str, Any],
    incoming: Mapping[str, Any],
    *,
    text_fields: tuple[str, ...] = ("comment",),
    geometry_fields: tuple[str, ...] = ("geometry",),
) -> dict[str, Any]:
    """
    The whole field-level compare-and-set of ERD 3.6 for one write, pure. `stored` is the row now, `base` the values the
    client last saw (only the fields it changed), `incoming` the new values. Returns
    `{"accepted": {field: value}, "overwritten": [field, ...], "conflict": None | {field, mine, theirs, merged}}`.

    Per field, in this order:
    1. stored already equals the new value: accepted (a replay, so a retry is a no-op).
    2. stored equals `base`: nobody else touched it, accepted.
    3. otherwise another device changed it:
       - a text field is 3-way merged (`merge3_text`): a clean merge is accepted; an overlap is the `conflict` (the first
         one; `merged` is the merge with theirs standing). A text field with no `base` cannot be merged, so it conflicts too
         instead of silently replacing text.
       - any other field, geometry included (a move is not mergeable), is last write wins and listed in `overwritten`.
         Without a `base` entry there is nothing to compare, so it is a plain write and not reported.
    When `conflict` is set the service answers 409 and writes nothing (the client parks the entry); `accepted` still
    lists the fields that would have gone through, for the response body.
    """
    if set(text_fields) & set(geometry_fields):
        raise ValueError("a field cannot be both text and geometry")
    accepted: dict[str, Any] = {}
    overwritten: list[str] = []
    conflict: dict[str, Any] | None = None
    for field, new in incoming.items():
        have = stored.get(field)
        if have == new or (field in base and have == base[field]):
            accepted[field] = new
        elif field in text_fields:
            mine, theirs = _text(new), _text(have)
            merged = merge3_stable(_text(base[field]), mine, theirs) if field in base else MergeResult(theirs, False, 1)
            if merged.clean:
                accepted[field] = merged.text
            elif conflict is None:
                conflict = {"field": field, "mine": mine, "theirs": theirs, "merged": merged.text}
        else:
            accepted[field] = new
            if field in base:
                overwritten.append(field)
    return {"accepted": accepted, "overwritten": sorted(overwritten), "conflict": conflict}


def resolve_conflict(resolution: str, mine: str, theirs: str) -> str:
    """The text a parked conflict becomes: `mine`, `theirs`, or `both` (theirs, a `---` rule, then mine). Nothing is lost."""
    if resolution == "mine":
        return mine
    if resolution == "theirs":
        return theirs
    if resolution == "both":
        return both(theirs, mine)
    raise ValueError(f"unknown resolution {resolution!r}")


def resolve_edit_vs_delete(*, stored_deleted: bool, stored_rev: int, base_rev: int, op: str) -> dict[str, Any]:
    """
    Edit versus delete (ERD 3.6: edit wins, nothing is lost). `op` is `edit` or `delete`; returns
    `{"action": apply | restore | noop | keep, "restored": bool}` for the service to carry out:
    - edit on a live row: `apply`; edit on a tombstone: `restore` (clear it, `rev + 1`, tell the client `restored`).
    - delete of a tombstone: `noop` (idempotent).
    - delete of a live row that was edited after the client's `base_rev`: `keep` (the other device's edit wins).
    - delete of a live row nobody touched: `apply`.
    """
    if op == "edit":
        return {"action": "restore" if stored_deleted else "apply", "restored": stored_deleted}
    if op == "delete":
        if stored_deleted:
            return {"action": "noop", "restored": False}
        return {"action": "keep" if stored_rev > base_rev else "apply", "restored": False}
    raise ValueError(f"unknown op {op!r}")
