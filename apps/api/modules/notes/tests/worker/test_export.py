"""build_flattened_pdf: structure, untouched source, rotation and crop placement, Devanagari, limits."""

import hashlib

import pikepdf
import pypdfium2 as pdfium
import pytest

from modules.notes.worker import export as ex
from modules.notes.worker.pdfutil import sha256_file

from .fixtures import make_pdfs as mk

DEVANAGARI = "विद्यार्थी परीक्षा"


def mark(kind="highlight", page=1, color="y", comment="", geometry=None, **extra):
    return {
        "page": page,
        "kind": kind,
        "geometry": geometry,
        "color": color,
        "comment": comment,
        "quote_exact": "",
        **extra,
    }


def render(path, index=0, scale=1.0):
    with pdfium.PdfDocument(str(path)) as doc:
        return doc[index].render(scale=scale).to_pil().convert("RGB")


def ink_box(image):
    """Normalised box of the dark pixels (the probe text)."""
    mask = image.convert("L").point(lambda v: 255 if v < 100 else 0)
    left, top, right, bottom = mask.getbbox()
    w, h = image.size
    return left / w, top / h, right / w, bottom / h


def mean_rgb(image, box):
    w, h = image.size
    crop = image.crop((int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h)))
    pixels = list(crop.get_flattened_data() if hasattr(crop, "get_flattened_data") else crop.getdata())
    return tuple(sum(p[i] for p in pixels) / len(pixels) for i in range(3))


def yellow_share(image, box):
    """Among the light pixels in the box (the paper, not the black glyphs) the share tinted yellow by the highlight."""
    w, h = image.size
    crop = image.crop((int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h)))
    light = [p for p in crop.getdata() if min(p) > 150]
    tinted = [p for p in light if p[0] > 200 and p[2] < p[1] - 25]
    return len(tinted) / max(len(light), 1)


def build(src, out, marks, fonts_dir, **kw):
    return ex.build_flattened_pdf(src, marks, out, fonts_dir=fonts_dir, **kw)


def test_output_opens_everywhere_keeps_pages_and_never_touches_the_source(tmp_path, src_text, fonts_dir):
    before = sha256_file(src_text)
    out = tmp_path / "out.pdf"
    marks = [
        mark("highlight", 1, geometry={"quads": [[0.1, 0.1, 0.4, 0.02]]}),
        mark("underline", 2, "g", geometry={"quads": [[0.1, 0.2, 0.4, 0.02]]}),
        mark("ink", 3, "i2", geometry={"strokes": [{"pts": [[0.1, 0.5], [0.4, 0.55], [0.6, 0.5]], "w": 0.004}]}),
        mark("area", 1, "b", geometry={"rect": [0.5, 0.5, 0.2, 0.1]}),
        mark("sticky", 2, "o", "check this", geometry={"pt": [0.8, 0.1]}),
        mark("textbox", 3, "y", "Remember Section 17(5)", geometry={"rect": [0.1, 0.7, 0.5, 0.06], "fs": 0.018}),
    ]
    result = build(src_text, out, marks, fonts_dir)
    assert (result.page_count, result.skipped, result.marks_drawn) == (3, (), 6)
    assert sha256_file(src_text) == before
    with pikepdf.open(out) as pdf:
        assert len(pdf.pages) == 3
    with pdfium.PdfDocument(str(out)) as doc:
        assert len(doc) == 3
    # every page still renders
    for i in range(3):
        assert render(out, i).size[0] > 100


def test_the_output_must_differ_from_the_source(src_text, fonts_dir):
    with pytest.raises(ValueError):
        build(src_text, src_text, [], fonts_dir)


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_a_highlight_lands_on_the_same_text_on_rotated_pages(tmp_path, make_rotated, fonts_dir, rotation):
    src = make_rotated(rotation)
    original = render(src)
    box = ink_box(original)  # where the reader sees the probe text, in the displayed frame
    pad = 0.004
    geometry = {"quads": [[box[0] - pad, box[1] - pad, box[2] - box[0] + 2 * pad, box[3] - box[1] + 2 * pad]]}
    out = tmp_path / f"out{rotation}.pdf"
    build(src, out, [mark(geometry=geometry)], fonts_dir)
    after = render(out)
    assert after.size == original.size
    inside = (box[0], box[1], box[2], box[3])
    assert yellow_share(after, inside) > 0.8, yellow_share(after, inside)
    assert yellow_share(original, inside) == 0
    # the text is still black under a multiply highlight
    assert ink_box(after) == pytest.approx(box, abs=0.01)
    # and nothing leaked into the opposite corner
    far = (
        0.8 if box[0] < 0.5 else 0.05,
        0.85 if box[1] < 0.5 else 0.05,
        0.95 if box[0] < 0.5 else 0.2,
        0.95 if box[1] < 0.5 else 0.15,
    )
    assert mean_rgb(after, far) == pytest.approx((255, 255, 255), abs=2)


def test_a_cropped_page_with_an_offset_origin(tmp_path, make_rotated, fonts_dir):
    for rotation in (0, 90):
        src = make_rotated(rotation, cropbox=(40, 560, 440, 760))
        original = render(src)
        box = ink_box(original)
        geometry = {"quads": [[box[0], box[1], box[2] - box[0], box[3] - box[1]]]}
        out = tmp_path / f"crop{rotation}.pdf"
        build(src, out, [mark(geometry=geometry)], fonts_dir)
        assert yellow_share(render(out), box) > 0.8


def test_highlight_uses_multiply_with_an_alpha_fallback(tmp_path, src_text, fonts_dir):
    out = tmp_path / "o.pdf"
    build(src_text, out, [mark(geometry={"quads": [[0.1, 0.1, 0.3, 0.02]]})], fonts_dir)
    with pikepdf.open(out) as pdf:
        gs = pdf.pages[0].obj.Resources.ExtGState.ArthaHl
        assert gs.BM == "/Multiply" and float(gs.ca) == pytest.approx(0.35)


def test_existing_resources_and_content_survive(tmp_path, src_text, fonts_dir):
    out = tmp_path / "o.pdf"
    build(src_text, out, [mark(geometry={"quads": [[0.1, 0.1, 0.3, 0.02]]})], fonts_dir)
    with pdfium.PdfDocument(str(out)) as doc:
        text = doc[0].get_textpage().get_text_range()
    assert "Input tax credit" in text


def test_a_page_with_shared_resources_does_not_leak_marks_to_other_pages(tmp_path, src_text, fonts_dir):
    out = tmp_path / "o.pdf"
    build(src_text, out, [mark("highlight", 1, geometry={"quads": [[0.1, 0.1, 0.3, 0.02]]})], fonts_dir)
    with pikepdf.open(out) as pdf:
        assert "/ArthaHl" in pdf.pages[0].obj.Resources.ExtGState
        assert "/ExtGState" not in pdf.pages[1].obj.Resources or "/ArthaHl" not in pdf.pages[1].obj.Resources.ExtGState


def test_devanagari_comment_renders_with_an_embedded_font(tmp_path, src_text, fonts_dir):
    out = tmp_path / "dev.pdf"
    marks = [mark("textbox", 1, "i1", DEVANAGARI, geometry={"rect": [0.1, 0.3, 0.6, 0.05], "fs": 0.02})]
    build(src_text, out, marks, fonts_dir)
    with pikepdf.open(out) as pdf:
        fonts = {k: f for k, f in pdf.pages[0].obj.Resources.Font.items() if f.Subtype == "/Type0"}
        names = {str(f.BaseFont) for f in fonts.values()}
        assert any("NotoSansDevanagari" in n for n in names), names
        for font in fonts.values():
            descendant = font.DescendantFonts[0]
            assert "/FontFile2" in descendant.FontDescriptor  # embedded, not referenced
            assert len(descendant.FontDescriptor.FontFile2.read_bytes()) > 1000
    # the glyph run is visible: dark pixels in the text box region (pen ink-1 is a mid-tone grey, so the cut-off is lenient)
    page = render(out, 0, scale=3)
    w, h = page.size
    region = page.crop((int(0.1 * w), int(0.3 * h), int(0.7 * w), int(0.35 * h))).convert("L")
    dark = sum(1 for v in region.getdata() if v < 170)
    assert dark > 150, dark
    # and the text stays searchable through the ToUnicode map
    with pdfium.PdfDocument(str(out)) as doc:
        extracted = doc[0].get_textpage().get_text_range()
    assert DEVANAGARI in extracted  # exact characters, thanks to /ActualText


def test_latin_and_devanagari_mix_in_one_comment(tmp_path, src_text, fonts_dir):
    out = tmp_path / "mix.pdf"
    comment = "Exam tip: " + DEVANAGARI + " (10 marks) 2026"
    build(src_text, out, [mark("sticky", 1, "y", comment, geometry={"pt": [0.5, 0.5]})], fonts_dir, appendix=True)
    with pdfium.PdfDocument(str(out)) as doc:
        assert len(doc) == 4  # three pages plus one appendix page
        text = doc[3].get_textpage().get_text_range()
    assert "Exam tip" in text and "10 marks" in text and "Page 1" in text


def test_appendix_lists_commented_marks_and_numbers_the_sticky_icon(tmp_path, src_text, fonts_dir):
    out = tmp_path / "app.pdf"
    marks = [
        mark(
            "highlight",
            2,
            comment="second",
            quote_exact="The quoted sentence",
            geometry={"quads": [[0.1, 0.1, 0.3, 0.02]]},
        ),
        mark("highlight", 1, comment="", geometry={"quads": [[0.1, 0.3, 0.3, 0.02]]}),  # no comment: not listed
        mark("sticky", 1, comment="first", geometry={"pt": [0.5, 0.5]}),
    ]
    result = build(src_text, out, marks, fonts_dir, appendix=True)
    assert (result.page_count, result.appendix_pages) == (4, 1)
    with pdfium.PdfDocument(str(out)) as doc:
        text = doc[3].get_textpage().get_text_range()
    assert text.index("first") < text.index("second") and "The quoted sentence" in text
    assert "1." in text and "2." in text and "3." not in text


def test_a_long_appendix_flows_onto_more_pages(tmp_path, src_text, fonts_dir):
    marks = [mark("sticky", 1, comment=f"note {i} " + "word " * 40, geometry={"pt": [0.5, 0.5]}) for i in range(60)]
    result = build(src_text, tmp_path / "long.pdf", marks, fonts_dir, appendix=True)
    assert result.appendix_pages >= 2 and result.page_count == 3 + result.appendix_pages


def test_pages_and_include_filters(tmp_path, src_text, fonts_dir):
    marks = [
        mark("highlight", 1, geometry={"quads": [[0.1, 0.1, 0.3, 0.02]]}),
        mark("underline", 2, geometry={"quads": [[0.1, 0.1, 0.3, 0.02]]}),
        mark("highlight", 3, geometry={"quads": [[0.1, 0.1, 0.3, 0.02]]}),
    ]
    out = tmp_path / "sub.pdf"
    result = build(src_text, out, marks, fonts_dir, pages=[2, 3], include={"highlight"})
    assert result.page_count == 2 and result.marks_drawn == 1 and result.skipped == ()
    with pdfium.PdfDocument(str(out)) as doc:
        assert "Page 2." in doc[0].get_textpage().get_text_range()
    with pytest.raises(ValueError):
        build(src_text, tmp_path / "bad.pdf", [], fonts_dir, pages=[9])


def test_invalid_marks_are_skipped_not_fatal(tmp_path, src_text, fonts_dir):
    marks = [
        mark("highlight", 1, geometry={"quads": []}),
        mark("highlight", 1, geometry={"nope": 1}),
        mark("highlight", 1, geometry={"quads": [[5, 5, 1, 1]]}),
        mark("highlight", 9, geometry={"quads": [[0.1, 0.1, 0.3, 0.02]]}),
        mark("bookmark", 1, geometry={"y": 0.2}),  # bookmarks are never drawn and never reported
        mark("highlight", 1, geometry={"quads": [[0.1, 0.1, 0.3, 0.02]]}),
    ]
    result = build(src_text, tmp_path / "o.pdf", marks, fonts_dir)
    assert result.marks_drawn == 1
    explicit = build(src_text, tmp_path / "b.pdf", [marks[4]], fonts_dir, include={"bookmark"})
    assert [s.reason for s in explicit.skipped] == ["not_rendered"]
    assert [(s.index, s.reason) for s in result.skipped] == [
        (0, "invalid_geometry"),
        (1, "invalid_geometry"),
        (2, "invalid_geometry"),
        (3, "page_out_of_range"),
    ]


def test_more_than_1000_pages_is_too_large_with_a_suggestion(tmp_path, fonts_dir):
    path = tmp_path / "many.pdf"
    with pikepdf.new() as pdf:
        for _ in range(1001):
            pdf.add_blank_page(page_size=(100, 100))
        pdf.save(path)
    with pytest.raises(ex.ExportTooLarge) as caught:
        build(path, tmp_path / "o.pdf", [], fonts_dir)
    assert caught.value.suggested_range == (1, 1000)
    assert not (tmp_path / "o.pdf").exists()
    assert build(path, tmp_path / "ok.pdf", [], fonts_dir, pages=range(1, 1001)).page_count == 1000


def test_time_budget(tmp_path, src_text, fonts_dir):
    with pytest.raises(ex.ExportTooLarge):
        build(src_text, tmp_path / "o.pdf", [], fonts_dir, time_budget_seconds=-1)


def test_copy_restricted_files_are_refused(tmp_path, src_text, fonts_dir):
    locked = mk.owner_only_pdf(tmp_path / "locked.pdf", src_text)
    with pytest.raises(ex.ExportNotAllowed):
        build(locked, tmp_path / "o.pdf", [], fonts_dir)


def test_missing_fonts_are_reported(tmp_path, src_text):
    empty = tmp_path / "nofonts"
    empty.mkdir()
    with pytest.raises(ex.FontsMissing):
        ex.build_flattened_pdf(src_text, [], tmp_path / "o.pdf", fonts_dir=empty)


def test_colour_table_covers_every_key():
    assert set(ex.COLOR_RGB) == {*ex.HIGHLIGHT_KEYS, *ex.INK_KEYS}
    assert all(0 <= c <= 1 for rgb in ex.COLOR_RGB.values() for c in rgb)
    assert set(ex.EDGE_RGB) == set(ex.HIGHLIGHT_KEYS)


def test_source_hash_check_helper_matches_hashlib(src_text):
    assert sha256_file(src_text) == hashlib.sha256(src_text.read_bytes()).hexdigest()
