"""
Unit tests for domain label and provider normalisation (F-12 ERD 2.1, 2.6).
"""

from modules.material.domain import labels


def test_normalise_label():
    assert labels.normalise_label("Illustration 12") == "ill-12"
    assert labels.normalise_label("Ill. 12") == "ill-12"
    assert labels.normalise_label("Illustration-12") == "ill-12"
    assert labels.normalise_label("Q.7(a)") == "q-7a"
    assert labels.normalise_label("Question 7a") == "q-7a"
    assert labels.normalise_label("Example 3") == "ex-3"
    assert labels.normalise_label("Ex. 3") == "ex-3"
    assert labels.normalise_label("Exercise 4") == "exer-4"
    assert labels.normalise_label("TYK 5") == "tyk-5"
    assert labels.normalise_label("Test Your Knowledge 5") == "tyk-5"
    assert labels.normalise_label("Practical 2") == "practical-2"


def test_extract_ordinal():
    assert labels.extract_ordinal("Illustration 12") == 12
    assert labels.extract_ordinal("Q.7(a)") == 7
    assert labels.extract_ordinal("Example 3") == 3
    assert labels.extract_ordinal("No number") is None


def test_normalise_provider_name():
    assert labels.normalise_provider_name("XYZ Classes") == "xyz"
    assert labels.normalise_provider_name("XYZ Academy") == "xyz"
    assert labels.normalise_provider_name("XYZ Commerce Tutorials") == "xyz"
    assert labels.normalise_provider_name("ICAI") == "icai"
