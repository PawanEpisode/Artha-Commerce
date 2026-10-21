"""
Unit tests for domain matching and progress calculations (F-12).
"""

from modules.material.domain import matching, progress


def test_matching_exact_and_renumbered():
    prev_rows = [
        {"id": "p1", "item_id": "i1", "kind": "illustration", "label_norm": "ill-1", "match_hash": "hash_a", "descriptor": "Intro problem", "position": 1024},
        {"id": "p2", "item_id": "i2", "kind": "illustration", "label_norm": "ill-2", "match_hash": "hash_b", "descriptor": "Advanced problem", "position": 2048},
    ]

    new_rows = [
        # renumbered: ill-2 has hash_a (matches p1)
        {"id": "n1", "kind": "illustration", "label_norm": "ill-2", "match_hash": "hash_a", "descriptor": "Intro problem", "position": 1024},
        # new row
        {"id": "n2", "kind": "illustration", "label_norm": "ill-3", "match_hash": "hash_c", "descriptor": "Brand new problem", "position": 2048},
    ]

    candidates = matching.match_units_items(prev_rows, new_rows)

    # p1 matched n1 (hash exact, renumbered)
    cand_p1 = next(c for c in candidates if c.previous_row_id == "p1")
    assert cand_p1.change_kind == "renumbered"
    assert cand_p1.match_method == "hash"
    assert cand_p1.match_confidence == 1.0

    # n2 is new
    cand_n2 = next(c for c in candidates if c.new_row_temp_id == "n2")
    assert cand_n2.change_kind == "new"

    # p2 was removed
    cand_p2 = next(c for c in candidates if c.previous_row_id == "p2" and c.change_kind == "removed")
    assert cand_p2 is not None


def test_progress_summary():
    items = [
        {"id": "ei1", "item_id": "i1", "kind": "illustration", "match_hash": "h1"},
        {"id": "ei2", "item_id": "i2", "kind": "illustration", "match_hash": "h2"},
        {"id": "ei3", "item_id": "i3", "kind": "mcq", "match_hash": "h3"},
    ]

    progress_map = {
        "i1": {"state": "done", "content_stamp": "h1", "revisited_at": None},
        "i2": {"state": "revise", "content_stamp": "h2", "revisited_at": None},
    }

    summary = progress.compute_chapter_summary(items, progress_map)
    assert summary["total"] == 3
    assert summary["done"] == 1
    assert summary["revise"] == 1
    assert summary["todo"] == 1
    assert summary["percent"] == 33
    assert summary["by_kind"]["illustrations"]["done"] == 1
    assert summary["by_kind"]["illustrations"]["total"] == 2
    assert summary["by_kind"]["questions"]["total"] == 1
    assert summary["by_kind"]["questions"]["done"] == 0


def test_is_revised_since_done():
    prog = {"state": "done", "content_stamp": "old_hash", "revisited_at": None}
    assert progress.is_revised_since_done(prog, "new_hash") is True
    assert progress.is_revised_since_done(prog, "old_hash") is False

    prog_revisited = {"state": "done", "content_stamp": "old_hash", "revisited_at": "2026-10-01"}
    assert progress.is_revised_since_done(prog_revisited, "new_hash") is False
