"""
`ocr_pages`: render with PDFium, read with the Tesseract CLI (TSV), return word boxes in the display frame (ERD 6.5, 3.5).

Frame: the page as displayed with its intrinsic /Rotate applied (PDFium draws it that way), origin top-left, x/y/w/h as
fractions of the rendered image, four decimals. The language is checked against an allow-list and passed to `subprocess`
as an argument vector (no shell), so a user string can never reach a command line. Tesseract has no network code and runs
with `OMP_THREAD_LIMIT=1` so one OCR page uses one core.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass

import pypdfium2 as pdfium

from . import pdfutil
from .extract import chunk_ranges  # noqa: F401 - re-exported: OCR chunks are `chunk_ranges(n, OCR_CHUNK)`

OCR_CHUNK = 10
ALLOWED_LANGS = frozenset({"eng", "eng+hin"})
A3_AREA_POINTS = 841.89 * 1190.55
TESSERACT_BIN = "tesseract"


@dataclass(frozen=True)
class OcrPage:
    page: int  # 1-based
    text: str
    conf: float  # mean word confidence, 0..100
    words: tuple[tuple[float, float, float, float, str], ...] = ()  # (x, y, w, h, word), normalised, 4 decimals
    error: str | None = None  # page_too_large | render_too_large | render_failed | timeout | ocr_failed


def ocr_pages(
    path: str | os.PathLike,
    pages: Iterable[int],
    lang: str = "eng",
    *,
    dpi: int = 300,
    max_dpi_over_a3: int = 200,
    timeout_per_page: float = 30,
    password: str | None = None,
) -> list[OcrPage]:
    """OCR the given 1-based pages. Never raises for a bad page; raises ValueError for a bad language or dpi."""
    if lang not in ALLOWED_LANGS:
        raise ValueError(f"Unsupported OCR language {lang!r}.")
    if not 72 <= dpi <= 600 or not 72 <= max_dpi_over_a3 <= 600:
        raise ValueError("dpi must be between 72 and 600.")
    wanted = list(dict.fromkeys(int(p) for p in pages))
    out: list[OcrPage] = []
    with pdfutil.open_pdfium(path, password=password) as doc, tempfile.TemporaryDirectory(prefix="ocr-") as tmp:
        for number in wanted:
            if number < 1 or number > len(doc):
                out.append(OcrPage(number, "", 0.0, (), "render_failed"))
                continue
            out.append(_ocr_one(doc, number, lang, dpi, max_dpi_over_a3, timeout_per_page, tmp))
    return out


def _ocr_one(doc, number: int, lang: str, dpi: int, max_dpi_over_a3: int, timeout: float, tmp: str) -> OcrPage:
    image_path = os.path.join(tmp, f"p{number}.png")
    try:
        page = doc[number - 1]
        try:
            width_pt, height_pt = page.get_size()  # rotation and crop box applied
            try:
                pdfutil.check_page_points(width_pt, height_pt)
            except pdfutil.PdfLimitError:
                return OcrPage(number, "", 0.0, (), "page_too_large")
            use_dpi = min(dpi, max_dpi_over_a3) if width_pt * height_pt > A3_AREA_POINTS * 1.02 else dpi
            scale = use_dpi / 72
            try:
                pdfutil.check_render_pixels(width_pt, height_pt, scale)
            except pdfutil.PdfLimitError:
                return OcrPage(number, "", 0.0, (), "render_too_large")
            image = page.render(scale=scale, may_draw_forms=False, grayscale=True).to_pil()
        finally:
            page.close()
    except (pdfium.PdfiumError, ValueError, MemoryError):
        return OcrPage(number, "", 0.0, (), "render_failed")
    try:
        pixel_w, pixel_h = image.size
        image.save(image_path, format="PNG")
        image.close()
        tsv = _run_tesseract(image_path, lang, use_dpi, timeout)
    except subprocess.TimeoutExpired:
        return OcrPage(number, "", 0.0, (), "timeout")
    except (OSError, subprocess.SubprocessError):
        return OcrPage(number, "", 0.0, (), "ocr_failed")
    finally:
        try:
            os.unlink(image_path)
        except OSError:
            pass
    if tsv is None:
        return OcrPage(number, "", 0.0, (), "ocr_failed")
    text, conf, words = parse_tsv(tsv, pixel_w, pixel_h)
    return OcrPage(number, text, conf, words)


def _run_tesseract(image_path: str, lang: str, dpi: int, timeout: float) -> str | None:
    env = {k: v for k, v in os.environ.items() if k in {"PATH", "TESSDATA_PREFIX", "HOME", "TMPDIR"}}
    env.update({"OMP_THREAD_LIMIT": "1", "LC_ALL": "C"})
    proc = subprocess.run(  # noqa: S603 - fixed argv, language from an allow-list
        [TESSERACT_BIN, image_path, "stdout", "-l", lang, "--dpi", str(dpi), "tsv"],
        capture_output=True,
        timeout=timeout,
        env=env,
        check=False,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout.decode("utf-8", errors="replace")


def parse_tsv(
    tsv: str, pixel_w: int, pixel_h: int
) -> tuple[str, float, tuple[tuple[float, float, float, float, str], ...]]:
    """Tesseract TSV to (text, mean confidence, normalised word boxes). Only level-5 rows with a word and conf >= 0 count."""
    words: list[tuple[float, float, float, float, str]] = []
    lines: list[list[str]] = []
    confs: list[float] = []
    current_key: tuple[str, str, str] | None = None
    for row in tsv.splitlines()[1:]:
        cols = row.split("\t")
        if len(cols) < 12 or cols[0] != "5":
            continue
        text = cols[11].strip()
        try:
            conf = float(cols[10])
            left, top, width, height = (int(cols[i]) for i in (6, 7, 8, 9))
        except ValueError:
            continue
        if not text or conf < 0 or width <= 0 or height <= 0:
            continue
        key = (cols[2], cols[3], cols[4])
        if key != current_key:
            lines.append([])
            current_key = key
        lines[-1].append(text)
        confs.append(conf)
        words.append(
            (
                round(min(max(left / pixel_w, 0.0), 1.0), 4),
                round(min(max(top / pixel_h, 0.0), 1.0), 4),
                round(min(width / pixel_w, 1.0), 4),
                round(min(height / pixel_h, 1.0), 4),
                text,
            )
        )
    text_out = "\n".join(" ".join(line) for line in lines)
    mean = round(sum(confs) / len(confs), 1) if confs else 0.0
    return text_out, mean, tuple(words)
