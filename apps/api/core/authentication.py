"""Verifies Supabase-issued JWTs. The API trusts the signature, never the client."""

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import jwt
from django.conf import settings
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed


@dataclass(frozen=True)
class SupabaseUser:
    """Lightweight request.user. The durable record lives in modules.profiles.Profile."""

    id: str
    email: str = ""
    claims: dict[str, Any] = field(default_factory=dict, repr=False)
    is_authenticated: bool = True

    @property
    def pk(self) -> str:  # DRF throttling keys on request.user.pk
        return self.id


REAUTH_MAX_AGE_SECONDS = 600


def recent_authentication(claims: dict[str, Any], *, now: float, max_age: int = REAUTH_MAX_AGE_SECONDS) -> bool:
    """
    True when the token proves the student authenticated (password, magic link or emailed code) within `max_age`
    seconds. Supabase lists every method used for the session in `amr` with a timestamp; a refresh keeps the original
    entries, so only a real sign-in or the reauthentication code makes this true. `[VERIFY]` against production tokens.
    """
    for entry in claims.get("amr") or []:
        stamp = entry.get("timestamp") if isinstance(entry, dict) else None
        if isinstance(stamp, (int, float)) and 0 <= now - stamp <= max_age:
            return True
    return False


@lru_cache(maxsize=1)
def _jwks_client() -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json", cache_keys=True, lifespan=3600)


def decode_token(token: str) -> dict[str, Any]:
    options = {"require": ["exp", "sub"]}
    try:
        alg = jwt.get_unverified_header(token).get("alg", "")
        if alg == "HS256":
            if not settings.SUPABASE_JWT_SECRET:
                raise AuthenticationFailed("HS256 tokens are not accepted: SUPABASE_JWT_SECRET is not configured.")
            return jwt.decode(
                token, settings.SUPABASE_JWT_SECRET, algorithms=["HS256"], audience="authenticated", options=options
            )
        key = _jwks_client().get_signing_key_from_jwt(token).key
        return jwt.decode(token, key, algorithms=["ES256", "RS256"], audience="authenticated", options=options)
    except jwt.PyJWTError as exc:
        raise AuthenticationFailed("Invalid or expired token.") from exc


class SupabaseJWTAuthentication(BaseAuthentication):
    keyword = b"bearer"

    def authenticate(self, request):
        parts = get_authorization_header(request).split()
        if not parts or parts[0].lower() != self.keyword:
            return None
        if len(parts) != 2:
            raise AuthenticationFailed("Malformed Authorization header.")
        claims = decode_token(parts[1].decode())
        return SupabaseUser(id=claims["sub"], email=claims.get("email", ""), claims=claims), None

    def authenticate_header(self, request):
        return "Bearer"
