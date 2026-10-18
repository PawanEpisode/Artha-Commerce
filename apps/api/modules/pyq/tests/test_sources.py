"""Finding the past-paper PDFs to host from the source-material folder layout."""

from __future__ import annotations

from pathlib import Path

from modules.pyq.domain.sources import classify, discover, term_code_of


def _touch(root: Path, *parts: str) -> Path:
    path = root.joinpath(*parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4")
    return path


def test_term_folders_become_term_codes():
    assert term_code_of("June 24") == "2024-06"
    assert term_code_of("Dec 23") == "2023-12"
    assert term_code_of("June 24 ") == "2024-06"  # one source folder has a trailing space
    assert term_code_of("Summer 24") is None


def test_file_names_say_what_the_file_is():
    assert classify("P13 - Corporate and Economic Laws - Question Paper - June 24.pdf")[0] == "paper"
    assert classify("P13 - Corporate and Economic Law - Question Paper - Dec 25.pdf")[0] == "paper"
    assert classify("P13 - Corporate and Economic Laws - Suggested Answer - June 24.pdf")[0] == "suggested_answers"
    kind, label = classify("P18 - CFR - Question & Answers - June 23.pdf")
    assert kind == "paper" and "Answers" in label  # one combined file
    assert classify("P13 - something else.pdf") is None


def test_discover_maps_folders_to_the_papers_the_seed_loader_creates(tmp_path):
    _touch(tmp_path, "P13 - Corporate and Economic Laws (CEL)", "June 24", "P13 - X - Question Paper - June 24.pdf")
    _touch(tmp_path, "P13 - Corporate and Economic Laws (CEL)", "June 24", "P13 - X - Suggested Answer - June 24.pdf")
    _touch(tmp_path, "P20A - SPMBV ( SPMBV )", "June 24 ", "P20A - SPMBV - Question Paper - June 24.pdf")
    _touch(tmp_path, "P18 - CFR ( CFR )", "Dec 23", "P18 - CFR - Question & Answers - Dec 23.pdf")
    _touch(tmp_path, "P13 - Corporate and Economic Laws (CEL)", "June 24", "notes.pdf")
    _touch(tmp_path, "Loose.pdf")

    files, unmatched = discover(tmp_path)

    by_ref = {(f.external_ref, f.link_kind) for f in files}
    assert by_ref == {
        ("pyq:cma-final:p13:2024-06", "paper"),
        ("pyq:cma-final:p13:2024-06", "suggested_answers"),
        ("pyq:cma-final:p20a:2024-06", "paper"),
        ("pyq:cma-final:p18:2023-12", "paper"),
    }
    assert sorted(unmatched) == ["Loose.pdf", str(Path("P13 - Corporate and Economic Laws (CEL)/June 24/notes.pdf"))]
