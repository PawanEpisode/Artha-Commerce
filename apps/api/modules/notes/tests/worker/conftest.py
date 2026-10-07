"""Fixtures for the PDF worker libraries: generated PDFs and a Noto font directory (found locally or downloaded once)."""

from __future__ import annotations

import os
import shutil
import subprocess
import urllib.request
from pathlib import Path

import pytest

from .fixtures import make_pdfs as mk

NOTO_BASE = "https://raw.githubusercontent.com/notofonts/notofonts.github.io/main/fonts"
NOTO_FILES = {
    "NotoSans-Regular.ttf": f"{NOTO_BASE}/NotoSans/hinted/ttf/NotoSans-Regular.ttf",
    "NotoSans-Bold.ttf": f"{NOTO_BASE}/NotoSans/hinted/ttf/NotoSans-Bold.ttf",
    "NotoSansDevanagari-Regular.ttf": f"{NOTO_BASE}/NotoSansDevanagari/hinted/ttf/NotoSansDevanagari-Regular.ttf",
    "NotoSansDevanagari-Bold.ttf": f"{NOTO_BASE}/NotoSansDevanagari/hinted/ttf/NotoSansDevanagari-Bold.ttf",
}
REQUIRED = ("NotoSans-Regular.ttf", "NotoSansDevanagari-Regular.ttf")
API_DIR = Path(__file__).resolve().parents[4]


def _has_fonts(directory: Path) -> bool:
    return all((directory / name).is_file() for name in REQUIRED)


@pytest.fixture(scope="session")
def fonts_dir(tmp_path_factory) -> Path:
    """First of: $WORKER_FONTS_DIR, the image's font dir, a repo cache, a download. Skips only when none is possible."""
    candidates = [
        os.environ.get("WORKER_FONTS_DIR", ""),
        "/usr/share/fonts/truetype/artha",
        str(Path.home() / ".cache" / "artha-test-fonts"),
        str(API_DIR / "worker" / "fonts"),
    ]
    for candidate in candidates:
        if candidate and _has_fonts(Path(candidate)):
            return Path(candidate)
    cache = Path.home() / ".cache" / "artha-test-fonts"
    try:
        cache.mkdir(parents=True, exist_ok=True)
        for name, url in NOTO_FILES.items():
            target = cache / name
            if not target.is_file():
                with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310 - fixed https URLs
                    target.write_bytes(response.read())
    except OSError:
        pytest.skip("Noto fonts are not installed and could not be downloaded (no network).")
    return cache


@pytest.fixture
def src_text(tmp_path) -> Path:
    return mk.text_pdf(tmp_path / "text.pdf")


@pytest.fixture
def make_rotated(tmp_path):
    def factory(rotation: int, **kw) -> Path:
        return mk.rotated_pdf(tmp_path / f"rot{rotation}.pdf", rotation, **kw)

    return factory


def tesseract_langs() -> set[str]:
    exe = shutil.which("tesseract")
    if exe is None:
        return set()
    out = subprocess.run([exe, "--list-langs"], capture_output=True, text=True, check=False).stdout
    return {line.strip() for line in out.splitlines()[1:] if line.strip()}
