"""
Tests for ICMAI Study Material Paper-Book ingestion.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from modules.material.domain.book_ingest import ingest_paper_book, resolve_source_path
from modules.material.models import Edition, Work
from modules.syllabus.tests.helpers import make_scheme


@pytest.mark.django_db
def test_ingest_paper_book():
    scheme = make_scheme()
    b = resolve_source_path("Docs/source-material/study-material/icmai/cma/final/Paper-Books/Paper_13_CORPORATE_AND_ECONOMIC_LAWS.pdf")
    if not b.exists():
        pytest.skip("Paper book PDF not found.")

    work = ingest_paper_book(b)
    assert work is not None
    assert work.provider.slug == "icmai"
    assert "Paper 13" in work.title
    assert work.editions.count() == 1

    ed = work.editions.first()
    assert ed.status == Edition.Status.CURRENT
    assert "study-material" in ed.source_url


def test_find_all_paper_books():
    from modules.material.domain.book_ingest import find_all_paper_books
    books = find_all_paper_books("Docs/source-material/study-material")
    assert len(books) >= 15
    for b in books:
        assert b.exists()
        assert b.name.endswith(".pdf")
