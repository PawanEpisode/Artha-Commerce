"""Avatar rules. The preset artwork is static SVG in the design system; the keys below must match its manifest."""

PRESET_COUNT = 24
PRESET_KEYS = tuple(f"p{n:02d}" for n in range(1, PRESET_COUNT + 1))

KIND_INITIALS = "initials"
KIND_PRESET = "preset"
KIND_UPLOAD = "upload"


def is_preset_key(key: str) -> bool:
    return key in PRESET_KEYS
