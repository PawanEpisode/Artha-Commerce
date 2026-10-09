from modules.recall.domain import decks as d


def row(item, version, importance="bullet", faces=1, kind="create"):
    return d.SnapshotRow(item, version, importance, faces, kind)


def test_first_version_everything_is_added():
    assert d.change_vs_prev(None, row("a", "v1")) == "added"


def test_unchanged_added_and_edit_kinds():
    prev = {"a": "v1", "b": "v1"}
    assert d.change_vs_prev(prev, row("a", "v1")) == "unchanged"
    assert d.change_vs_prev(prev, row("c", "v1")) == "added"
    for kind in ("typo", "clarify", "substantive", "amendment"):
        assert d.change_vs_prev(prev, row("a", "v2", kind=kind)) == kind


def test_a_new_version_marked_create_is_a_rewrite():
    assert d.change_vs_prev({"a": "v1"}, row("a", "v2", kind="create")) == "substantive"


def test_removed_items_and_summary():
    prev = {"a": "v1", "b": "v1", "c": "v1"}
    rows = [row("a", "v1"), row("b", "v2", kind="typo"), row("d", "v1")]
    assert d.removed_item_ids(prev, rows) == ["c"]
    s = d.diff_summary(prev, rows)
    assert (s["added"], s["removed"], s["unchanged"], s["typo"], s["substantive"]) == (1, 1, 1, 1, 0)
    assert d.diff_summary(None, rows)["removed"] == 0


def test_tier_counts_count_faces():
    t = d.tier_counts([row("a", "v", "mandatory", 3), row("b", "v", "bullet"), row("c", "v", "mandatory")])
    assert t == {"v": 1, "mandatory": 2, "important": 0, "bullet": 1, "cards": 5}


def test_rights_gate_blocks_unknown_only():
    got = d.rights_blockers({"a": "unknown", "b": "original", "c": "licensed", "d": "unknown"})
    assert got == ["a", "d"]


def test_cards_at_or_above_the_tier():
    rows = [row("a", "v", "mandatory", 2), row("b", "v", "important"), row("c", "v", "bullet", 4)]
    assert d.cards_at_or_above(rows, "bullet") == 7
    assert d.cards_at_or_above(rows, "important") == 3
    assert d.cards_at_or_above(rows, "mandatory") == 2


def test_preview_folds_and_cuts_at_a_word():
    assert d.preview("a   b\n c") == "a b c"
    long = "word " * 100
    out = d.preview(long, 20)
    assert len(out) <= 20 and out.endswith("…") and " " not in out[-2:]
