"""
Which push services the server is willing to call. A student sends us the push URL, and we later POST to it from our
network, so an unchecked URL would be a server-side request forgery (SSRF) hole. Only https, port 443, no credentials
in the URL, and a host that is exactly a known push service (or a subdomain of one that hosts many).

Pure: parsing and comparison only. No DNS lookups (an allow-listed name is the control, not the address it resolves to).
"""

from __future__ import annotations

from urllib.parse import urlsplit

MAX_ENDPOINT_LENGTH = 2048

#: Exact host names: Google (Chrome, Edge on Android and desktop) and Mozilla (Firefox).
EXACT_HOSTS = frozenset({"fcm.googleapis.com", "updates.push.services.mozilla.com", "web.push.apple.com"})
#: Services that give each subscription a subdomain. A match needs at least one label before the suffix.
HOST_SUFFIXES = (".push.apple.com", ".notify.windows.com")


class EndpointRejected(ValueError):
    """The push URL is not one we will call."""


def _has_unsafe_characters(url: str) -> bool:
    return any(ord(char) <= 32 or ord(char) == 127 for char in url) or "\\" in url


def _host_allowed(host: str) -> bool:
    if host in EXACT_HOSTS:
        return True
    return any(host.endswith(suffix) and len(host) > len(suffix) for suffix in HOST_SUFFIXES)


def validate_endpoint(url: object) -> str:
    """Returns `url` unchanged when it may be called; raises `EndpointRejected` otherwise."""
    if not isinstance(url, str) or not url or len(url) > MAX_ENDPOINT_LENGTH:
        raise EndpointRejected("The push address must be a non-empty string of at most 2048 characters.")
    if _has_unsafe_characters(url):
        raise EndpointRejected("The push address contains spaces, control characters or a backslash.")
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise EndpointRejected("The push address is not a valid URL.") from None
    if parts.scheme != "https":
        raise EndpointRejected("The push address must use https.")
    if "@" in parts.netloc or parts.username is not None or parts.password is not None:
        raise EndpointRejected("The push address may not carry credentials.")
    if port not in (None, 443):
        raise EndpointRejected("The push address may not use a custom port.")
    host = parts.hostname or ""
    if not host.isascii() or host.endswith(".") or not _host_allowed(host):
        raise EndpointRejected("That push service is not supported.")
    return url


def is_allowed_endpoint(url: object) -> bool:
    try:
        validate_endpoint(url)
    except EndpointRejected:
        return False
    return True
