"""
Property tests for the field-level compare-and-set (ERD 3.6). Two devices start from the same stored state and each makes one
edit; the server replays any ordered subset of them (with repeats, as a retrying client does). Whatever the order:
nothing raises, text both sides left alone survives, a replay changes nothing, and a resolved conflict converges.
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from modules.notes.domain import merge

ALPHABET = "abcdefgh \n"
texts = st.text(alphabet=ALPHABET, min_size=0, max_size=40)


@st.composite
def edits(draw, base: str):
    """A replacement of base[start:end] by new text: covers insertions (start == end), deletions and rewrites."""
    start = draw(st.integers(0, len(base)))
    end = draw(st.integers(start, len(base)))
    return start, end, draw(st.text(alphabet="XYZ12 ", min_size=0, max_size=6))


@st.composite
def scenarios(draw):
    """A stored text and the edits two devices make to it. (One composite, not `st.data()`: it shrinks reliably.)"""
    base = draw(texts)
    return base, draw(edits(base)), draw(edits(base))


def apply(base: str, edit: tuple[int, int, str]) -> str:
    start, end, new = edit
    return base[:start] + new + base[end:]


def is_subsequence(small: str, big: str) -> bool:
    it = iter(big)
    return all(ch in it for ch in small)


def survivors(base: str, spans: list[tuple[int, int, str]]) -> str:
    """The characters of `base` that neither device touched."""
    touched = set()
    for start, end, _ in spans:
        touched.update(range(start, end))
    return "".join(ch for i, ch in enumerate(base) if i not in touched)


def scenario(base, edit_a, edit_b):
    state = {"comment": base, "color": "y", "geometry": {"rect": [0.1, 0.1, 0.2, 0.2]}}
    seen = dict(state)
    ops = {
        "A": {"comment": apply(base, edit_a), "color": "g"},
        "B": {"comment": apply(base, edit_b), "geometry": {"rect": [0.3, 0.3, 0.2, 0.2]}},
    }
    return state, seen, ops


@settings(max_examples=300, deadline=None)
@given(scenarios(), st.lists(st.sampled_from("AB"), max_size=5))
def test_any_ordered_subset_of_two_devices_never_raises_and_keeps_the_agreed_text(case, order):
    base, edit_a, edit_b = case
    stored, seen, ops = scenario(base, edit_a, edit_b)
    applied = []
    for name in order:
        result = merge.reconcile_fields(stored, seen, ops[name])
        if result["conflict"] is None:
            stored.update(result["accepted"])
            applied.append(edit_a if name == "A" else edit_b)
    assert is_subsequence(survivors(base, applied), stored["comment"])
    assert {"A", "B"} <= set(order) or stored["geometry"] in (seen["geometry"], ops["B"]["geometry"])


@settings(max_examples=300, deadline=None)
@given(scenarios())
def test_two_insertions_both_survive_or_conflict_and_both_keeps_everything(case):
    base, (i, *_), (j, *_) = case
    stored, seen, ops = scenario(base, (i, i, "<A>"), (j, j, "<B>"))
    first = merge.reconcile_fields(stored, seen, ops["A"])
    stored.update(first["accepted"])
    second = merge.reconcile_fields(stored, seen, ops["B"])
    if second["conflict"] is None:
        text = second["accepted"]["comment"]
    else:
        c = second["conflict"]
        text = merge.resolve_conflict("both", c["mine"], c["theirs"])
        assert "<A>" in text and "<B>" in text
    assert is_subsequence(base, text) or second["conflict"] is not None
    assert "<A>" in text and "<B>" in text


@settings(max_examples=300, deadline=None)
@given(scenarios())
def test_replaying_the_same_write_changes_nothing(case):
    base, edit_a, edit_b = case
    stored, seen, ops = scenario(base, edit_a, edit_b)
    for name in ("A", "B"):  # B arrives after A, then the retry of each
        result = merge.reconcile_fields(stored, seen, ops[name])
        if result["conflict"] is None:
            stored.update(result["accepted"])
    for name in ("A", "B", "A"):
        before = dict(stored)
        replay = merge.reconcile_fields(stored, seen, ops[name])
        if replay["conflict"] is None:
            stored.update(replay["accepted"])
        assert stored == before, name


@settings(max_examples=300, deadline=None)
@given(scenarios(), st.sampled_from(["mine", "theirs", "both"]))
def test_a_resolved_conflict_converges_and_a_resend_is_a_no_op(case, resolution):
    base, edit_a, edit_b = case
    stored, seen, ops = scenario(base, edit_a, edit_b)
    stored.update(merge.reconcile_fields(stored, seen, ops["A"])["accepted"])
    result = merge.reconcile_fields(stored, seen, {"comment": ops["B"]["comment"]})
    if result["conflict"] is None:
        return
    c = result["conflict"]
    resolved = merge.resolve_conflict(resolution, c["mine"], c["theirs"])
    # the client resends against the theirs it saw
    resend = merge.reconcile_fields(stored, {"comment": c["theirs"]}, {"comment": resolved})
    assert resend["conflict"] is None and resend["accepted"] == {"comment": resolved}
    stored.update(resend["accepted"])
    again = merge.reconcile_fields(stored, {"comment": c["theirs"]}, {"comment": resolved})
    assert again == {"accepted": {"comment": resolved}, "overwritten": [], "conflict": None}
    assert stored["comment"] == resolved
