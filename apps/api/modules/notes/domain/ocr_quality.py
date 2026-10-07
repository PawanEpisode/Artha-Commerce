"""
OCR quality and scanned-document detection (ERD 2.2, 2.3, 6.1), pure; the worker feeds it what Tesseract and the PDF
inspector measured.

- `page_confidence`: Tesseract reports a confidence per word and `-1` for layout boxes that are not words. The page score is
  the mean over real words, weighted by word length: a long word read wrongly says more about the page than a stray "a".
- `is_scanned`: a document is a scan when at least 70% of up to 20 sampled pages have under 20 extractable characters AND an
  image covering most of the page. Both conditions: a blank divider page has no text but no image, a text PDF with a logo
  has an image but plenty of text.
- `ocr_estimate_seconds`: the number shown in "About 25 minutes" before the student agrees (an assumption: re-measure with
  real files, ERD 6.1).
- `confidence_bucket`: the three words the UI and analytics use instead of a raw number.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

SECONDS_PER_PAGE = 6  # Tesseract on the worker, one page at 300 dpi; the PRD banner multiplies it by the page count
SAMPLE_PAGES = 20
SCANNED_SHARE_PERCENT = 70
SCANNED_MAX_CHARS = 20  # fewer extractable characters than this counts as "no text layer"
IMAGE_COVERAGE_MIN = 0.8  # share of the page area one image must cover to count as "the page is a picture"
HIGH_CONFIDENCE, MEDIUM_CONFIDENCE = 85, 60


def _word(item: Any) -> tuple[str, float]:
    if isinstance(item, Mapping):
        return str(item.get("text", "")), float(item.get("conf", -1))
    text, conf = item
    return str(text), float(conf)


def page_confidence(words: Iterable[Any]) -> int | None:
    """Mean word confidence 0 to 100 (whole number, half up) of `(text, conf)` pairs or `{text, conf}` dicts; None without words."""
    total = weight = 0.0
    for item in words:
        text, conf = _word(item)
        n = len(text.strip())
        if conf < 0 or n == 0:
            continue
        total += min(conf, 100.0) * n
        weight += n
    return None if weight == 0 else int(total / weight + 0.5)


def is_scanned(samples: Sequence[Mapping[str, float]]) -> bool | None:
    """
    `samples` are `{chars, image_coverage}` for the pages the inspector looked at (it picks up to 20, spread over the
    document); only the first 20 are used. None when nothing was sampled (an empty or locked file).
    """
    pages = list(samples)[:SAMPLE_PAGES]
    if not pages:
        return None
    scanned = sum(1 for p in pages if p["chars"] < SCANNED_MAX_CHARS and p["image_coverage"] >= IMAGE_COVERAGE_MIN)
    return scanned * 100 >= SCANNED_SHARE_PERCENT * len(pages)


def ocr_estimate_seconds(pages: int) -> int:
    return max(0, int(pages)) * SECONDS_PER_PAGE


def confidence_bucket(confidence: float | None) -> str:
    """`high`, `medium`, `low`, or `none` when there is no score (the page was not OCR'd)."""
    if confidence is None:
        return "none"
    if confidence >= HIGH_CONFIDENCE:
        return "high"
    return "medium" if confidence >= MEDIUM_CONFIDENCE else "low"
