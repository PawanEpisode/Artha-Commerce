from modules.questionbank.domain.fingerprint import (
    compute_fp_exact,
    compute_fp_template,
    hamming_distance,
    normalise_for_fingerprint,
    simhash_64,
)


def test_normalise_removes_math_delimiters_and_latex_spacing():
    raw = "What is $\\text{ITC}$ under $Section\\,17(5)$?  $$x + y = 10$$"
    norm = normalise_for_fingerprint(raw)
    assert "$" not in norm
    assert "\\," not in norm
    assert "what is itc under section 17 5 x y 10" in norm


def test_fp_exact_is_deterministic_and_option_order_independent():
    stem = "Calculate total income for FY 2024-25"
    opts1 = ["Rs. 5,00,000", "Rs. 6,00,000", "Rs. 7,00,000"]
    opts2 = ["Rs. 7,00,000", "Rs. 5,00,000", "Rs. 6,00,000"]

    h1 = compute_fp_exact(stem, opts1, "500000")
    h2 = compute_fp_exact(stem, opts2, "500000")
    assert h1 == h2


def test_fp_template_replaces_numbers_with_hash():
    stem1 = "Company A bought goods worth 50,000"
    stem2 = "Company A bought goods worth 90,000"
    opts1 = ["GST 5000", "GST 9000"]
    opts2 = ["GST 8000", "GST 12000"]

    t1 = compute_fp_template(stem1, opts1)
    t2 = compute_fp_template(stem2, opts2)
    assert t1 == t2  # Both templates collapse numbers to #


def test_simhash_identical_text_has_zero_hamming_distance():
    text = "Under the Central Goods and Services Tax Act 2017 an input tax credit is allowed"
    h1 = simhash_64(text)
    h2 = simhash_64(text)
    assert hamming_distance(h1, h2) == 0


def test_simhash_near_text_has_small_hamming_distance():
    text1 = "In accordance with Section 16 of the Central Goods and Services Tax Act 2017 every registered person shall be entitled to take credit of input tax charged on supply"
    text2 = "In accordance with Section 16 of the Central Goods and Services Tax Act 2017 every registered person shall be entitled to take credit of input tax charged on supplies"
    h1 = simhash_64(text1)
    h2 = simhash_64(text2)
    dist = hamming_distance(h1, h2)
    assert dist <= 8


def test_simhash_distinct_text_has_large_hamming_distance():
    text1 = "Under the Central Goods and Services Tax Act input tax credit is allowed"
    text2 = "Auditing standard SA 230 requires documentation of audit procedures performed"
    h1 = simhash_64(text1)
    h2 = simhash_64(text2)
    dist = hamming_distance(h1, h2)
    assert dist > 10


def test_bands_match_on_near_duplicates_by_pigeonhole():
    # If two 64-bit hashes have Hamming distance <= 3, at least one 16-bit band MUST match by pigeonhole principle
    h = simhash_64("In accordance with Section 16 of Central Goods and Services Tax Act 2017")
    for flip_bits in [(0,), (10,), (25, 40), (5, 30, 55)]:
        h_near = h
        for bit in flip_bits:
            h_near ^= 1 << bit
        assert hamming_distance(h, h_near) <= 3
        bands_h = [(h >> (16 * i)) & 0xFFFF for i in range(4)]
        bands_near = [(h_near >> (16 * i)) & 0xFFFF for i in range(4)]
        assert any(b1 == b2 for b1, b2 in zip(bands_h, bands_near, strict=True))
