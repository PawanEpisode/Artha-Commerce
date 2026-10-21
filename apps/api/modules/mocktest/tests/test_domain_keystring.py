"""
Tests for key string parsing.
"""

from modules.mocktest.domain import keystring


def test_parse_key_string_hyphenated():
    raw = "1-A 2-C 3-B 4-D 5-A"
    res = keystring.parse_key_string(raw)
    assert len(res) == 5
    assert res[0] == {"position": 1, "key": "A"}
    assert res[1] == {"position": 2, "key": "C"}
    assert res[2] == {"position": 3, "key": "B"}
    assert res[3] == {"position": 4, "key": "D"}
    assert res[4] == {"position": 5, "key": "A"}


def test_parse_key_string_dot_and_newlines():
    raw = """
    1. A
    2. C
    3. B
    """
    res = keystring.parse_key_string(raw)
    assert len(res) == 3
    assert res[0] == {"position": 1, "key": "A"}
    assert res[1] == {"position": 2, "key": "C"}
    assert res[2] == {"position": 3, "key": "B"}
