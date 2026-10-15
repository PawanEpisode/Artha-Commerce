from decimal import Decimal

from modules.questionbank.domain.numeric import parse_indian_number


def test_parses_plain_integers_and_decimals():
    assert parse_indian_number("100") == Decimal("100")
    assert parse_indian_number("100.5") == Decimal("100.5")
    assert parse_indian_number("0") == Decimal("0")
    assert parse_indian_number("0.0") == Decimal("0.0")
    assert parse_indian_number(".75") == Decimal("0.75")


def test_parses_indian_grouping():
    assert parse_indian_number("1,25,000") == Decimal("125000")
    assert parse_indian_number("1,25,00,000") == Decimal("12500000")
    assert parse_indian_number("10,00,000.50") == Decimal("1000000.50")


def test_parses_international_grouping():
    assert parse_indian_number("125,000") == Decimal("125000")
    assert parse_indian_number("1,125,000.25") == Decimal("1125000.25")


def test_handles_currency_symbols_and_prefixes():
    assert parse_indian_number("₹ 1,25,000") == Decimal("125000")
    assert parse_indian_number("Rs. 450") == Decimal("450")
    assert parse_indian_number("Rs 500.50") == Decimal("500.50")
    assert parse_indian_number("INR 1000") == Decimal("1000")
    assert parse_indian_number("1000 INR") == Decimal("1000")
    assert parse_indian_number("500 ₹") == Decimal("500")


def test_handles_percentage():
    assert parse_indian_number("12.5%") == Decimal("12.5")
    assert parse_indian_number("18 %") == Decimal("18")


def test_handles_negative_formats():
    assert parse_indian_number("-500") == Decimal("-500")
    assert parse_indian_number("(500)") == Decimal("-500")
    assert parse_indian_number("( 1,25,000 )") == Decimal("-125000")
    assert parse_indian_number("(0)") == Decimal("0")
    # Multiple negative indicators are invalid
    assert parse_indian_number("(-500)") is None
    assert parse_indian_number("--500") is None


def test_rejects_more_than_six_decimals():
    assert parse_indian_number("1.123456") == Decimal("1.123456")
    assert parse_indian_number("1.1234567") is None


def test_rejects_words():
    assert parse_indian_number("5 lakh") is None
    assert parse_indian_number("2 crore") is None
    assert parse_indian_number("1 million") is None
    assert parse_indian_number("10 thousand") is None
    assert parse_indian_number("10k") is None


def test_rejects_malformed_input():
    assert parse_indian_number("") is None
    assert parse_indian_number("   ") is None
    assert parse_indian_number("abc") is None
    assert parse_indian_number("1,23,4567") is None  # invalid comma grouping
    assert parse_indian_number("1.2.3") is None
    assert parse_indian_number(None) is None  # type: ignore[arg-type]
