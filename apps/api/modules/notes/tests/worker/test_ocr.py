"""ocr_pages: needs the tesseract binary; the Hindi cases also need the `hin` language data."""

import shutil

import pytest

from modules.notes.worker import ocr
from modules.notes.worker.pdfutil import MAX_RENDER_PIXELS

from .conftest import tesseract_langs
from .fixtures import make_pdfs as mk

needs_tesseract = pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract is not installed")
needs_hindi = pytest.mark.skipif("hin" not in tesseract_langs(), reason="tesseract has no `hin` language data")


def test_tsv_parser_normalises_boxes_and_averages_confidence():
    header = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext"
    rows = [
        "1\t1\t0\t0\t0\t0\t0\t0\t1000\t500\t-1\t",
        "5\t1\t1\t1\t1\t1\t100\t50\t200\t25\t90.0\tHello",
        "5\t1\t1\t1\t1\t2\t320\t50\t100\t25\t70.0\tworld",
        "5\t1\t1\t1\t2\t1\t100\t100\t50\t25\t-1\tnoise",
        "5\t1\t1\t1\t2\t2\t100\t100\t50\t25\t80\t   ",
        "5\t1\t1\t1\t3\t1\t100\t150\t50\t25\t80\tNext",
    ]
    text, conf, words = ocr.parse_tsv("\n".join([header, *rows]), 1000, 500)
    assert text == "Hello world\nNext" and conf == 80.0
    assert words[0] == (0.1, 0.1, 0.2, 0.05, "Hello") and len(words) == 3


def test_language_allow_list(tmp_path):
    for bad in ("fra", "eng;rm -rf /", "eng+hin+fra", "", "$(id)"):
        with pytest.raises(ValueError):
            ocr.ocr_pages(tmp_path / "x.pdf", [1], bad)


def test_dpi_bounds(src_text):
    with pytest.raises(ValueError):
        ocr.ocr_pages(src_text, [1], dpi=1200)


@needs_tesseract
def test_reads_a_scanned_page_with_boxes_in_the_page_frame(tmp_path):
    path = mk.scanned_pdf(tmp_path / "scan.pdf", 2)
    pages = ocr.ocr_pages(path, [1, 2])
    assert [p.page for p in pages] == [1, 2]
    first = pages[0]
    assert first.error is None and "INPUT" in first.text.upper() and "CREDIT" in first.text.upper()
    assert 60 <= first.conf <= 100
    boxes = {w[4].upper(): w for w in first.words}
    x, y, w, h, _ = boxes["INPUT"]
    # "INPUT TAX CREDIT" starts at 150 px / 1654 px and 250 px / 2339 px of the A4 page (the bitmap's pixel grid)
    assert x == pytest.approx(150 / 1654, abs=0.02) and y == pytest.approx(250 / 2339, abs=0.03)
    assert 0 < w < 0.4 and 0 < h < 0.1
    assert all(0 <= v <= 1 for word in first.words for v in word[:4])
    assert all(len(str(v).split(".")[-1]) <= 4 for word in first.words for v in word[:4])
    # the second line sits below the first
    assert boxes["GOODS"][1] > boxes["INPUT"][1]


def _upright_after_rotation(path, rotation):
    """A portrait page whose text is drawn turned by `rotation` degrees, so /Rotate shows it upright."""
    import pikepdf
    from reportlab.pdfgen import canvas

    base = path.with_suffix(".base.pdf")
    c = canvas.Canvas(str(base), pagesize=(612, 792))
    c.translate(450, 150) if rotation == 90 else c.translate(150, 650)
    c.rotate(rotation)
    c.setFont("Helvetica-Bold", 48)
    c.drawString(0, 0, "ROTATED WORD")
    c.showPage()
    c.save()
    with pikepdf.open(base) as pdf:
        pdf.pages[0].obj.Rotate = rotation
        pdf.save(path)
    return path


def _ink_box(path):
    """Normalised bounding box of the dark pixels of the displayed page (what a reader sees)."""
    import pypdfium2 as pdfium

    with pdfium.PdfDocument(str(path)) as doc:
        image = doc[0].render(scale=1).to_pil().convert("L")
    mask = image.point(lambda v: 255 if v < 128 else 0)
    left, top, right, bottom = mask.getbbox()
    w, h = image.size
    return left / w, top / h, right / w, bottom / h


@needs_tesseract
@pytest.mark.parametrize("rotation", [90, 270])
def test_boxes_follow_the_displayed_frame_on_a_rotated_page(tmp_path, rotation):
    path = _upright_after_rotation(tmp_path / f"r{rotation}.pdf", rotation)
    page = ocr.ocr_pages(path, [1])[0]
    left, top, right, bottom = _ink_box(path)
    assert right - left > 0.3  # displayed landscape, text reads left to right
    word = next(w for w in page.words if w[4].upper().startswith("ROTATED"))
    cx, cy = word[0] + word[2] / 2, word[1] + word[3] / 2
    assert left - 0.02 <= cx <= right + 0.02 and top - 0.02 <= cy <= bottom + 0.02


@needs_tesseract
def test_a_text_pdf_page_is_ocr_able_too(src_text):
    page = ocr.ocr_pages(src_text, [1])[0]
    assert page.error is None and "Input" in page.text


@needs_tesseract
def test_pages_over_a3_use_the_lower_dpi_and_oversized_pixels_are_refused(tmp_path):
    big = mk.huge_page_pdf(tmp_path / "big.pdf", 1500, 1500)  # 1500 pt square is over A3
    result = ocr.ocr_pages(big, [1], dpi=300, max_dpi_over_a3=100)
    assert result[0].error is None  # 1500 pt at 100 dpi is about 2.1 megapixels
    too_big = mk.huge_page_pdf(tmp_path / "bomb.pdf", 14000, 14000)
    # 14,000 pt at 200 dpi is 38.9k px a side: over the 40 megapixel cap
    result = ocr.ocr_pages(too_big, [1], max_dpi_over_a3=200)
    assert result[0].error == "render_too_large" and result[0].words == ()
    assert (14000 * 200 / 72) ** 2 > MAX_RENDER_PIXELS


@needs_tesseract
def test_a_bad_page_number_is_an_error_row_not_an_exception(src_text):
    pages = ocr.ocr_pages(src_text, [1, 99])
    assert pages[1].error == "render_failed" and pages[0].error is None


@needs_tesseract
def test_timeout_is_reported_per_page(src_text, monkeypatch):
    import subprocess

    def slow(*a, **k):
        raise subprocess.TimeoutExpired("tesseract", 1)

    monkeypatch.setattr(ocr, "_run_tesseract", slow)
    assert ocr.ocr_pages(src_text, [1])[0].error == "timeout"


@needs_tesseract
def test_tesseract_runs_with_one_thread_and_no_shell(src_text, monkeypatch):
    seen = {}
    real = ocr.subprocess.run

    def spy(argv, **kw):
        seen["argv"], seen["env"] = argv, kw["env"]
        return real(argv, **kw)

    monkeypatch.setattr(ocr.subprocess, "run", spy)
    ocr.ocr_pages(src_text, [1], "eng")
    assert seen["env"]["OMP_THREAD_LIMIT"] == "1" and isinstance(seen["argv"], list)
    assert seen["argv"][0] == "tesseract" and seen["argv"][-1] == "tsv" and "eng" in seen["argv"]


@needs_tesseract
@needs_hindi
def test_english_plus_hindi_language_pack_loads(tmp_path):
    path = mk.scanned_pdf(tmp_path / "scan.pdf", 1)
    page = ocr.ocr_pages(path, [1], "eng+hin")[0]
    assert page.error is None and "INPUT" in page.text.upper()


def test_chunk_ranges_reuse():
    assert ocr.chunk_ranges(25, ocr.OCR_CHUNK) == [(1, 10), (11, 20), (21, 25)]
