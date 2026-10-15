"""
Link safety and allow-list checking for official past-paper links (F-09 ERD 7).
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

DEFAULT_ALLOWED_HOSTS = [
    "icai.org",
    "www.icai.org",
    "boslive.icai.org",
    "icmai.in",
    "www.icmai.in",
    "icsi.edu",
    "www.icsi.edu",
    "arthacommerce.com",
    "localhost",
    "127.0.0.1",
]


def get_allowed_hosts() -> list[str]:
    custom = os.environ.get("PYQ_LINKOUT_HOSTS", "").strip()
    if custom:
        hosts = [h.strip() for h in custom.split(",") if h.strip()]
        return [*DEFAULT_ALLOWED_HOSTS, *hosts]
    return DEFAULT_ALLOWED_HOSTS


def validate_paper_link(url: str) -> tuple[bool, str, str]:
    """
    Validates that a URL is HTTPS and points to an allowed host.
    Returns (is_valid, host, error_message).
    """
    if not url.startswith("https://"):
        return False, "", "Only HTTPS links are permitted."

    parsed = urlparse(url)
    host = parsed.netloc.lower().split(":")[0]
    allowed = get_allowed_hosts()

    if host not in allowed and not any(host.endswith("." + a) for a in allowed if "." in a):
        return False, host, f"Host '{host}' is not on the PYQ link allow-list."

    return True, host, ""
