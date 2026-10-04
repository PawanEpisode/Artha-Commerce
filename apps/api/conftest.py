import time

import jwt
import pytest

SECRET = "test-secret-test-secret-test-secret-32b"


@pytest.fixture(autouse=True)
def _supabase_settings(settings):
    settings.SUPABASE_JWT_SECRET = SECRET
    settings.SECURE_SSL_REDIRECT = False


@pytest.fixture
def make_token():
    def _make(sub="3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11", **extra):
        payload = {
            "sub": sub,
            "aud": "authenticated",
            "exp": int(time.time()) + 600,
            "email": "student@example.com",
            **extra,
        }
        return jwt.encode(payload, SECRET, algorithm="HS256")

    return _make


@pytest.fixture
def auth_client(client, make_token):
    client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {make_token()}"
    return client
