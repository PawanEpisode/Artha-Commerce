"""PDF header sniffing: pure, no database."""

from modules.media import sniff


def head(prefix=b"", tail=b"x" * 2000):
    return (prefix + b"%PDF-1.7\n" + tail)[: sniff.PDF_SNIFF_BYTES]


def test_a_plain_pdf_passes():
    assert sniff.pdf_sniff(head()) is None
    assert sniff.pdf_sniff(b"%PDF-2.0\n%\xe2\xe3\xcf\xd3\n") is None


def test_junk_before_the_header_is_tolerated_only_inside_the_first_kilobyte():
    assert sniff.pdf_sniff(head(b"\n" * 1023)) is None  # header starts at offset 1023: the last allowed
    assert sniff.pdf_sniff(head(b"\n" * 1024)) == "type_mismatch"  # offset 1024: hidden too deep
    assert sniff.pdf_header_offset(head(b"abc")) == 3


def test_other_formats_and_look_alikes_are_refused():
    for data in (
        b"",
        b"PK\x03\x04" + b"\0" * 100,
        b"\x89PNG\r\n\x1a\n",
        b"%PDF",
        b"%PDF-9.9",
        b"%PDF-x.y",
        b"<html>%PDF-1.7"[:5],
    ):
        assert sniff.pdf_sniff(data) == "type_mismatch", data


def test_an_archive_with_a_pdf_appended_after_a_kilobyte_is_a_polyglot_and_is_refused():
    assert sniff.pdf_sniff((b"PK\x03\x04" + b"\0" * 1500 + b"%PDF-1.4")[: sniff.PDF_SNIFF_BYTES]) == "type_mismatch"
