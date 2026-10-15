from decimal import Decimal

from modules.questionbank.domain.content import (
    compute_content_hash,
    extract_search_text,
    lint_explanation,
    lint_option,
    lint_stem,
)


def test_lint_stem_valid():
    assert lint_stem("What is the rate of GST on specified services?") == []


def test_lint_stem_rejects_empty():
    assert len(lint_stem("")) > 0
    assert len(lint_stem("   ")) > 0


def test_lint_stem_rejects_over_max_chars():
    long_stem = "a" * 20_001
    errors = lint_stem(long_stem)
    assert any("exceeds maximum length" in err for err in errors)


def test_lint_explanation_rules():
    # Long form requires explanation
    assert len(lint_explanation("", "long_form")) > 0
    # Public MCQ requires 60+ chars
    assert len(lint_explanation("Short expl", "mcq_single", is_public=True)) > 0
    valid_expl = (
        "This is a detailed explanation that clearly explains why the answer is correct and exceeds sixty characters."
    )
    assert lint_explanation(valid_expl, "mcq_single", is_public=True) == []


def test_lint_option_limits():
    assert lint_option("Option A", 0) == []
    assert len(lint_option("", 0)) > 0
    assert len(lint_option("x" * 2001, 0)) > 0


def test_extract_search_text():
    stem = "Calculate total depreciation under Section 32 of Income Tax Act."
    options = ["10%", "15%", "20%", "25%"]
    explanation = "Plant and machinery depreciation is 15%."

    stem_head, search_text = extract_search_text(stem, options, explanation)
    assert stem_head == stem[:300]
    assert "depreciation" in search_text
    assert "15%" in search_text


def test_compute_content_hash_deterministic():
    stem = "Question 1"
    opts = [{"position": 0, "body_md": "Opt A", "is_correct": True}]
    h1 = compute_content_hash(stem, opts, None, None, Decimal("1.0"))
    h2 = compute_content_hash(stem, opts, None, None, Decimal("1.0"))
    assert h1 == h2

    # Different marks -> different hash
    h3 = compute_content_hash(stem, opts, None, None, Decimal("2.0"))
    assert h1 != h3
