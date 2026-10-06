from core.http import service_role_headers


def test_a_legacy_jwt_key_goes_in_both_headers():
    key = "aaa.bbb.ccc"
    assert service_role_headers(key) == {"apikey": key, "Authorization": f"Bearer {key}"}


def test_a_new_style_secret_key_is_not_sent_as_a_bearer_token():
    assert service_role_headers("sb_secret_abc123") == {"apikey": "sb_secret_abc123"}
