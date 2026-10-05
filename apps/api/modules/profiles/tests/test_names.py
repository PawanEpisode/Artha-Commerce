import pytest

from modules.profiles.domain.names import InvalidName, first_name, normalize_name, suggested_name


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Aarav  Mehta ", "Aarav Mehta"),
        ("Aarav", "Aarav"),
        ("आरव मेहता", "आरव मेहता"),
        ("தமிழ் செல்வன்", "தமிழ் செல்வன்"),
        ("Café", "Café"),
        ("Café", "Café"),  # decomposed input is stored composed (NFC)
        ("A" * 60, "A" * 60),
        ("Aarav 🎓", "Aarav 🎓"),
        ("Nikhil‍K", "Nikhil‍K"),  # a zero-width joiner is legitimate in Indic scripts
    ],
)
def test_valid_names_are_normalised(raw, expected):
    assert normalize_name(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "\t\n"])
def test_blank_names_are_refused(raw):
    with pytest.raises(InvalidName, match="Enter your name"):
        normalize_name(raw)


def test_a_name_over_sixty_characters_is_refused():
    with pytest.raises(InvalidName, match="60"):
        normalize_name("A" * 61)


@pytest.mark.parametrize("raw", ["Aa‮bb", "x⁦y", "a\x00b", "a\x07b", "line break", "a‎b"])
def test_control_and_bidi_override_characters_are_refused(raw):
    with pytest.raises(InvalidName):
        normalize_name(raw)


def test_first_name():
    assert first_name("Aarav Mehta") == "Aarav" and first_name("Aarav") == "Aarav" and first_name("") == ""


def test_the_suggestion_prefers_the_provider_name():
    assert suggested_name({"user_metadata": {"full_name": "Aarav Mehta"}}, "x@y.com") == "Aarav Mehta"
    assert suggested_name({"user_metadata": {"name": "Neha Rao"}}, "x@y.com") == "Neha Rao"


def test_the_suggestion_falls_back_to_a_readable_email_local_part():
    assert suggested_name({}, "aarav.mehta2@example.com") == "Aarav Mehta"
    assert suggested_name({}, "neha_rao@example.com") == "Neha Rao"
    assert suggested_name({}, "12345@example.com") == ""
    assert suggested_name({}, "") == ""


def test_an_unusable_provider_name_falls_through_to_the_email():
    claims = {"user_metadata": {"full_name": "bad‮name"}}
    assert suggested_name(claims, "sam@example.com") == "Sam"
