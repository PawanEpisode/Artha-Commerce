import pytest

from modules.notes.domain import ocr_quality as q


def test_page_confidence_ignores_non_words_and_weights_by_length():
    words = [("Input", 90), ("tax", 60), ("", 95), ("   ", 10), ("box", -1), ("credit", 90)]
    # (90*5 + 60*3 + 90*6) / 14 = 83.57
    assert q.page_confidence(words) == 84
    assert q.page_confidence([{"text": "ab", "conf": 50.0}, {"text": "cdef", "conf": 100}]) == 83  # 83.33
    assert q.page_confidence([("a", 100), ("bbbb", 0)]) == 20
    assert q.page_confidence([("x", 49.5)]) == 50  # half up


@pytest.mark.parametrize("words", [[], [("", 90)], [("word", -1)], [("  ", 80)]])
def test_page_confidence_is_none_without_real_words(words):
    assert q.page_confidence(words) is None


def test_page_confidence_clamps_a_runaway_value():
    assert q.page_confidence([("word", 140)]) == 100


def _page(chars, coverage):
    return {"chars": chars, "image_coverage": coverage}


def test_a_scan_needs_most_pages_to_have_no_text_and_a_page_sized_image():
    scan = [_page(0, 0.95)] * 7 + [_page(500, 0.1)] * 3
    assert q.is_scanned(scan) is True  # exactly 70%
    assert q.is_scanned([_page(0, 0.95)] * 6 + [_page(500, 0.1)] * 4) is False  # 60%


def test_both_conditions_are_needed():
    assert q.is_scanned([_page(0, 0.0)] * 10) is False  # blank pages are not scans
    assert q.is_scanned([_page(900, 0.99)] * 10) is False  # a text page with a background image
    assert q.is_scanned([_page(19, 0.8)] * 10) is True
    assert q.is_scanned([_page(20, 0.8)] * 10) is False
    assert q.is_scanned([_page(5, 0.79)] * 10) is False


def test_only_the_first_twenty_samples_count_and_none_means_unknown():
    many = [_page(0, 0.9)] * 14 + [_page(900, 0.0)] * 6 + [_page(900, 0.0)] * 50
    assert q.is_scanned(many) is True  # 14 of the first 20
    assert q.is_scanned([]) is None


def test_the_estimate_is_six_seconds_a_page():
    assert q.SECONDS_PER_PAGE == 6
    assert q.ocr_estimate_seconds(320) == 1920
    assert q.ocr_estimate_seconds(0) == 0
    assert q.ocr_estimate_seconds(-4) == 0


@pytest.mark.parametrize(
    ("value", "bucket"),
    [(None, "none"), (100, "high"), (85, "high"), (84, "medium"), (60, "medium"), (59, "low"), (0, "low")],
)
def test_confidence_buckets(value, bucket):
    assert q.confidence_bucket(value) == bucket
