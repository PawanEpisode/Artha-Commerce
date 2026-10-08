"""Finding a quote again in a new edition and judging a page unchanged: pure rules, no database."""

from modules.notes.domain import reanchor as d

OLD = "Input tax credit under GST is available on inward supplies used for business."


def pages(mapping):
    return lambda n: mapping.get(n, "")


def test_pages_are_tried_nearest_first_and_stay_in_range():
    assert d.page_order(5, 20)[:3] == [5, 4, 6] or d.page_order(5, 20)[:3] == [5, 6, 4]
    assert all(1 <= p <= 3 for p in d.page_order(1, 3))


def test_a_quote_is_found_again_on_the_same_page():
    found = d.find_quote(
        "tax credit under GST",
        "Input ",
        " is available",
        hint_page=2,
        hint_start=None,
        page_count=4,
        text_of=pages({2: OLD}),
    )
    assert found and found.page == 2 and OLD[found.start : found.end] == "tax credit under GST" and found.score >= 0.95


def test_a_quote_that_moved_a_few_pages_is_found_there():
    found = d.find_quote(
        "tax credit under GST",
        "",
        "",
        hint_page=2,
        hint_start=None,
        page_count=6,
        text_of=pages({2: "Something else entirely.", 4: "Revised. " + OLD}),
    )
    assert found and found.page == 4


def test_a_quote_that_is_gone_is_not_found():
    found = d.find_quote(
        "quantum chromodynamics lecture",
        "",
        "",
        hint_page=1,
        hint_start=None,
        page_count=3,
        text_of=pages({1: OLD, 2: OLD, 3: OLD}),
    )
    assert found is None or found.score < d.ATTACH_MIN


def test_a_page_is_unchanged_when_its_text_is_the_same_up_to_spacing():
    assert d.same_page_text(OLD, OLD.replace(" ", "  ")) is True
    assert d.same_page_text(OLD, "A completely different paragraph about depreciation of fixed assets.") is False


def test_a_page_with_no_text_to_compare_is_unknown():
    assert d.same_page_text("", OLD) is None
    assert d.same_page_text(OLD, "") is None


def test_the_same_place_ignores_a_hair_of_difference():
    a = [(0.1, 0.1, 0.3, 0.02)]
    assert d.same_place(a, [(0.105, 0.1, 0.3, 0.02)]) is True
    assert d.same_place(a, [(0.1, 0.3, 0.3, 0.02)]) is False
