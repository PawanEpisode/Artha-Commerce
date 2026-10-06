import pytest
from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured

from core import fields

KEY_A, KEY_B = Fernet.generate_key().decode(), Fernet.generate_key().decode()


@pytest.fixture(autouse=True)
def _keys(settings):
    settings.FIELD_ENCRYPTION_KEYS = [KEY_A]
    settings.FIELD_HASH_PEPPER = "pepper-one"


def test_text_round_trips_and_the_stored_value_is_not_readable():
    token = fields.encrypt_text("https://push.example/endpoint/abc")
    assert "push.example" not in token
    assert fields.decrypt_text(token) == "https://push.example/endpoint/abc"


def test_every_encryption_is_different_but_decrypts_the_same():
    a, b = fields.encrypt_text("same"), fields.encrypt_text("same")
    assert a != b
    assert fields.decrypt_text(a) == fields.decrypt_text(b) == "same"


def test_rotation_new_key_encrypts_and_old_rows_still_open(settings):
    old = fields.encrypt_text("secret")
    settings.FIELD_ENCRYPTION_KEYS = [KEY_B, KEY_A]  # new key first
    assert fields.decrypt_text(old) == "secret"
    new = fields.encrypt_text("secret")
    settings.FIELD_ENCRYPTION_KEYS = [KEY_B]  # old key dropped
    assert fields.decrypt_text(new) == "secret"
    with pytest.raises(fields.DecryptionError):
        fields.decrypt_text(old)


def test_a_tampered_value_is_rejected():
    token = fields.encrypt_text("secret")
    with pytest.raises(fields.DecryptionError):
        fields.decrypt_text(token[:-4] + "AAAA")


def test_missing_or_malformed_configuration_fails_loudly(settings):
    settings.FIELD_ENCRYPTION_KEYS = []
    with pytest.raises(ImproperlyConfigured):
        fields.encrypt_text("x")
    settings.FIELD_ENCRYPTION_KEYS = ["not-a-key"]
    with pytest.raises(ImproperlyConfigured):
        fields.encrypt_text("x")
    settings.FIELD_HASH_PEPPER = ""
    with pytest.raises(ImproperlyConfigured):
        fields.hmac_hex("x")


def test_hmac_is_stable_keyed_and_fixed_length(settings):
    first = fields.hmac_hex("https://push.example/a")
    assert first == fields.hmac_hex("https://push.example/a")
    assert len(first) == 64
    assert first != fields.hmac_hex("https://push.example/b")
    settings.FIELD_HASH_PEPPER = "pepper-two"
    assert fields.hmac_hex("https://push.example/a") != first


def test_field_encrypts_on_write_and_decrypts_on_read_and_passes_none_through():
    field = fields.EncryptedTextField(null=True)
    assert field.get_prep_value(None) is None
    assert field.from_db_value(None, None, None) is None
    stored = field.get_prep_value("secret")
    assert stored != "secret"
    assert field.from_db_value(stored, None, None) == "secret"
