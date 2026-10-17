"""
The only impure file in `pdf_ingest`: reads a PDF and hands plain structures to the pure parsers.

* MCQ banks: table rows via pdfplumber (imported lazily, so the web app and the normal test run never need it).
* Workbooks: `pdftotext -layout` plus `pdfimages -list` from poppler (`brew install poppler`). Tables are rebuilt from the
  column gaps in `text.layout_to_markdown`, because pdfplumber's table finder dropped the rupee sign and swallowed paragraphs.

Both are needed only by `build_question_bank_seed`; `load_question_bank_seed` reads the committed JSON and needs neither.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any


def _pdfplumber():
    try:
        import pdfplumber
    except ImportError as exc:  # pragma: no cover - only hit on machines without the optional dependency
        raise RuntimeError("pdfplumber is required to read PDFs: pip install pdfplumber") from exc
    return pdfplumber


def mcq_table_rows(path: Path) -> list[list[str | None]]:
    """Every table row of an MCQ bank PDF, in page order."""
    rows: list[list[str | None]] = []
    with _pdfplumber().open(path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                rows.extend(table)
    return rows


def _poppler(tool: str) -> str:
    path = shutil.which(tool)
    if not path:  # pragma: no cover - environment
        raise RuntimeError(
            f"{tool} (poppler) is required to read workbooks: brew install poppler / apt install poppler-utils"
        )
    return path


def workbook_pages(path: Path) -> list[dict[str, Any]]:
    """
    Pages as `{"page": n, "blocks": [...]}`: one layout-preserving text block per page plus any large images.

    pdftotext -layout is used on purpose. pdfplumber's table detection swallowed ordinary paragraphs and dropped the rupee
    glyph on these workbooks, and its layout text reordered cells; pdftotext keeps every character in reading order.
    Tables are rebuilt from column gaps by `text.layout_to_markdown`.
    """
    raw = subprocess.run(
        [_poppler("pdftotext"), "-layout", str(path), "-"], check=True, capture_output=True, text=True
    ).stdout
    texts = raw.split("\f")
    if texts and not texts[-1].strip():
        texts.pop()
    images: dict[int, list[tuple[float, float]]] = {}
    listing = subprocess.run([_poppler("pdfimages"), "-list", str(path)], check=True, capture_output=True, text=True)
    for line in listing.stdout.splitlines()[2:]:
        cols = line.split()
        if len(cols) > 4 and cols[0].isdigit() and cols[3].isdigit() and cols[4].isdigit():
            # pdfimages reports pixels; with the printed ppi column that is points. ppi is column 12/13 in newer poppler.
            images.setdefault(int(cols[0]), []).append((float(cols[3]), float(cols[4])))
    pages: list[dict[str, Any]] = []
    for number, text in enumerate(texts, start=1):
        blocks: list[dict[str, Any]] = []
        if text.strip():
            blocks.append({"type": "text", "text": text})
        for w, h in images.get(number, []):
            blocks.append(
                {"type": "image", "w": w / 3, "h": h / 3}
            )  # ~216 ppi scans: close enough to points for a size cut-off
        pages.append({"page": number, "blocks": blocks})
    return pages
