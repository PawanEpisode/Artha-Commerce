"""
Avatar image pipeline, pure over bytes (ERD section 6). No Django, no I/O: bytes in, two WebP renditions out, or one
`ImageRejected` with a code the web turns into a sentence. Metadata never survives: nothing is copied to the output.
"""

from __future__ import annotations

import io
import warnings
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_INPUT_BYTES = 1_000_000
MAX_PIXELS = 25_000_000
MIN_SIDE = 128
LARGE = 512
SMALL = 128
QUALITY = 82
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
#: Behind transparent pixels. A neutral light grey reads on all four themes.
FLATTEN_COLOUR = (240, 240, 240)
#: A square is "close enough" within one percent, otherwise the middle square is cut out.
SQUARE_TOLERANCE = 0.01


class ImageRejected(ValueError):
    """`code` is one of `invalid_image`, `image_too_large`, `image_too_small`."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Renditions:
    large: bytes
    small: bytes


def _open(data: bytes) -> Image.Image:
    # A decompression bomb must be an error, not a warning, and the header check must come before any pixel decode.
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        try:
            image = Image.open(io.BytesIO(data))
            if image.format not in ALLOWED_FORMATS:
                raise ImageRejected("invalid_image")
            if getattr(image, "n_frames", 1) != 1:
                raise ImageRejected("invalid_image")
            width, height = image.size
            if width * height > MAX_PIXELS:
                raise ImageRejected("image_too_large")
            image.load()
        except ImageRejected:
            raise
        except (Image.DecompressionBombWarning, Image.DecompressionBombError):
            raise ImageRejected("image_too_large") from None
        except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
            raise ImageRejected("invalid_image") from None
    return image


def _square(image: Image.Image) -> Image.Image:
    width, height = image.size
    if abs(width - height) / max(width, height) <= SQUARE_TOLERANCE:
        return image
    side = min(width, height)
    left, top = (width - side) // 2, (height - side) // 2
    return image.crop((left, top, left + side, top + side))


def _flatten(image: Image.Image) -> Image.Image:
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        base = Image.new("RGB", rgba.size, FLATTEN_COLOUR)
        base.paste(rgba, mask=rgba.getchannel("A"))
        return base
    return image.convert("RGB")


def _encode(image: Image.Image, size: int) -> bytes:
    out = io.BytesIO()
    image.resize((size, size), Image.Resampling.LANCZOS).save(out, format="WEBP", quality=QUALITY, method=4)
    return out.getvalue()


def process_avatar(data: bytes) -> Renditions:
    image = _open(data)
    image = ImageOps.exif_transpose(image)  # also drops the orientation tag
    if min(image.size) < MIN_SIDE:
        raise ImageRejected("image_too_small")
    image = _flatten(_square(image))
    return Renditions(large=_encode(image, LARGE), small=_encode(image, SMALL))
