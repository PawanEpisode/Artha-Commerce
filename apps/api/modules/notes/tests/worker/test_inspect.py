"""inspect_pdf: structure, permissions, scanned detection, error codes, bounded memory."""

import subprocess
import sys

import pypdfium2 as pdfium

from modules.notes.worker import pdfutil
from modules.notes.worker.inspect import inspect_pdf, sample_indices, scanned_verdict

from .conftest import API_DIR
from .fixtures import make_pdfs as mk


def test_text_pdf_is_readable_and_not_scanned(src_text):
    r = inspect_pdf(src_text)
    assert r.ok and r.error_code is None
    assert (r.page_count, len(r.page_meta)) == (3, 3)
    assert r.page_meta[0] == {"w": 595.28, "h": 841.89}
    assert (r.is_encrypted, r.needs_password, r.can_copy, r.can_modify) == (False, False, True, True)
    assert r.is_scanned is False and r.text_pct == 100
    assert r.sha256 == pdfutil.sha256_file(src_text) and r.bytes == src_text.stat().st_size
    assert r.has_javascript is False and r.outline == ()
    assert r.engine_version.startswith("pikepdf ")


def test_cover_is_a_240px_wide_webp(src_text):
    cover = inspect_pdf(src_text).cover_webp
    assert cover is not None and cover[:4] == b"RIFF" and cover[8:12] == b"WEBP"
    from io import BytesIO

    from PIL import Image

    assert Image.open(BytesIO(cover)).size[0] == 240


def test_scanned_pdf_is_detected(tmp_path):
    r = inspect_pdf(mk.scanned_pdf(tmp_path / "scan.pdf", pages=3))
    assert r.ok and r.is_scanned is True and r.text_pct == 0


def test_scanned_verdict_rule():
    assert scanned_verdict([(0, True)] * 7 + [(500, False)] * 3) == (True, 30)
    assert scanned_verdict([(0, True)] * 6 + [(500, False)] * 4)[0] is False  # 60% is under the 70% bar
    assert scanned_verdict([(0, False)] * 10)[0] is False  # blank pages are not pictures of text
    assert scanned_verdict([]) == (False, 0)


def test_sampling_is_even_and_capped():
    assert sample_indices(1, 20) == [0]
    assert sample_indices(5, 20) == [0, 1, 2, 3, 4]
    picks = sample_indices(1000, 20)
    assert len(picks) == 20 and picks[0] == 0 and picks[-1] == 999


def test_user_password_pdf_needs_a_password_and_reveals_nothing(tmp_path, src_text):
    r = inspect_pdf(mk.encrypted_pdf(tmp_path / "enc.pdf", src_text))
    assert r.ok and r.is_encrypted and r.needs_password
    assert r.page_count is None and r.page_meta == () and r.cover_webp is None
    assert r.sha256 and r.bytes  # file facts do not need the password


def test_correct_password_opens_it(tmp_path, src_text):
    path = mk.encrypted_pdf(tmp_path / "enc.pdf", src_text)
    r = inspect_pdf(path, password="secret")
    assert r.ok and not r.needs_password and r.is_encrypted and r.page_count == 3
    assert inspect_pdf(path, password="wrong").needs_password


def test_owner_password_only_opens_and_reports_permissions(tmp_path, src_text):
    r = inspect_pdf(mk.owner_only_pdf(tmp_path / "own.pdf", src_text))
    assert r.ok and r.is_encrypted and not r.needs_password
    assert (r.can_copy, r.can_modify) == (False, False)
    assert r.page_count == 3


def test_truncated_file_is_corrupt(tmp_path):
    big = mk.text_pdf(tmp_path / "big.pdf", pages=30)
    r = inspect_pdf(mk.truncated_pdf(tmp_path / "cut.pdf", big, keep=0.3))
    assert not r.ok and r.error_code in {"pdf_corrupt", "decode_failed"}


def test_garbage_with_a_pdf_header_is_corrupt(tmp_path):
    path = tmp_path / "junk.pdf"
    path.write_bytes(b"%PDF-1.7\nthis is not a pdf at all\n" * 5)
    r = inspect_pdf(path)
    assert not r.ok and r.error_code == "pdf_corrupt" and r.sha256


def test_polyglot_with_data_before_the_header_is_rejected(tmp_path, src_text):
    r = inspect_pdf(mk.polyglot_pdf(tmp_path / "poly.pdf", src_text, junk=2048))
    assert not r.ok and r.error_code == "type_mismatch"


def test_header_within_the_first_kb_is_accepted(tmp_path, src_text):
    path = tmp_path / "lead.pdf"
    path.write_bytes(b"\n" * 100 + src_text.read_bytes())
    assert inspect_pdf(path).ok


def test_missing_file_is_corrupt(tmp_path):
    assert inspect_pdf(tmp_path / "nope.pdf").error_code == "pdf_corrupt"


def test_outline_with_pages_and_children(tmp_path, src_text):
    r = inspect_pdf(mk.pdf_with_outline(tmp_path / "o.pdf", src_text))
    assert [n["title"] for n in r.outline] == ["Chapter 1", "Chapter 2"]
    assert [n["page"] for n in r.outline] == [1, 3]
    assert r.outline[0]["children"] == [{"title": "Section 1.1", "page": 2, "children": []}]


def test_outline_is_capped_at_2000_nodes(tmp_path, src_text):
    import pikepdf

    path = tmp_path / "bigoutline.pdf"
    with pikepdf.open(src_text) as pdf:
        with pdf.open_outline() as outline:
            outline.root.extend(pikepdf.OutlineItem(f"Item {i}", 0) for i in range(2600))
        pdf.save(path)
    r = inspect_pdf(path)

    def count(nodes):
        return sum(1 + count(n["children"]) for n in nodes)

    assert count(r.outline) == 2000


def test_javascript_is_flagged_not_run(tmp_path, src_text):
    r = inspect_pdf(mk.pdf_with_javascript(tmp_path / "js.pdf", src_text))
    assert r.ok and r.has_javascript is True


def test_a_page_bigger_than_14400_points_is_a_policy_error(tmp_path):
    r = inspect_pdf(mk.huge_page_pdf(tmp_path / "huge.pdf", 15000, 200))
    assert not r.ok and r.error_code == "policy"
    assert inspect_pdf(mk.huge_page_pdf(tmp_path / "ok.pdf", 14400, 200)).ok


def test_rotation_and_crop_box_shape_the_page_meta(make_rotated):
    r = inspect_pdf(make_rotated(90))
    assert r.page_meta[0] == {"w": 792.0, "h": 612.0}  # Letter, turned
    r = inspect_pdf(make_rotated(0, cropbox=(10, 20, 410, 320)))
    assert r.page_meta[0] == {"w": 400.0, "h": 300.0}
    r = inspect_pdf(make_rotated(270, cropbox=(10, 20, 410, 320)))
    assert r.page_meta[0] == {"w": 300.0, "h": 400.0}


def test_more_than_1000_pages_is_refused(tmp_path):
    import pikepdf

    path = tmp_path / "many.pdf"
    with pikepdf.new() as pdf:
        for _ in range(1001):
            pdf.add_blank_page(page_size=(100, 100))
        pdf.save(path)
    r = inspect_pdf(path)
    assert not r.ok and r.error_code == "too_many_pages"


def test_thousand_pages_inspect_and_extract_stay_within_memory(tmp_path):
    path = mk.many_pages_pdf(tmp_path / "thousand.pdf", 1000)
    script = (
        "import resource, sys\n"
        "from modules.notes.worker.inspect import inspect_pdf\n"
        "from modules.notes.worker.extract import extract_pages, chunk_ranges\n"
        "r = inspect_pdf(sys.argv[1]); assert r.ok and r.page_count == 1000, r\n"
        "n = 0\n"
        "for a, b in chunk_ranges(1000, 20):\n"
        "    n += sum(1 for p in extract_pages(sys.argv[1], a, b) if p.chars > 0)\n"
        "assert n == 1000, n\n"
        "print(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", script, str(path)],
        cwd=API_DIR,
        capture_output=True,
        text=True,
        check=True,
        timeout=240,
    )
    peak_mb = int(out.stdout.strip().splitlines()[-1]) / 1024  # ru_maxrss is KiB on Linux
    assert peak_mb < 400, f"peak RSS {peak_mb:.0f} MB"


def test_pdfium_agrees_with_pikepdf_on_page_count(src_text):
    with pdfium.PdfDocument(str(src_text)) as doc:
        assert len(doc) == inspect_pdf(src_text).page_count
