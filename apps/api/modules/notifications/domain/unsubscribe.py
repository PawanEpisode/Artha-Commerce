"""
Signed one-click unsubscribe tokens (X-01.1 W3.5). Stateless: the token carries the student and the category, signed
with a server secret, so a link in an email works without a login and nothing is stored. It does not expire, because
an old email must still be able to switch the emails off. Pure: the secret is an argument.
"""

from __future__ import annotations

import base64
import hashlib
import hmac

_SIG_BYTES = 16
_PURPOSE = b"notifications-unsubscribe:v1:"


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(secret: str, payload: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), _PURPOSE + payload, hashlib.sha256).digest()
    return _b64(digest[:_SIG_BYTES])


def make_token(secret: str, *, user_id: str, category: str) -> str:
    payload = f"{user_id}|{category}".encode()
    return f"{_b64(payload)}.{_sign(secret, payload)}"


def read_token(secret: str, token: str) -> tuple[str, str] | None:
    """The (user_id, category) a token was made for, or None when it is malformed or was not signed with `secret`."""
    try:
        encoded, signature = token.split(".", 1)
        payload = _unb64(encoded)
        text = payload.decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
    if not hmac.compare_digest(signature, _sign(secret, payload)):
        return None
    user_id, separator, category = text.partition("|")
    if not separator or not user_id or not category:
        return None
    return user_id, category
