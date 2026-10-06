"""Builders shared by the notification tests."""

import base64
import os
import uuid

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from modules.notifications.services import devices


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def make_keys() -> dict:
    """A real P-256 public key and 16-byte auth secret, as a browser would hand over."""
    key = ec.generate_private_key(ec.SECP256R1())
    public = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return {"p256dh": _b64(public), "auth": _b64(os.urandom(16))}


def make_endpoint(host="fcm.googleapis.com") -> str:
    return f"https://{host}/fcm/send/{uuid.uuid4().hex}"


def subscription(endpoint=None, keys=None) -> dict:
    return {"endpoint": endpoint or make_endpoint(), "keys": keys or make_keys()}


def register(user_id, endpoint=None, keys=None, **kwargs):
    keys = keys or make_keys()
    return devices.register_device(
        user_id, endpoint=endpoint or make_endpoint(), p256dh=keys["p256dh"], auth=keys["auth"], **kwargs
    )
