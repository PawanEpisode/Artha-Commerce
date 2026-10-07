"""extract_pages and chunk_ranges."""

import pytest

from modules.notes.worker import extract as ex
from modules.notes.worker.pdfutil import PdfOpenError, PdfPasswordRequired

from .fixtures import make_pdfs as mk


def test_chunk_ranges():
    assert ex.chunk_ranges(0) == []
    assert ex.chunk_ranges(1) == [(1, 1)]
    assert ex.chunk_ranges(45, 20) == [(1, 20), (21, 40), (41, 45)]
    assert ex.chunk_ranges(20, 10) == [(1, 10), (11, 20)]
    with pytest.raises(ValueError):
        ex.chunk_ranges(5, 0)


def test_normalise_text():
    assert ex.normalise_text("a\x00b  \t c\r\n\r\n d\x07e ") == "ab c\nde"
    assert len(ex.normalise_text("x" * 70_000)) == ex.MAX_CHARS_PER_PAGE


def test_lang_hint():
    assert ex.lang_hint("Goods and services") == "en"
    assert ex.lang_hint("विद्यार्थी") == "hi"
    assert ex.lang_hint("1234 ...") is None


def test_extracts_a_range_one_based_inclusive(src_text):
    pages = ex.extract_pages(src_text, 2, 3)
    assert [p.page for p in pages] == [2, 3]
    assert "Page 2." in pages[0].text and "Input tax credit" in pages[0].text
    assert pages[0].chars == len(pages[0].text) and pages[0].lang_hint == "en" and pages[0].error is None


def test_range_is_clipped_to_the_page_count(src_text):
    assert [p.page for p in ex.extract_pages(src_text, 3, 50)] == [3]
    assert ex.extract_pages(src_text, 9, 12) == []


def test_bad_ranges_raise(src_text):
    with pytest.raises(ValueError):
        ex.extract_pages(src_text, 0, 2)
    with pytest.raises(ValueError):
        ex.extract_pages(src_text, 3, 2)


def test_a_scanned_page_has_empty_text_and_no_error(tmp_path):
    page = ex.extract_pages(mk.scanned_pdf(tmp_path / "s.pdf", 1), 1, 1)[0]
    assert (page.text, page.chars, page.error) == ("", 0, None)


def test_a_failing_page_does_not_abort_the_chunk(src_text, monkeypatch):
    real = ex._extract_one
    import pypdfium2 as pdfium

    def flaky(doc, number):
        if number == 2:
            raise_for = pdfium.PdfiumError("boom")
            raise raise_for
        return real(doc, number)

    # the wrapper under test is _extract_one's own try/except, so make the page fetch fail inside it
    class Doc:
        def __init__(self, doc):
            self.doc = doc

        def __len__(self):
            return len(self.doc)

        def __getitem__(self, i):
            if i == 1:
                raise pdfium.PdfiumError("boom")
            return self.doc[i]

    from modules.notes.worker import pdfutil

    original = pdfutil.open_pdfium

    from contextlib import contextmanager

    @contextmanager
    def wrapped(path, **kw):
        with original(path, **kw) as doc:
            yield Doc(doc)

    monkeypatch.setattr(ex.pdfutil, "open_pdfium", wrapped)
    pages = ex.extract_pages(src_text, 1, 3)
    assert [p.page for p in pages] == [1, 2, 3]
    assert pages[1].text == "" and pages[1].error == "extract_failed"
    assert pages[0].text and pages[2].text and flaky


def test_an_oversized_page_is_skipped_with_an_error(tmp_path):
    pages = ex.extract_pages(mk.huge_page_pdf(tmp_path / "h.pdf", 15000, 200), 1, 1)
    assert pages[0].error == "page_too_large" and pages[0].text == ""


def test_unreadable_files(tmp_path, src_text):
    junk = tmp_path / "junk.pdf"
    junk.write_bytes(b"%PDF-1.4 nope")
    with pytest.raises(PdfOpenError):
        ex.extract_pages(junk, 1, 1)
    with pytest.raises(PdfPasswordRequired):
        ex.extract_pages(mk.encrypted_pdf(tmp_path / "e.pdf", src_text), 1, 1)
    assert ex.extract_pages(mk.encrypted_pdf(tmp_path / "e2.pdf", src_text), 1, 1, password="secret")[0].text
