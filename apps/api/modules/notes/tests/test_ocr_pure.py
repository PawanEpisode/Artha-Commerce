"""Pure rules of OCR and export: page selections, engine strings, export options and who may export."""

import pytest

from modules.notes.domain import export_options as eo
from modules.notes.domain.pagespec import PageSpecError, format_pages, parse_pages
from modules.notes.services import ocr


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        ("1-3", [1, 2, 3]),
        ("1-40,50", [*range(1, 41), 50]),
        (" 3 , 1 ,2-4 ", [1, 2, 3, 4]),
        ("5,5,5", [5]),
        ("10-12,1-2", [1, 2, 10, 11, 12]),
        (None, list(range(1, 61))),
        ("", list(range(1, 61))),
        ("   ", list(range(1, 61))),
        ("60", [60]),
    ],
)
def test_parse_pages(spec, expected):
    assert parse_pages(spec, 60) == expected


@pytest.mark.parametrize(
    ("spec", "code"),
    [
        ("0", "out_of_range"),
        ("61", "out_of_range"),
        ("1-61", "out_of_range"),
        ("5-3", "reversed"),
        ("a", "syntax"),
        ("1,,2", "syntax"),
        ("1-", "syntax"),
        ("-3", "syntax"),
        ("1-2-3", "syntax"),
        ("1;2", "syntax"),
        ("1," * 200, "too_long"),
        ("999999", "syntax"),
    ],
)
def test_parse_pages_refuses_bad_specs(spec, code):
    with pytest.raises(PageSpecError) as caught:
        parse_pages(spec, 60)
    assert caught.value.code == code


def test_parse_pages_needs_a_page():
    with pytest.raises(PageSpecError):
        parse_pages("1", 0)


def test_format_pages_is_the_canonical_form():
    assert format_pages([3, 1, 2, 50, 7, 8, 8]) == "1-3,7-8,50"
    assert format_pages([]) == ""
    assert parse_pages(format_pages([4, 5, 9]), 20) == [4, 5, 9]


def test_the_chunk_is_ten_pages_like_the_worker_library():
    from modules.notes.worker import ocr as engine

    assert ocr.CHUNK == engine.OCR_CHUNK == 10
    assert set(ocr.LANGS) == set(engine.ALLOWED_LANGS)


def test_engine_strings_and_coverage():
    assert ocr.engine_string("eng", 2) == "tesseract-5.2:eng"
    assert ocr.engine_lang("tesseract-5.2:eng+hin") == "eng+hin"
    assert ocr.engine_lang(None) is None
    assert ocr.engine_covers("tesseract-5.1:eng", "eng")
    assert ocr.engine_covers("tesseract-5.1:eng+hin", "eng")  # Hindi data reads English too
    assert not ocr.engine_covers("tesseract-5.1:eng", "eng+hin")
    assert not ocr.engine_covers(None, "eng")


def test_the_specs_of_queued_jobs_read_back():
    assert ocr.pages_of_spec("1-3,9") == [1, 2, 3, 9]
    assert ocr.pages_of_spec(None) == []


def test_export_options_default_and_canonical_form():
    opts = eo.validate_options(None, 100)
    assert opts == eo.ExportOptions() and opts.stored() == {}
    full = eo.validate_options({"pages": "1-100"}, 100)
    assert full.pages is None  # everything is the same as no selection
    chosen = eo.validate_options(
        {
            "pages": "3,1-2",
            "include": ["sticky", "highlight"],
            "colors": ["g", "y"],
            "tags": ["b", "a"],
            "appendix": True,
        },
        100,
    )
    assert chosen.stored() == {
        "pages": "1-3",
        "include": ["highlight", "sticky"],
        "colors": ["y", "g"],
        "tags": ["a", "b"],
        "appendix": True,
    }
    assert eo.validate_options(chosen.stored(), 100) == chosen  # what is stored validates back to the same options


@pytest.mark.parametrize(
    ("raw", "field"),
    [
        ([], "options"),
        ({"nope": 1}, "options"),
        ({"pages": "101"}, "pages"),
        ({"pages": 5}, "pages"),
        ({"include": []}, "include"),
        ({"include": ["bookmark"]}, "include"),
        ({"include": "highlight"}, "include"),
        ({"colors": ["red"]}, "colors"),
        ({"colors": []}, "colors"),
        ({"tags": [1]}, "tags"),
        ({"tags": ["x"] * 60}, "tags"),
        ({"appendix": "yes"}, "appendix"),
    ],
)
def test_export_options_refuse_bad_input(raw, field):
    with pytest.raises(eo.OptionsError) as caught:
        eo.validate_options(raw, 100)
    assert caught.value.field == field


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({}, None),
        ({"can_copy": None, "can_modify": None}, None),  # unknown flags: the worker's check on the real file decides
        ({"can_copy": False}, "restricted"),
        ({"can_modify": False}, "restricted"),
        ({"status": "needs_password"}, "locked"),
        ({"is_encrypted": True, "page_count": None}, "locked"),
        ({"status": "inspecting"}, "not_ready"),
        ({"page_count": None}, "not_ready"),
        ({"status": "needs_password", "can_copy": False}, "locked"),  # locked is reported before restricted
    ],
)
def test_who_may_export(kwargs, reason):
    base = {"status": "ready", "is_encrypted": False, "page_count": 10, "can_copy": True, "can_modify": True}
    assert eo.export_block_reason(**{**base, **kwargs}) == reason
