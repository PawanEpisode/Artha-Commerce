"""
Management command: python manage.py build_question_bank_seed --kind mcq|workbook [--paper 13] [--source-dir ...]

Reads the Institute's CMA Final PDFs and writes reviewable seed JSON (and a needs-review.md per paper) under
`modules/questionbank/seed/cma-final/<kind>/`. It never touches the database; `load_question_bank_seed` does that.
PYQ papers are transcribed from page images and built by `build_pyq_seed`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from modules.questionbank.domain.pdf_ingest import extract, mcq, review, seedbuild, supplement, typeset, workbook

PAPERS = ["13", "14", "15", "16", "17", "18", "19", "20A"]
WORKBOOK_PAPERS = PAPERS[1:]
SEED_ROOT = Path(__file__).resolve().parents[2] / "seed" / "cma-final"
SYLLABUS = Path(__file__).resolve().parents[3] / "syllabus" / "seed" / "cma" / "final" / "2022.json"
_EDITION = re.compile(r"(First|Second|Third|Fourth)\s+Edition\s*:\s*([A-Za-z]+)\s+(\d{4})")


def subject_for(paper: str, subjects: list[dict[str, Any]]) -> dict[str, Any]:
    number = int(re.match(r"\d+", paper).group())
    matches = [s for s in subjects if s["paper_number"] == number]
    if len(matches) > 1:  # elective papers 20A, 20B, 20C share a number
        matches = [s for s in matches if f"Paper {paper.upper()}" in s["name"]]
    if len(matches) != 1:
        raise CommandError(f"cannot find the syllabus subject for paper {paper}")
    return matches[0]


def write_seed(kind: str, paper: str, seed: dict[str, Any]) -> list[Path]:
    folder = SEED_ROOT / kind
    folder.mkdir(parents=True, exist_ok=True)
    seed_path = folder / f"p{paper.lower()}.json"
    seed_path.write_text(json.dumps(seed, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    review_path = folder / f"p{paper.lower()}.needs-review.md"
    review_path.write_text(seedbuild.needs_review_markdown(seed), encoding="utf-8")
    return [seed_path, review_path]


class Command(BaseCommand):
    help = "Parse the CMA Final MCQ banks or workbooks into reviewable seed JSON (no database access)."

    def add_arguments(self, parser):
        parser.add_argument("--kind", choices=["mcq", "workbook"], required=True)
        parser.add_argument("--paper", help="One paper, e.g. 13 or 20A. Default: all.")
        parser.add_argument(
            "--overlay-only",
            action="store_true",
            help="mcq only: apply seed/cma-final/mcq-typeset onto the existing seed files instead of re-parsing the PDFs "
            "(keeps the parsed answer keys exactly as committed).",
        )
        parser.add_argument(
            "--supplement-only",
            action="store_true",
            help="workbook only: apply seed/cma-final/workbook-supplement onto the existing seed files instead of re-parsing.",
        )
        parser.add_argument(
            "--source-dir",
            default=str(
                Path(settings.BASE_DIR).parent.parent / "docs" / "source-material" / "question-bank" / "cma-final"
            ),
        )

    def handle(self, *args, **options):
        source_dir = Path(options["source_dir"])
        kind = options["kind"]
        papers = [options["paper"].upper()] if options["paper"] else (PAPERS if kind == "mcq" else WORKBOOK_PAPERS)
        subjects = json.loads(SYLLABUS.read_text(encoding="utf-8"))["subjects"]
        for paper in papers:
            subject = subject_for(paper, subjects)
            if kind == "mcq" and options["overlay_only"]:
                self._overlay_only(paper)
                continue
            if kind == "workbook" and options["supplement_only"]:
                self._supplement_only(paper)
                continue
            if kind == "mcq":
                pdf = source_dir / "mcqs" / f"MCQ_Bank_Paper{paper}.pdf"
                items, problems = mcq.parse_mcq_tables(extract.mcq_table_rows(pdf))
                source = {
                    "source_kind": "institute_mcq",
                    "source_name": f"ICMAI MCQ Bank, Paper {paper}: {subject['name']}",
                    "source_file": f"mcqs/{pdf.name}",
                    "source_year": None,
                }
                mcq_overlay = typeset.load_overlay(SEED_ROOT / "mcq-typeset", paper)
                seed = seedbuild.build_mcq_seed(
                    items, paper=paper, subject=subject, source=source, problems=problems, overlay=mcq_overlay
                )
            else:
                pdf = source_dir / "numerical-workbooks" / f"WorkBook_Paper{paper}.pdf"
                pages = extract.workbook_pages(pdf)
                items, problems = workbook.parse_workbook(pages)
                head = " ".join(b["text"] for p in pages[:6] for b in p["blocks"] if b["type"] == "text")
                edition = _EDITION.search(head)
                source = {
                    # Workbook questions are Institute practice material; the question bank has no dedicated kind, so they
                    # use institute_mat (Study Material) and carry the `workbook` tag.
                    "source_kind": "institute_mat",
                    "source_name": f"ICMAI Work Book, Paper {paper}: {subject['name']}",
                    "source_file": f"numerical-workbooks/{pdf.name}",
                    "source_year": int(edition.group(3)) if edition else None,
                    "edition": edition.group(0) if edition else None,
                }
                overlay_folder = SEED_ROOT / "workbook-typeset"
                overlay = (
                    typeset.load_overlay(overlay_folder, paper)
                    if (overlay_folder / f"p{paper.lower()}.json").exists()
                    else None
                )
                decisions = review.load_decisions(SEED_ROOT / "workbook-review", paper)
                seed = seedbuild.build_workbook_seed(
                    items,
                    paper=paper,
                    subject=subject,
                    source=source,
                    problems=problems,
                    overlay=overlay,
                    decisions=decisions,
                )
            if kind == "workbook":
                self._supplement(seed, paper)
            paths = write_seed(kind, paper, seed)
            c = seed["counts"]
            self.stdout.write(
                f"paper {paper} {kind}: {c['items']} items, {c['ok']} ok, {c['needs_review']} draft -> {paths[0].name}"
            )

    def _supplement(self, seed: dict[str, Any], paper: str) -> list[str]:
        sup = supplement.load_supplement_file(SEED_ROOT / "workbook-supplement" / f"p{paper.lower()}.json")
        log = supplement.apply_supplement(seed["items"], sup) if sup else []
        if log:
            supplement.recount(seed)
        for line in log:
            self.stdout.write(f"paper {paper} supplement: {line}")
        return log

    def _supplement_only(self, paper: str) -> None:
        path = SEED_ROOT / "workbook" / f"p{paper.lower()}.json"
        seed = json.loads(path.read_text(encoding="utf-8"))
        if self._supplement(seed, paper):
            path.write_text(json.dumps(seed, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            (SEED_ROOT / "workbook" / f"p{paper.lower()}.needs-review.md").write_text(
                seedbuild.needs_review_markdown(seed), encoding="utf-8"
            )
        self.stdout.write(f"paper {paper} workbook supplement: {seed['counts']['items']} items")

    def _overlay_only(self, paper: str) -> None:
        path = SEED_ROOT / "mcq" / f"p{paper.lower()}.json"
        seed = json.loads(path.read_text(encoding="utf-8"))
        overlay = typeset.load_overlay(SEED_ROOT / "mcq-typeset", paper)
        for item in seed["items"]:
            entry = overlay.get(item["external_ref"])
            if not entry:
                continue
            payload = item["payload"]
            base_reasons = [r for r in item["review_reasons"] if not r.startswith("typeset")]
            stem, texts, reasons, notes, done = seedbuild.apply_mcq_overlay(
                payload["stem_md"], [o["body_md"] for o in payload["options"]], base_reasons, entry
            )
            payload["stem_md"] = stem
            for option, text in zip(payload["options"], texts, strict=True):
                option["body_md"] = text  # is_correct is never touched
            item["review_reasons"] = reasons
            item["status"] = "needs_review" if reasons else "ok"
            item["evidence"] = {
                **item["evidence"],
                **({"typeset": True, "typeset_notes": notes} if done else {}),
            }
        seed["counts"] = {
            "items": len(seed["items"]),
            "ok": sum(1 for i in seed["items"] if i["status"] == "ok"),
            "needs_review": sum(1 for i in seed["items"] if i["status"] != "ok"),
        }
        path.write_text(json.dumps(seed, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        (SEED_ROOT / "mcq" / f"p{paper.lower()}.needs-review.md").write_text(
            seedbuild.needs_review_markdown(seed), encoding="utf-8"
        )
        c = seed["counts"]
        self.stdout.write(f"paper {paper} mcq overlay: {c['items']} items, {c['ok']} ok, {c['needs_review']} draft")
