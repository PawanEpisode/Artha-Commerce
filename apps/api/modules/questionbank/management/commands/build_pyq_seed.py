"""
Management command: python manage.py build_pyq_seed [--paper 14] [--term 2024-06]

Turns the page-image transcriptions in `seed/cma-final/pyq-transcriptions/` (schema `artha.pyq-transcription.v1`) into
`artha.paper.v1` seed files under `seed/cma-final/pyq/<paper>-<term>.json`, plus one `needs-review.md` per paper.
It never touches the database; `load_question_bank_seed` does that, through `pyq.services.import_paper`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from modules.pyq.domain.importer import validate_paper_payload
from modules.questionbank.domain.pdf_ingest import overrides as overrides_mod
from modules.questionbank.domain.pdf_ingest import pyq as pyq_ingest
from modules.questionbank.domain.pdf_ingest import review as review_mod
from modules.questionbank.domain.pdf_ingest import typeset

from .build_question_bank_seed import PAPERS, SEED_ROOT, SYLLABUS, subject_for

SCHEMA = "artha.qbseed.v1"
TRANSCRIPTIONS = SEED_ROOT / "pyq-transcriptions"
OVERLAYS = SEED_ROOT / "pyq-typeset"
REVIEWS = SEED_ROOT / "pyq-review"
OVERRIDES = SEED_ROOT / "pyq-overrides"


def needs_review_markdown(paper: str, built: list[dict[str, Any]]) -> str:
    lines = [f"# Paper {paper.upper()}: previous year papers needing review", ""]
    lines.append(
        "Parts below load as DRAFT questions and are never published automatically. "
        "Reasons come from the transcriber (page images were the source) and from the builder."
    )
    total = 0
    for seed in built:
        if not seed["review"] and not seed["paper_review"]:
            continue
        lines += ["", f"## {seed['payload']['title']}", ""]
        for note in seed["paper_review"]:
            lines.append(f"- **paper**: {note}")
        for item in seed["review"]:
            total += 1
            lines.append(f"- **{item['part']}**: " + "; ".join(item["reasons"]))
    if total == 0 and not any(s["paper_review"] for s in built):
        lines += ["", "Nothing to review."]
    return "\n".join(lines) + "\n"


class Command(BaseCommand):
    help = "Build artha.paper.v1 seed files from the PYQ transcriptions (no database access)."

    def add_arguments(self, parser):
        parser.add_argument("--paper", help="One paper, e.g. 14 or 20A. Default: all.")
        parser.add_argument("--term", help="One term code, e.g. 2024-06. Default: all.")
        parser.add_argument("--out-dir", help="Write the seeds here instead of seed/cma-final/pyq (for comparisons).")
        parser.add_argument(
            "--no-cases", action="store_true", help="Skip the case-scenario formatting (for comparisons)."
        )
        parser.add_argument("--no-overrides", action="store_true", help="Skip pyq-overrides (for comparisons).")

    def handle(self, *args, **options):
        papers = [options["paper"].upper()] if options["paper"] else PAPERS
        subjects = json.loads(SYLLABUS.read_text(encoding="utf-8"))["subjects"]
        out_dir = Path(options["out_dir"]) if options.get("out_dir") else SEED_ROOT / "pyq"
        out_dir.mkdir(parents=True, exist_ok=True)
        failed = False
        for paper in papers:
            subject = subject_for(paper, subjects)
            built: list[dict[str, Any]] = []
            for path in sorted(TRANSCRIPTIONS.glob(f"p{paper.lower()}-*.json")):
                t = json.loads(path.read_text(encoding="utf-8"))
                if options["term"] and t.get("term_code") != options["term"]:
                    continue
                try:
                    overlay = typeset.load_overlay_file(OVERLAYS / f"p{paper.lower()}-{t['term_code']}.json")
                    decisions = review_mod.load_decisions_file(REVIEWS / f"p{paper.lower()}-{t['term_code']}.json")
                    res = pyq_ingest.build_paper(
                        t, subject=subject, overlay=overlay, decisions=decisions, cases=not options["no_cases"]
                    )
                    if not options["no_overrides"]:
                        overrides_mod.apply_overrides(
                            res,
                            overrides_mod.load_overrides_file(OVERRIDES / f"p{paper.lower()}-{t['term_code']}.json"),
                        )
                except pyq_ingest.TranscriptionError as exc:
                    failed = True
                    self.stderr.write(f"{path.name}: {exc}")
                    continue
                problems = validate_paper_payload(res["payload"])
                if problems:
                    failed = True
                    self.stderr.write(f"{path.name}: importer validation: {problems}")
                    continue
                seed = {
                    "schema": SCHEMA,
                    "kind": "pyq",
                    "paper": paper,
                    "source_file": f"pyq-transcriptions/{path.name}",
                    "paper_review": t.get("review", []),
                    "payload": res["payload"],
                    "review": res["report"],
                    "typeset_notes": res["typeset_notes"],
                    "review_decisions": res["decisions"],
                    "case_groups": res.get("case_groups", []),
                    "owner_overrides": res.get("overrides", []),
                    "counts": res["counts"],
                }
                target = out_dir / f"p{paper.lower()}-{t['term_code']}.json"
                target.write_text(json.dumps(seed, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
                built.append(seed)
                c = res["counts"]
                self.stdout.write(
                    f"paper {paper} {t['term_code']}: {c['leaves']} leaves, {c['draft_parts']} draft, {c['answered']} answered"
                )
            if built and not options["term"]:
                (out_dir / f"p{paper.lower()}.needs-review.md").write_text(
                    needs_review_markdown(paper, built), encoding="utf-8"
                )
        if failed:
            raise CommandError("one or more transcriptions failed validation")
