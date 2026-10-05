#!/usr/bin/env python3
"""Download the ICAI paper PDFs listed in docs/syllabus-sources/ca-pdf-links.json.

Run from the repo root:

    python scripts/download_ca_pdfs.py

Each file is saved as:

    docs/syllabus-sources/ca/<level>/<subject>/<filename-from-url>

Files that are already a valid PDF are skipped. Pass --force to download them again.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LINKS_PATH = REPO_ROOT / "docs" / "syllabus-sources" / "ca-pdf-links.json"
DEST_ROOT = REPO_ROOT / "docs" / "syllabus-sources" / "ca"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
TIMEOUT_SECONDS = 120


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--level",
        choices=("foundation", "intermediate", "final", "spom"),
        help="Download only this level. Default: every level in the links file.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download files that are already present.",
    )
    return parser.parse_args()


def load_links() -> dict:
    with LINKS_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def destinations(links: dict, level_filter: str | None) -> list[tuple[str, str, str, Path]]:
    rows: list[tuple[str, str, str, Path]] = []
    papers = links["papers"]
    levels = [level_filter] if level_filter else list(papers)
    for level in levels:
        for paper in papers[level]:
            subject = paper["subject"]
            for pdf in paper["pdfs"]:
                url = pdf["url"]
                filename = url.rstrip("/").rsplit("/", 1)[-1]
                if not filename.lower().endswith(".pdf"):
                    filename = f"{filename}.pdf"
                dest = DEST_ROOT / level / subject / filename
                rows.append((level, subject, url, dest))
    return rows


def is_pdf(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(5) == b"%PDF-"
    except OSError:
        return False


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    temporary = dest.with_suffix(dest.suffix + ".part")
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/pdf,*/*",
            "Referer": "https://www.icai.org/",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            first = response.read(5)
            if first != b"%PDF-":
                content_type = response.headers.get("Content-Type", "unknown")
                raise RuntimeError(f"response is not a PDF (Content-Type: {content_type})")
            with temporary.open("wb") as handle:
                handle.write(first)
                while True:
                    chunk = response.read(1024 * 64)
                    if not chunk:
                        break
                    handle.write(chunk)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    temporary.replace(dest)


def main() -> int:
    args = parse_args()
    rows = destinations(load_links(), args.level)
    failed: list[tuple[str, str]] = []
    downloaded = 0
    skipped = 0

    print(f"Downloading {len(rows)} PDF(s) into {DEST_ROOT}")
    for index, (level, subject, url, dest) in enumerate(rows, start=1):
        label = f"[{index}/{len(rows)}] {level}/{subject}/{dest.name}"
        if dest.exists() and is_pdf(dest) and not args.force:
            print(f"{label}  skipped (already downloaded)")
            skipped += 1
            continue
        print(f"{label}  downloading…")
        try:
            download(url, dest)
        except (urllib.error.URLError, TimeoutError, RuntimeError, OSError) as error:
            print(f"{label}  failed: {error}", file=sys.stderr)
            failed.append((url, str(error)))
            continue
        size_kb = dest.stat().st_size / 1024
        print(f"{label}  saved ({size_kb:.0f} KB)")
        downloaded += 1

    print(f"Done. downloaded={downloaded} skipped={skipped} failed={len(failed)}")
    if failed:
        print("Failed URLs:", file=sys.stderr)
        for url, error in failed:
            print(f"  {url}  ({error})", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
