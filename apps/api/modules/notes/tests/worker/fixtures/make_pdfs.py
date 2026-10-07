"""
Generators for the PDF worker test fixtures. Nothing here is committed as a binary: every file is built into `tmp_path`
at test time with reportlab, Pillow and pikepdf, so the repository stays small and the cases are readable.
"""

from __future__ import annotations

import io
import shutil
from pathlib import Path

import pikepdf
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4, letter
from reportlab.pdfgen import canvas

LINE = "Input tax credit under GST is available on inward supplies"


def text_pdf(path: Path, pages: int = 3, *, line: str = LINE) -> Path:
    c = canvas.Canvas(str(path), pagesize=A4)
    for n in range(1, pages + 1):
        c.setFont("Helvetica", 14)
        c.drawString(72, 760, f"Page {n}. {line}")
        c.drawString(72, 720, "Chapter heading and a second line of ordinary text for the extractor.")
        c.showPage()
    c.save()
    return path


def many_pages_pdf(path: Path, pages: int = 1000) -> Path:
    c = canvas.Canvas(str(path), pagesize=letter)
    for n in range(1, pages + 1):
        c.setFont("Helvetica", 10)
        for row in range(10):
            c.drawString(72, 700 - row * 14, f"Page {n} row {row} " + "lorem ipsum dolor sit amet " * 4)
        c.showPage()
    c.save()
    return path


def _dejavu() -> str | None:
    for candidate in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ):
        if Path(candidate).is_file():
            return candidate
    return None


def scanned_pdf(path: Path, pages: int = 2, *, lines=("INPUT TAX CREDIT", "GOODS AND SERVICES TAX")) -> Path:
    """Image-only pages: text rendered into a bitmap at 200 dpi (A4) and placed as a full-page picture."""
    c = canvas.Canvas(str(path), pagesize=A4)
    font_path = _dejavu()
    for _ in range(pages):
        img = Image.new("L", (1654, 2339), 255)
        draw = ImageDraw.Draw(img)
        font = ImageFont.truetype(font_path, 70) if font_path else ImageFont.load_default()
        for i, text in enumerate(lines):
            draw.text((150, 250 + i * 140), text, fill=0, font=font)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        from reportlab.lib.utils import ImageReader

        c.drawImage(ImageReader(buf), 0, 0, width=A4[0], height=A4[1])
        c.showPage()
    c.save()
    return path


def encrypted_pdf(path: Path, src: Path, *, user: str = "secret", owner: str = "owner-secret", **allow) -> Path:
    with pikepdf.open(src) as pdf:
        permissions = pikepdf.Permissions(**allow) if allow else pikepdf.Permissions()
        pdf.save(path, encryption=pikepdf.Encryption(user=user, owner=owner, allow=permissions))
    return path


def owner_only_pdf(path: Path, src: Path) -> Path:
    return encrypted_pdf(path, src, user="", owner="owner-secret", extract=False, modify_other=False, print_lowres=True)


def truncated_pdf(path: Path, src: Path, keep: float = 0.45) -> Path:
    data = src.read_bytes()
    path.write_bytes(data[: int(len(data) * keep)])
    return path


def polyglot_pdf(path: Path, src: Path, junk: int = 2048) -> Path:
    path.write_bytes(b"GIF89a" + b"\x00" * junk + src.read_bytes())
    return path


def pdf_with_outline(path: Path, src: Path) -> Path:
    with pikepdf.open(src) as pdf:
        with pdf.open_outline() as outline:
            ch1 = pikepdf.OutlineItem("Chapter 1", 0)
            ch1.children.append(pikepdf.OutlineItem("Section 1.1", 1))
            outline.root.extend([ch1, pikepdf.OutlineItem("Chapter 2", 2)])
        pdf.save(path)
    return path


def pdf_with_javascript(path: Path, src: Path) -> Path:
    with pikepdf.open(src) as pdf:
        pdf.Root.OpenAction = pikepdf.Dictionary(S=pikepdf.Name.JavaScript, JS=pikepdf.String("app.alert('hi');"))
        pdf.save(path)
    return path


def huge_page_pdf(path: Path, width: float = 15000, height: float = 200) -> Path:
    with pikepdf.new() as pdf:
        pdf.add_blank_page(page_size=(100, 100))
        pdf.pages[0].obj.MediaBox = [0, 0, width, height]  # add_blank_page refuses sizes over 14,400
        pdf.save(path)
    return path


# The probe text sits in the upper left of an unrotated Letter page, so a wrong rotation shows up as a wrong place.
PROBE = "PROBE TEXT"


def rotated_pdf(path: Path, rotation: int, *, cropbox: tuple[float, float, float, float] | None = None) -> Path:
    base = path.with_suffix(".base.pdf")
    c = canvas.Canvas(str(base), pagesize=letter)
    c.setFont("Helvetica-Bold", 36)
    c.drawString(80, 650, PROBE)
    c.showPage()
    c.save()
    with pikepdf.open(base) as pdf:
        pdf.pages[0].obj.Rotate = rotation
        if cropbox:
            pdf.pages[0].obj.CropBox = list(cropbox)
        pdf.save(path)
    base.unlink()
    return path


def copy(src: Path, dst: Path) -> Path:
    shutil.copyfile(src, dst)
    return dst
