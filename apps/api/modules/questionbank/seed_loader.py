"""
Loads the committed question-bank seeds (`seed/cma-final/<kind>/`) through the existing services:

* mcq / workbook items -> `services.upsert_from_source` (idempotent on `(origin_module, external_ref)`);
* PYQ papers          -> `pyq.services.import_paper` (idempotent on the paper's `external_ref`).

No second importer lives here: this module only reads files, decides what may be published, and counts outcomes.
Anything the parser was unsure about (`status != "ok"`, or a PYQ part with review reasons) is loaded as an unpublished
draft and is never published by this loader, with or without `--publish`.
"""

from __future__ import annotations

import copy
import json
import uuid
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from django.db import transaction

from modules.pyq.models import PyqPaper
from modules.pyq.services import import_paper, publish_paper, withdraw_paper
from modules.questionbank.services import upsert_from_source

SEED_ROOT = Path(__file__).resolve().parent / "seed" / "cma-final"
KINDS = ("mcq", "workbook", "pyq")
# A fixed actor so reruns attribute to the same "user" and content hashes stay stable.
SEED_ACTOR_ID = uuid.uuid5(uuid.NAMESPACE_URL, "https://arthacommerce.in/question-bank/seed-loader")


@dataclass
class LoadReport:
    paper: str
    kind: str
    label: str = ""
    parsed: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    merged: int = 0
    drafts: int = 0  # loaded but held back for review
    published: int = 0
    skipped: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def row(self) -> str:
        return (
            f"{self.paper:<5} {self.kind:<9} {self.label:<8} parsed={self.parsed:<4} created={self.created:<4} "
            f"updated={self.updated:<4} unchanged={self.unchanged:<4} merged={self.merged:<3} "
            f"draft={self.drafts:<3} published={self.published:<4} skipped={len(self.skipped)}"
        )


def seed_files(kind: str, paper: str | None = None) -> list[Path]:
    folder = SEED_ROOT / kind
    files = sorted(p for p in folder.glob("p*.json") if not p.name.endswith(".needs-review.json"))
    if paper:
        prefix = f"p{paper.lower()}"
        files = [p for p in files if p.stem == prefix or p.stem.startswith(prefix + "-")]
    return files


def _count(report: LoadReport, outcome: str, merged: bool) -> None:
    if merged:
        report.merged += 1
    elif outcome == "created":
        report.created += 1
    elif outcome == "new_version":
        report.updated += 1
    else:
        report.unchanged += 1


def load_item_seed(path: Path, *, publish: bool, actor_id: uuid.UUID = SEED_ACTOR_ID) -> LoadReport:
    seed = json.loads(path.read_text(encoding="utf-8"))
    report = LoadReport(paper=str(seed["paper"]).upper(), kind=seed["kind"])
    for item in seed["items"]:
        report.parsed += 1
        ok = item["status"] == "ok"
        if not ok:
            report.drafts += 1
        try:
            with transaction.atomic():
                res = upsert_from_source(
                    origin_module=item["origin_module"],
                    external_ref=item["external_ref"],
                    payload=copy.deepcopy(item["payload"]),
                    ownership="platform",
                    rights_status="institute_material",
                    actor_id=actor_id,
                    auto_publish=bool(publish and ok),
                    mapping_confidence=(item.get("mapping_meta") or {}).get("confidence"),
                )
        except Exception as exc:  # one bad item must not stop the paper
            report.skipped.append(f"{item['external_ref']}: {type(exc).__name__}: {exc}")
            continue
        _count(report, res.outcome, res.duplicate_of is not None)
        if publish and ok and res.canonical.live_version_id:
            report.published += 1
    return report


def _adopt_legacy_shell(payload: dict[str, Any], report: LoadReport, *, replace: bool, actor_id: uuid.UUID) -> bool:
    """
    The early `seed_cma_pyq` command left empty paper shells (official links, no questions) under another external_ref. They
    hold the paper's natural key, so the import would fail on the unique constraint. An empty shell is adopted: it takes our
    external_ref and its links are kept. A paper that already has questions is never touched; it is reported instead.
    Returns False when the paper has to be skipped.
    """
    clash = (
        PyqPaper.objects.filter(
            course__code=payload["course_code"].lower(),
            level__code=payload["level_code"].lower(),
            subject_key=payload["subject_key"],
            term_code=payload["term_code"],
            variant=payload.get("variant", ""),
        )
        .exclude(external_ref=payload["external_ref"])
        .first()
    )
    if clash is None:
        return True
    if clash.questions.exists() and replace:
        # Withdrawn (not deleted) and moved out of the way of the natural key. Its questions stay in the bank untouched;
        # `repair_question_bank` deals with filler.
        payload["links"] = [
            *payload.get("links", []),
            *[
                {"link_kind": k.link_kind, "label": k.label, "url": k.url, "host": k.host, "page_hint": k.page_hint}
                for k in clash.links.all()
            ],
        ]
        withdraw_paper(actor_id, clash.id, PyqPaper.WithdrawnReason.REPLACED)
        clash.variant = "legacy-seed"
        clash.save(update_fields=["variant", "updated_at"])
        report.notes.append(
            f"withdrew the earlier paper '{clash.external_ref}' (it had questions) and moved it to variant 'legacy-seed'"
        )
        return True
    if clash.questions.exists():
        report.skipped.append(
            f"{payload['external_ref']}: an existing paper '{clash.external_ref}' with questions already holds this term. "
            "Nothing was changed. Rerun with --replace-legacy to withdraw it and load this paper instead."
        )
        return False
    kept = [
        {
            "link_kind": link.link_kind,
            "label": link.label,
            "url": link.url,
            "host": link.host,
            "page_hint": link.page_hint,
        }
        for link in clash.links.all()
    ]
    payload["links"] = [*payload.get("links", []), *kept]
    clash.external_ref = payload["external_ref"]
    fields = ["external_ref", "updated_at"]
    if clash.status == PyqPaper.Status.PUBLISHED:
        # The shell was published with no questions. It goes back to draft; `--publish` republishes it when nothing is in doubt.
        clash.status, clash.published_at = PyqPaper.Status.DRAFT, None
        fields += ["status", "published_at"]
    clash.save(update_fields=fields)
    report.notes.append(f"adopted the empty legacy paper '{clash.title}' and kept its {len(kept)} link(s)")
    return True


def load_pyq_seed(
    path: Path, *, publish: bool, replace_legacy: bool = False, actor_id: uuid.UUID = SEED_ACTOR_ID
) -> LoadReport:
    seed = json.loads(path.read_text(encoding="utf-8"))
    payload = copy.deepcopy(seed["payload"])
    report = LoadReport(paper=str(seed["paper"]).upper(), kind="pyq", label=payload["term_code"])
    leaves = [p for p in payload["parts"] if p.get("is_leaf")]
    report.parsed = len(leaves)
    review_parts = {r["part"] for r in seed["review"]}
    report.drafts = sum(1 for p in leaves if not p.get("publish", False) or p["number_label"] in review_parts)
    for part in leaves:
        # Nothing is published unless asked for, and parts with doubts are never published.
        part["publish"] = bool(publish and part.get("publish", False) and part["number_label"] not in review_parts)
    existed = PyqPaper.objects.filter(external_ref=payload["external_ref"]).exists()
    legacy = _adopt_legacy_shell(payload, report, replace=replace_legacy, actor_id=actor_id)
    if legacy is False:
        return report
    try:
        with transaction.atomic():
            res = import_paper(actor_id, payload)
    except Exception as exc:
        report.skipped.append(f"{payload['external_ref']}: {type(exc).__name__}: {exc}")
        return report
    if not res.is_valid or res.paper is None:
        report.skipped.append(f"{payload['external_ref']}: " + "; ".join(res.issues))
        return report
    out = Counter(res.outcomes)
    # `import_paper` counts a merged duplicate under both "created" and "merged_duplicate"; report it once.
    report.merged = out.get("merged_duplicate", 0)
    report.created = out.get("created", 0) - report.merged
    report.updated = out.get("new_version", 0)
    report.unchanged = out.get("unchanged", 0)
    report.notes.append(f"paper {'updated' if existed else 'created'}: {res.paper.title}")
    report.notes.extend(res.warnings)
    if publish:
        # `paper_review` holds the transcriber's layout notes ("page 8 is blank", "5+5+4 marks as printed"). They are
        # informational: every part that was in doubt carries its own review reason, which is what blocks publishing.
        if report.drafts:
            report.notes.append("paper not published: it has items needing review or answers")
        else:
            try:
                with transaction.atomic():
                    publish_paper(actor_id, res.paper.id)
                report.published = len(leaves)
            except ValueError as exc:
                report.notes.append(f"paper not published: {exc}")
    return report
