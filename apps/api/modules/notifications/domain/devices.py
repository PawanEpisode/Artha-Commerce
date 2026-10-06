"""Pure facts about a browser subscription: whether its keys are well formed, and the label a student sees."""

from __future__ import annotations

import base64
import binascii

from .enums import DeviceBrowser, DevicePlatform, DisplayMode

MAX_LABEL_LENGTH = 80
P256DH_LENGTH = 65  # an uncompressed P-256 point: 0x04 followed by X and Y
AUTH_LENGTH = 16


class InvalidKeys(ValueError):
    """The subscription keys are not what a browser produces."""


def _b64url_decode(value: object) -> bytes:
    if not isinstance(value, str) or not value or len(value) > 256:
        raise InvalidKeys("A subscription key must be a short base64url string.")
    try:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (binascii.Error, ValueError):
        raise InvalidKeys("A subscription key must be base64url.") from None


def validate_keys(p256dh: object, auth: object) -> None:
    """Raises `InvalidKeys` unless both keys decode to the lengths the Web Push encryption needs."""
    public = _b64url_decode(p256dh)
    if len(public) != P256DH_LENGTH or public[0] != 4:
        raise InvalidKeys("The public key is not a P-256 point.")
    if len(_b64url_decode(auth)) != AUTH_LENGTH:
        raise InvalidKeys("The auth secret must be 16 bytes.")


_BROWSER_NAMES = {
    DeviceBrowser.CHROME: "Chrome",
    DeviceBrowser.EDGE: "Edge",
    DeviceBrowser.FIREFOX: "Firefox",
    DeviceBrowser.SAFARI: "Safari",
}
_PLATFORM_NAMES = {
    DevicePlatform.ANDROID: "Android",
    DevicePlatform.IOS: "iOS",
    DevicePlatform.WINDOWS: "Windows",
    DevicePlatform.MACOS: "Mac",
    DevicePlatform.LINUX: "Linux",
}


def derive_label(platform: str, browser: str, display_mode: str = DisplayMode.BROWSER) -> str:
    """For example "Chrome on Android", "Safari on iOS (installed app)". Built on the server from closed sets, never from free text."""
    browser_name = _BROWSER_NAMES.get(DeviceBrowser(browser), "Browser")
    platform_name = _PLATFORM_NAMES.get(DevicePlatform(platform))
    label = f"{browser_name} on {platform_name}" if platform_name else browser_name
    if display_mode in (DisplayMode.STANDALONE, DisplayMode.APP):
        label += " (installed app)"
    return label[:MAX_LABEL_LENGTH]
