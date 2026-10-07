"""
Email clients do not support CSS variables, so the weekly email uses fixed hex values. They mirror
`packages/email-templates/src/brand.ts` (the sanctioned exception to "no raw hex"); a test reads that file and fails
when the two drift apart.
"""

from __future__ import annotations

NAME = "ArthaCommerce"
TAGLINE = "Exam preparation for CA, CS and CMA"

LIGHT = {
    "page": "#f7f0dd",
    "card": "#fcf6e9",
    "text": "#2b2018",
    "muted": "#605245",
    "border": "#ddd3bf",
    "primary": "#3643ae",
    "onPrimary": "#fbf8f1",
    "codeBg": "#efe5d0",
}
DARK = {
    "page": "#090d18",
    "card": "#101524",
    "text": "#f3f2ec",
    "muted": "#9ea5b2",
    "border": "#272d3d",
    "primary": "#738cff",
    "onPrimary": "#090d18",
    "codeBg": "#1a2133",
}
