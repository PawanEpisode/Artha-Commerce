"""The avatar image pipeline: pure bytes in, renditions out, or one rejection code."""

import io

import pytest
from PIL import Image

from modules.profiles.domain import images
from modules.profiles.domain.images import ImageRejected, process_avatar


def encode(image: Image.Image, fmt="JPEG", **kwargs) -> bytes:
    out = io.BytesIO()
    image.save(out, format=fmt, **kwargs)
    return out.getvalue()


def solid(size=(600, 600), colour=(200, 40, 40), mode="RGB") -> Image.Image:
    return Image.new(mode, size, colour)


def decode(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


def test_makes_a_512_and_a_128_webp_square():
    result = process_avatar(encode(solid()))
    large, small = decode(result.large), decode(result.small)
    assert (large.format, large.size) == ("WEBP", (512, 512))
    assert (small.format, small.size) == ("WEBP", (128, 128))


@pytest.mark.parametrize("fmt", ["JPEG", "PNG", "WEBP"])
def test_accepts_the_three_formats(fmt):
    assert process_avatar(encode(solid(), fmt)).large


def test_a_non_square_photo_is_cut_to_its_middle_square():
    wide = Image.new("RGB", (800, 400), (0, 0, 255))
    wide.paste((255, 0, 0), (0, 0, 200, 400))  # left quarter red, cut away
    wide.paste((255, 0, 0), (600, 0, 800, 400))  # right quarter red, cut away
    centre = decode(process_avatar(encode(wide, "PNG")).large).convert("RGB")
    r, g, b = centre.getpixel((10, 256))
    assert b > 200 and r < 60  # still blue at the left edge of the square


def test_a_nearly_square_photo_is_only_resized():
    result = process_avatar(encode(solid((600, 603))))
    assert decode(result.large).size == (512, 512)


def test_exif_orientation_is_applied_and_no_metadata_survives():
    photo = Image.new("RGB", (300, 200), (10, 200, 10))
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 270: the file stores it sideways
    exif[0x010F] = "SecretCamera"
    exif[0x8825] = {1: "N", 2: (12.0, 0.0, 0.0)}  # GPS block
    data = encode(photo, "JPEG", exif=exif.tobytes())
    assert b"SecretCamera" in data
    result = process_avatar(data)
    for blob in (result.large, result.small):
        assert b"SecretCamera" not in blob and b"Exif" not in blob
        assert not decode(blob).info.get("exif")


def test_transparent_pixels_are_flattened_on_a_neutral_colour():
    transparent = Image.new("RGBA", (400, 400), (0, 0, 0, 0))
    pixel = decode(process_avatar(encode(transparent, "PNG")).large).convert("RGB").getpixel((256, 256))
    assert all(abs(c - 240) <= 3 for c in pixel)


def test_palette_png_with_transparency_works():
    palette = Image.new("P", (300, 300))
    palette.info["transparency"] = 0
    assert process_avatar(encode(palette, "PNG", transparency=0)).large


def test_too_small_is_refused_after_orientation():
    assert _code(encode(solid((127, 500)))) == "image_too_small"
    assert process_avatar(encode(solid((128, 128)))).large


def test_not_an_image_is_refused():
    assert _code(b"hello world") == "invalid_image"
    assert _code(b"") == "invalid_image"


def test_svg_is_refused():
    assert _code(b'<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300"/>') == "invalid_image"


def test_gif_is_refused_even_when_still():
    assert _code(encode(solid((300, 300)), "GIF")) == "invalid_image"


def test_an_animated_webp_is_refused():
    frames = [solid((300, 300), c) for c in ((255, 0, 0), (0, 255, 0))]
    data = encode(frames[0], "WEBP", save_all=True, append_images=frames[1:], duration=100)
    assert _code(data) == "invalid_image"


def test_a_truncated_file_is_refused():
    data = encode(solid((600, 600)), "PNG")
    assert _code(data[: len(data) // 2]) == "invalid_image"


def test_too_many_pixels_is_refused_before_decoding(monkeypatch):
    monkeypatch.setattr(images, "MAX_PIXELS", 100_000)
    assert _code(encode(solid((400, 400)), "PNG")) == "image_too_large"


def test_a_decompression_bomb_is_an_error_not_a_crash(monkeypatch):
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 10_000)
    assert _code(encode(solid((400, 400)), "PNG")) == "image_too_large"


def _code(data: bytes) -> str:
    with pytest.raises(ImageRejected) as caught:
        process_avatar(data)
    return caught.value.code
