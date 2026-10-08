"""The new edition reader: raw text, and the rectangle of a quote in the stored frame on plain, rotated and cropped pages."""

import pypdfium2 as pdfium
import pytest

from modules.notes.domain import coords
from modules.notes.worker import reanchor

from .fixtures import make_pdfs as mk


def dark_box(pdf_path, rotation_scale=2.0):
    """Where ink actually is on the rendered page, as fractions: the ground truth the rectangle must match."""
    doc = pdfium.PdfDocument(str(pdf_path))
    image = doc[0].render(scale=rotation_scale, grayscale=True).to_pil()
    mask = image.point(lambda v: 255 if v < 128 else 0)
    left, top, right, bottom = mask.getbbox()
    w, h = image.size
    return [left / w, top / h, (right - left) / w, (bottom - top) / h]


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_the_rectangle_of_a_quote_lands_on_the_ink_whatever_the_page_rotation(tmp_path, rotation):
    path = mk.rotated_pdf(tmp_path / f"r{rotation}.pdf", rotation)
    with reanchor.open_edition(path) as edition:
        raw = edition.text(1)
        start = raw.index("PROBE")
        quads = edition.quads(1, start, start + len("PROBE TEXT"))
    assert quads, raw
    x, y, w, h = quads[0]
    ink = dark_box(path)
    # PDFium's text box includes the line's ascent and descent, so it is taller than the ink; the ink must lie inside it.
    assert x - 0.01 <= ink[0] and ink[0] + ink[2] <= x + w + 0.01
    assert y - 0.01 <= ink[1] and ink[1] + ink[3] <= y + h + 0.01
    assert (
        max(w, h) < 0.7 and min(w, h) < 0.15
    )  # a box around the words (turned on its side at 90 and 270), not the page


def test_a_cropped_page_is_measured_from_its_crop_box(tmp_path):
    path = mk.rotated_pdf(tmp_path / "crop.pdf", 0, cropbox=(40, 300, 572, 792))
    with reanchor.open_edition(path) as edition:
        start = edition.text(1).index("PROBE")
        quads = edition.quads(1, start, start + 5)
    ink = dark_box(path)
    assert quads and quads[0][0] - 0.01 <= ink[0] and quads[0][1] - 0.01 <= ink[1]


def test_text_comes_back_page_by_page_and_a_missing_page_is_empty(tmp_path):
    path = mk.text_pdf(tmp_path / "t.pdf", pages=3)
    with reanchor.open_edition(path) as edition:
        assert edition.page_count == 3
        assert "Page 2." in edition.text(2) and "Page 3." not in edition.text(2)
        assert edition.quads(1, 0, 0) == []


def test_the_forward_maths_is_the_inverse_of_the_exports(tmp_path):
    for rotation in (0, 90, 180, 270):
        stored = [0.2, 0.1, 0.3, 0.05]
        user = coords.rect_to_user_space(stored, rotation, 600.0, 800.0)
        unrotated = [user[0] / 600, 1 - (user[1] + user[3]) / 800, user[2] / 600, user[3] / 800]
        back = coords.rotate_rect(unrotated, rotation)
        assert all(abs(a - b) < 0.001 for a, b in zip(stored, back, strict=True)), rotation
