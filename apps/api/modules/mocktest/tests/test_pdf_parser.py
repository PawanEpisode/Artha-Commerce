"""
Tests for MQP and PTP PDF parser.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from modules.mocktest.domain.pdf_parser import parse_mqp_pair, parse_ptp, resolve_source_path


def test_parse_mqp_pair():
    q = resolve_source_path("Docs/source-material/mock-tests/cma/final/Model Question Paper (MQP)- Paper13/June_26/MQP_Paper_13_Syllabus_2022_June2026_Set_1.pdf")
    a = resolve_source_path("Docs/source-material/mock-tests/cma/final/Model Question Paper (MQP)- Paper13/June_26/MQP_Answer_Paper_13_Syllabus2022_June2026_Set_1.pdf")

    if not q.exists() or not a.exists():
        pytest.skip("PDF files not found in workspace.")

    data = parse_mqp_pair(q, a)

    assert "CMA Final" in data["title"]
    assert "Paper 13" in data["title"]
    assert data["course_code"] == "cma"
    assert data["level_code"] == "final"
    assert data["subject_key"] == "corporate-and-economic-laws"
    assert len(data["sections"]) == 2

    # Section A has MCQs
    sec_a = data["sections"][0]
    assert sec_a["kind"] == "objective"
    assert len(sec_a["items"]) == 15
    first_mcq = sec_a["items"][0]
    assert first_mcq["marks"] == 2
    assert len(first_mcq["question"]["options"]) == 4
    # Check that answer key and explanation were extracted
    assert any(opt["is_correct"] for opt in first_mcq["question"]["options"])
    assert len(first_mcq["question"]["explanation_md"]) > 0

    # Section B has descriptive questions
    sec_b = data["sections"][1]
    assert sec_b["kind"] == "descriptive"
    assert len(sec_b["items"]) > 0
    assert len(sec_b["choice_groups"]) == 1
    assert sec_b["choice_groups"][0]["required_count"] == 5

    # Check CDN URLs
    assert "mock-tests" in data["source_pdf_url"]
    assert "mock-tests" in data["solution_pdf_url"]


def test_parse_ptp():
    p = resolve_source_path("Docs/source-material/study-material/icmai/cma/final/Postal-Test-Paper/Postal-Test-Paper-Paper13.pdf")
    if not p.exists():
        pytest.skip("PTP file not found.")

    data = parse_ptp(p)
    assert "Postal Test Paper" in data["title"]
    assert data["course_code"] == "cma"
    assert len(data["sections"]) == 2
    assert len(data["sections"][0]["items"]) > 0


def test_find_all_mqp_pairs():
    from modules.mocktest.domain.pdf_parser import find_all_mqp_pairs
    pairs = find_all_mqp_pairs("Docs/source-material/mock-tests")
    assert len(pairs) >= 50
    for q, a in pairs[:10]:
        assert q.exists()
        assert a.exists()


def test_find_all_ptp_files():
    from modules.mocktest.domain.pdf_parser import find_all_ptp_files
    ptps = find_all_ptp_files("Docs/source-material")
    assert len(ptps) >= 15
    for p in ptps:
        assert p.exists()
        assert "postal" in p.name.lower()
