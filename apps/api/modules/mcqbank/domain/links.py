"""
Link safety and host allowlist checking (F-05 ERD 7).
"""

from __future__ import annotations

from urllib.parse import urlparse

from django.conf import settings

DEFAULT_ALLOWED_HOSTS = {
    "icai.nic.in",
    "icmai.in",
    "icsi.edu",
    "boslive.icai.org",
    "exam.icmai.in",
    "www.icai.org",
    "www.icmai.in",
    "www.icsi.edu",
}


def is_safe_linkout_url(url: str) -> bool:
    """Verifies that url is HTTPS and hostname matches allow-list."""
    if not url or not url.startswith("https://"):
        return False
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        allowed = getattr(settings, "MCQ_LINKOUT_HOSTS", DEFAULT_ALLOWED_HOSTS)
        return host in allowed or any(host.endswith("." + allowed_h) for allowed_h in allowed)
    except Exception:
        return False
