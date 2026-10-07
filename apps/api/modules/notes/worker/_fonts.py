"""
Text for PDF overlays: HarfBuzz shaping plus embedded, subset TrueType fonts (Noto Sans and Noto Sans Devanagari).

Why not reportlab or a base-14 font: Devanagari needs shaping (conjuncts, reordered vowel signs, mark positioning) and
neither reportlab nor PDF's own text operators do that. We shape with HarfBuzz, write glyph ids with an Identity-H
Type0 font, and attach a ToUnicode map so the exported text stays selectable and searchable. Fonts are subset to the glyphs
actually used (`retain_gids` keeps ids stable, so shaping output can be written directly).
"""

from __future__ import annotations

import hashlib
import io
import os
import re
from dataclasses import dataclass
from pathlib import Path

import pikepdf
import uharfbuzz as hb
from fontTools import subset as ft_subset
from fontTools.ttLib import TTFont

FONT_FILES = {
    ("latin", False): "NotoSans-Regular.ttf",
    ("latin", True): "NotoSans-Bold.ttf",
    ("deva", False): "NotoSansDevanagari-Regular.ttf",
    ("deva", True): "NotoSansDevanagari-Bold.ttf",
}
REQUIRED_FONT_FILES = (FONT_FILES[("latin", False)], FONT_FILES[("deva", False)])
DEFAULT_FONTS_DIR = "/usr/share/fonts/truetype/artha"

_DEVA = re.compile(r"[ऀ-ॿ꣠-ꣿ]")
_JOINERS = "‌‍"


class FontsMissing(FileNotFoundError):
    """The Noto font files are not in the fonts directory."""


def default_fonts_dir() -> str:
    return os.environ.get("WORKER_FONTS_DIR", DEFAULT_FONTS_DIR)


@dataclass(frozen=True)
class Glyph:
    face: Face
    gid: int
    x: float  # pen position in points from the start of the line, before the glyph's own offset
    x_off: float
    y_off: float
    adj: float  # shaped advance minus the font's own advance, points (kerning); used for TJ adjustments


class Face:
    """One TrueType file: cmap, advances, a HarfBuzz font and the set of glyphs written so far."""

    def __init__(self, path: Path, resource_name: str):
        self.path = path
        self.resource_name = resource_name
        self.data = path.read_bytes()
        self.ttfont = TTFont(io.BytesIO(self.data), lazy=True)
        self.upem = int(self.ttfont["head"].unitsPerEm)
        self.cmap = self.ttfont.getBestCmap()
        self.hmtx = self.ttfont["hmtx"]
        self.order = self.ttfont.getGlyphOrder()
        self.hb_font = hb.Font(hb.Face(self.data))
        self.used: dict[int, str] = {}  # gid -> unicode text for the ToUnicode map
        self.font_object: pikepdf.Object | None = None

    def has(self, char: str) -> bool:
        return ord(char) in self.cmap

    def advance_units(self, gid: int) -> int:
        return self.hmtx[self.order[gid]][0]

    def shape(self, text: str, size: float) -> tuple[list[tuple[int, float, float, float, float]], float]:
        """Glyph tuples (gid, x_off, y_off, x_adv, kern_adj) in points and the total width. `text` is one script run."""
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.hb_font, buf, {"kern": True, "liga": True, "mark": True, "mkmk": True})
        k = size / self.upem
        starts = sorted({info.cluster for info in buf.glyph_infos})
        nxt = {c: (starts[i + 1] if i + 1 < len(starts) else len(text)) for i, c in enumerate(starts)}
        seen: set[int] = set()
        out: list[tuple[int, float, float, float, float]] = []
        total = 0.0
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions, strict=True):
            gid = info.codepoint
            cluster_text = "" if info.cluster in seen else text[info.cluster : nxt[info.cluster]]
            seen.add(info.cluster)
            self.used.setdefault(gid, cluster_text)
            if cluster_text and not self.used[gid]:
                self.used[gid] = cluster_text
            adv = pos.x_advance * k
            out.append((gid, pos.x_offset * k, pos.y_offset * k, adv, adv - self.advance_units(gid) * k))
            total += adv
        return out, total


class FontSet:
    """The four Noto faces of one export, loaded on first use, embedded once at the end."""

    def __init__(self, fonts_dir: str | os.PathLike):
        self.dir = Path(fonts_dir)
        for name in REQUIRED_FONT_FILES:
            if not (self.dir / name).is_file():
                raise FontsMissing(f"Font file {name} not found in {self.dir}.")
        self._faces: dict[tuple[str, bool], Face] = {}

    def face(self, script: str, bold: bool = False) -> Face:
        key = (script, bold)
        if key not in self._faces:
            path = self.dir / FONT_FILES[key]
            if not path.is_file():  # no bold file shipped: fall back to regular
                return self.face(script, False)
            self._faces[key] = Face(path, f"ArthaF{len(self._faces) + 1}")
        return self._faces[key]

    # --- runs and lines -----------------------------------------------------------------------------------------------

    def runs(self, text: str, bold: bool = False) -> list[tuple[Face, str]]:
        """Splits text into runs that each have one face. Neutral characters stay with the face before them."""
        latin, deva = self.face("latin", bold), self.face("deva", bold)
        result: list[tuple[Face, str]] = []
        current: Face | None = None
        for ch in text:
            if _DEVA.match(ch):
                face = deva
            elif ch in _JOINERS:
                face = current or deva
            elif ch.isspace() or not ch.isalpha():
                face = current or latin
                if not face.has(ch):
                    face = latin if latin.has(ch) else deva if deva.has(ch) else face
            else:
                face = latin
            if not face.has(ch) and ch not in _JOINERS:
                ch, face = ("?", latin) if not ch.isspace() else (" ", face)
            elif ch in _JOINERS and not face.has(ch):
                continue
            if result and result[-1][0] is face:
                result[-1] = (face, result[-1][1] + ch)
            else:
                result.append((face, ch))
            current = face
        return result

    def shape_text(self, text: str, size: float, bold: bool = False, x0: float = 0.0) -> tuple[list[Glyph], float]:
        glyphs: list[Glyph] = []
        x = x0
        for face, run in self.runs(text, bold):
            shaped, _ = face.shape(run, size)
            for gid, x_off, y_off, adv, adj in shaped:
                glyphs.append(Glyph(face, gid, x, x_off, y_off, adj))
                x += adv
        return glyphs, x - x0

    def width(self, text: str, size: float, bold: bool = False) -> float:
        total = 0.0
        for face, run in self.runs(text, bold):
            total += face.shape(run, size)[1]
        return total

    def wrap(self, text: str, size: float, max_width: float, bold: bool = False) -> list[str]:
        """Greedy word wrap on spaces; honours newlines; hard-breaks a word that is wider than the line."""
        lines: list[str] = []
        for paragraph in text.split("\n"):
            words = paragraph.split(" ")
            line = ""
            for word in words:
                candidate = word if not line else f"{line} {word}"
                if self.width(candidate, size, bold) <= max_width:
                    line = candidate
                    continue
                if line:
                    lines.append(line)
                    line = ""
                while word and self.width(word, size, bold) > max_width and len(word) > 1:
                    cut = len(word) - 1
                    while cut > 1 and self.width(word[:cut], size, bold) > max_width:
                        cut -= 1
                    lines.append(word[:cut])
                    word = word[cut:]
                line = word
            lines.append(line)
        return lines

    # --- content stream -----------------------------------------------------------------------------------------------

    @staticmethod
    def emit(glyphs: list[Glyph], size: float, x: float, y: float, text: str | None = None) -> str:
        """
        Operators drawing a shaped line with its baseline at (x, y) in the current space. Colour is set by the caller.
        With `text`, the line is wrapped in `/ActualText` so extraction returns the real characters even where shaping
        reordered or merged glyphs (a ToUnicode map is per glyph and cannot express that).
        """
        ops: list[str] = []
        group: list[Glyph] = []

        def flush() -> None:
            if not group:
                return
            first = group[0]
            items: list[str] = []
            for g in group:
                if items and abs(g.adj) > 1e-6:
                    items.append(_num(-g.adj / size * 1000))
                items.append(f"<{g.gid:04x}>")
            ops.append(
                f"BT /{first.face.resource_name} {_num(size)} Tf 1 0 0 1 {_num(x + first.x)} {_num(y)} Tm [{' '.join(items)}] TJ ET"
            )
            group.clear()

        for g in glyphs:
            if g.x_off or g.y_off:
                flush()
                ops.append(
                    f"BT /{g.face.resource_name} {_num(size)} Tf 1 0 0 1 {_num(x + g.x + g.x_off)} {_num(y + g.y_off)} Tm <{g.gid:04x}> Tj ET"
                )
                continue
            if group and (group[-1].face is not g.face):
                flush()
            group.append(g)
        flush()
        if text and ops:
            hex_text = ("\ufeff" + text).encode("utf-16-be").hex()
            return f"/Span << /ActualText <{hex_text}> >> BDC\n" + "\n".join(ops) + "\nEMC"
        return "\n".join(ops)

    def font_resources(self) -> dict[str, pikepdf.Object]:
        return {f.resource_name: f.font_object for f in self._faces.values() if f.font_object is not None}

    # --- embedding ------------------------------------------------------------------------------------------------------

    def prepare(self, pdf: pikepdf.Pdf) -> None:
        """Creates the (still empty) font objects so pages can reference them before the glyph set is final."""
        for face in self._faces.values():
            if face.font_object is None:
                face.font_object = pdf.make_indirect(pikepdf.Dictionary(Type=pikepdf.Name.Font))

    def embed_all(self, pdf: pikepdf.Pdf) -> None:
        for face in self._faces.values():
            if face.font_object is not None and face.used:
                _embed(pdf, face)


def _num(value: float) -> str:
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def _subset_bytes(face: Face) -> bytes:
    options = ft_subset.Options()
    options.retain_gids = True
    options.layout_features = []
    options.hinting = False
    options.notdef_outline = True
    options.name_IDs = [1, 2, 3, 4, 6]
    options.glyph_names = False
    options.drop_tables += ["DSIG", "GDEF", "GPOS", "GSUB", "kern"]
    font = TTFont(io.BytesIO(face.data))
    subsetter = ft_subset.Subsetter(options)
    subsetter.populate(gids=sorted(face.used) + [0])
    subsetter.subset(font)
    out = io.BytesIO()
    font.save(out)
    return out.getvalue()


def _to_unicode_cmap(used: dict[int, str]) -> bytes:
    entries = []
    for gid, text in sorted(used.items()):
        # a glyph that is only part of a cluster (a reordered vowel sign, a half form) maps to nothing: the cluster's text
        # is carried by its first glyph, and an unmapped glyph would extract as a random character
        entries.append(f"<{gid:04x}> <{text.encode('utf-16-be').hex()}>")
    blocks = []
    for i in range(0, len(entries), 100):
        chunk = entries[i : i + 100]
        blocks.append(f"{len(chunk)} beginbfchar\n" + "\n".join(chunk) + "\nendbfchar")
    body = "\n".join(blocks)
    cmap = (
        "/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n"
        "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
        "/CMapName /Adobe-Identity-UCS def\n/CMapType 2 def\n"
        f"1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n{body}\nendcmap\n"
        "CMapName currentdict /CMap defineresource pop\nend\nend\n"
    )
    return cmap.encode("ascii")


def _embed(pdf: pikepdf.Pdf, face: Face) -> None:
    digest = hashlib.sha1(face.path.name.encode()).digest()
    tag = "".join(chr(65 + digest[i] % 26) for i in range(6))
    base = f"{tag}+{face.path.stem}"
    data = _subset_bytes(face)
    file_stream = pdf.make_stream(data)
    file_stream.Length1 = len(data)
    head, hhea = face.ttfont["head"], face.ttfont["hhea"]
    k = 1000 / face.upem
    descriptor = pdf.make_indirect(
        pikepdf.Dictionary(
            Type=pikepdf.Name.FontDescriptor,
            FontName=pikepdf.Name("/" + base),
            Flags=4,
            FontBBox=[round(head.xMin * k), round(head.yMin * k), round(head.xMax * k), round(head.yMax * k)],
            ItalicAngle=0,
            Ascent=round(hhea.ascent * k),
            Descent=round(hhea.descent * k),
            CapHeight=round(hhea.ascent * k * 0.7),
            StemV=80,
            FontFile2=file_stream,
        )
    )
    widths = pikepdf.Array()
    for gid in sorted(face.used):
        widths.append(gid)
        widths.append(pikepdf.Array([round(face.advance_units(gid) * k)]))
    descendant = pdf.make_indirect(
        pikepdf.Dictionary(
            Type=pikepdf.Name.Font,
            Subtype=pikepdf.Name.CIDFontType2,
            BaseFont=pikepdf.Name("/" + base),
            CIDSystemInfo=pikepdf.Dictionary(
                Registry=pikepdf.String("Adobe"), Ordering=pikepdf.String("Identity"), Supplement=0
            ),
            FontDescriptor=descriptor,
            CIDToGIDMap=pikepdf.Name.Identity,
            DW=1000,
            W=widths,
        )
    )
    font = face.font_object
    font.Subtype = pikepdf.Name.Type0
    font.BaseFont = pikepdf.Name("/" + base)
    font.Encoding = pikepdf.Name("/Identity-H")
    font.DescendantFonts = pikepdf.Array([descendant])
    font.ToUnicode = pdf.make_stream(_to_unicode_cmap(face.used))
