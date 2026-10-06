"""
Encryption at rest for small secrets (push endpoints and keys), shared by any module that needs it.

- `EncryptedTextField` stores a Fernet token (authenticated encryption) and gives the plain text back in Python.
  It is write-only for lookups: ciphertext differs on every save, so never filter, order or index on it. Look rows up
  by a keyed hash instead (`hmac_hex`).
- Keys come from `FIELD_ENCRYPTION_KEYS`, a comma list. The first key encrypts; every key can decrypt, which makes
  rotation safe: prepend a new key, deploy, re-save rows, then drop the old key.
- `FIELD_HASH_PEPPER` keys the HMAC, so a database leak alone cannot confirm a guessed value.
"""

from __future__ import annotations

import hashlib
import hmac
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models


class DecryptionError(Exception):
    """A stored secret cannot be read with any configured key (wrong key, or the value was tampered with)."""


@lru_cache(maxsize=8)
def _fernet_for(keys: tuple[str, ...]) -> MultiFernet:
    try:
        return MultiFernet([Fernet(key.encode()) for key in keys])
    except ValueError as exc:  # a malformed key: fail loudly at first use, never store plain text
        raise ImproperlyConfigured("FIELD_ENCRYPTION_KEYS holds a key that is not a valid Fernet key.") from exc


def _fernet() -> MultiFernet:
    keys = tuple(settings.FIELD_ENCRYPTION_KEYS)
    if not keys:
        raise ImproperlyConfigured("FIELD_ENCRYPTION_KEYS is not set.")
    return _fernet_for(keys)


def encrypt_text(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_text(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise DecryptionError("Stored secret could not be decrypted with the configured keys.") from exc


def hmac_hex(value: str) -> str:
    """Stable 64-character lookup key for a secret value (keyed with `FIELD_HASH_PEPPER`)."""
    pepper = settings.FIELD_HASH_PEPPER
    if not pepper:
        raise ImproperlyConfigured("FIELD_HASH_PEPPER is not set.")
    return hmac.new(pepper.encode(), value.encode(), hashlib.sha256).hexdigest()


class EncryptedTextField(models.TextField):
    description = "Text encrypted at rest (Fernet)"

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        return None if value is None else encrypt_text(value)

    def from_db_value(self, value, expression, connection):
        return None if value is None else decrypt_text(value)
