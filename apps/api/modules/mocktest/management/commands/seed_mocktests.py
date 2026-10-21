"""
Django management command:
    python manage.py seed_mocktests [--dir DIR] [--file FILE] [--dry-run] [--publish]

Seeds mock test papers and MTPs from structured JSON files in Docs/source-material/mock-tests/.
Creates QuestionBank questions idempotently, builds Sections, ChoiceGroups, and Items,
validates blueprint scoring rules, and optionally publishes papers.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any
import uuid

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from modules.mocktest.domain import blueprint
from modules.mocktest.domain.pdf_parser import (
    find_all_mqp_pairs,
    find_all_ptp_files,
    parse_mqp_pair,
    parse_ptp,
    resolve_source_path,
)
from modules.mocktest.models import ChoiceGroup, Item, Paper, PaperVersion, Section, Series
from modules.questionbank import services as qb_services
from modules.syllabus.models import Course, ExamTerm, Level, Scheme, Subject

SEED_ACTOR_ID = uuid.uuid5(uuid.NAMESPACE_URL, "https://arthacommerce.in/mocktest/seed-loader")


class Command(BaseCommand):
    help = "Seeds Mock Test Papers and MTPs from JSON and PDF source materials."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dir",
            default="Docs/source-material/mock-tests",
            help="Directory containing mock test JSON or PDF files.",
        )
        parser.add_argument(
            "--file",
            help="Path to a single mock test JSON file to ingest.",
        )
        parser.add_argument(
            "--ingest-all-mqp",
            action="store_true",
            help="Scan and ingest all MQP Question & Answer PDF pairs in Docs/source-material/mock-tests/.",
        )
        parser.add_argument(
            "--ingest-all-ptp",
            action="store_true",
            help="Scan and ingest all Postal Test Paper PDFs in Docs/source-material/.",
        )
        parser.add_argument(
            "--ingest-all-pdfs",
            action="store_true",
            help="Scan and ingest all MQP and PTP PDF papers.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Limit the number of PDF papers to ingest (0 = all).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and validate without committing changes.",
        )
        parser.add_argument(
            "--publish",
            action="store_true",
            help="Mark papers and versions as LIVE and PUBLIC if valid.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        publish = options["publish"]
        target_file = options.get("file")
        ingest_mqp = options["ingest_all_mqp"] or options["ingest_all_pdfs"]
        ingest_ptp = options["ingest_all_ptp"] or options["ingest_all_pdfs"]
        limit = options["limit"]
        from contextlib import nullcontext

        ctx = transaction.atomic() if dry_run else nullcontext()
        with ctx:
            if ingest_mqp or ingest_ptp:
                if ingest_mqp:
                    self.stdout.write("Scanning for MQP Question & Answer PDF pairs...")
                    pairs = find_all_mqp_pairs(options["dir"])
                    if limit > 0:
                        pairs = pairs[:limit]
                    self.stdout.write(f"Found {len(pairs)} MQP pair(s) to process.")
                    for idx, (q_path, a_path) in enumerate(pairs, start=1):
                        self.stdout.write(f"[{idx}/{len(pairs)}] Ingesting MQP: {q_path.name}...")
                        try:
                            data = parse_mqp_pair(q_path, a_path)
                            self._process_data(data, publish=publish, label=q_path.name)
                        except Exception as exc:
                            self.stdout.write(self.style.ERROR(f"Error parsing {q_path.name}: {exc}"))
                            if dry_run:
                                raise exc

                if ingest_ptp:
                    self.stdout.write("Scanning for Postal Test Paper PDFs...")
                    ptps = find_all_ptp_files("Docs/source-material")
                    if limit > 0:
                        ptps = ptps[:limit]
                    self.stdout.write(f"Found {len(ptps)} PTP file(s) to process.")
                    for idx, ptp_path in enumerate(ptps, start=1):
                        self.stdout.write(f"[{idx}/{len(ptps)}] Ingesting PTP: {ptp_path.name}...")
                        try:
                            data = parse_ptp(ptp_path)
                            self._process_data(data, publish=publish, label=ptp_path.name)
                        except Exception as exc:
                            self.stdout.write(self.style.ERROR(f"Error parsing {ptp_path.name}: {exc}"))
                            if dry_run:
                                raise exc
            else:
                if target_file:
                    files = [Path(target_file)]
                else:
                    seed_dir = resolve_source_path(options["dir"])
                    if not seed_dir.exists():
                        self.stdout.write(self.style.WARNING(f"Directory not found: {options['dir']}"))
                        return
                    files = sorted(seed_dir.rglob("*.json"))

                if not files:
                    self.stdout.write(self.style.WARNING("No mock test JSON files found to seed."))
                    return

                self.stdout.write(f"Found {len(files)} mock test file(s) to process.")
                for file_path in files:
                    self._process_file(file_path, publish=publish)

            if dry_run:
                transaction.set_rollback(True)
                self.stdout.write(self.style.SUCCESS("DRY RUN completed. All changes rolled back."))
            else:
                self.stdout.write(self.style.SUCCESS("Mock test seeding completed successfully."))

    def _process_file(self, file_path: Path, publish: bool = False):
        self.stdout.write(f"Processing JSON: {file_path.name}...")
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._process_data(data, publish=publish, label=file_path.name)

    def _process_data(self, data: dict[str, Any], publish: bool = False, label: str = ""):

        course_code = data.get("course_code") or data.get("course")
        level_code = data.get("level_code") or data.get("level")
        scheme_code = data.get("scheme_code") or data.get("scheme")
        subject_key = data.get("subject_key") or data.get("subject")

        course = Course.objects.filter(code=course_code).first()
        if not course:
            course, _ = Course.objects.get_or_create(code=course_code, defaults={"name": course_code.upper()})

        level = Level.objects.filter(course=course, code=level_code).first()
        if not level:
            level, _ = Level.objects.get_or_create(course=course, code=level_code, defaults={"name": level_code.title(), "sort_order": 1})

        scheme = None
        if scheme_code:
            scheme = Scheme.objects.filter(level=level, code=scheme_code).first()
        if not scheme:
            scheme = Scheme.objects.filter(level=level).first()
        if not scheme:
            scheme, _ = Scheme.objects.get_or_create(level=level, code="default", defaults={"name": "Standard Scheme"})

        subject = None
        if subject_key:
            subject = Subject.objects.filter(scheme=scheme, key=subject_key).first()

        term = None
        term_code = data.get("exam_term") or data.get("term_code")
        if term_code:
            term = (
                ExamTerm.objects.filter(level=level, code=term_code).first()
                or ExamTerm.objects.filter(course=course, code=term_code).first()
            )
            if not term:
                term_name = "June " + term_code[:4] if "06" in term_code else "December " + term_code[:4]
                term, _ = ExamTerm.objects.get_or_create(
                    level=level,
                    code=term_code,
                    defaults={"name": term_name, "is_open": True},
                )

        # 1. Series (optional)
        series_obj = None
        series_data = data.get("series")
        if series_data:
            series_slug = series_data.get("slug") or f"{level_code}-{series_data['title'].lower().replace(' ', '-')}"[:120]
            series_obj, _ = Series.objects.get_or_create(
                level=level,
                slug=series_slug,
                defaults={
                    "course": course,
                    "title": series_data["title"],
                    "kind": series_data.get("kind", Series.Kind.INSTITUTE_MTP),
                    "series_no": series_data.get("series_no", 1),
                    "exam_term": term,
                    "scheme": scheme,
                    "status": Series.Status.LIVE if publish else Series.Status.DRAFT,
                },
            )

        # 2. Paper
        title = data["title"]
        slug = data.get("slug") or title.lower().replace(" ", "-")[:120]
        delivery_mode = data.get("delivery_mode", Paper.DeliveryMode.NATIVE)
        kind = data.get("kind", Paper.Kind.MTP)

        paper, _ = Paper.objects.update_or_create(
            level=level,
            slug=slug,
            defaults={
                "series": series_obj,
                "course": course,
                "scheme": scheme,
                "subject": subject,
                "subject_key": subject_key or (subject.key if subject else ""),
                "exam_term": term,
                "title": title,
                "description": data.get("description", ""),
                "kind": kind,
                "source_tag": data.get("source_tag", Paper.SourceTag.INSTITUTE),
                "source_pdf_url": data.get("source_pdf_url", ""),
                "solution_pdf_url": data.get("solution_pdf_url", ""),
                "coaching_name": data.get("coaching_name", ""),
                "ownership": Paper.Ownership.PLATFORM,
                "rights_status": data.get("rights_status", Paper.RightsStatus.INSTITUTE_MATERIAL),
                "visibility": Paper.Visibility.PUBLIC if publish else Paper.Visibility.PRIVATE,
                "status": Paper.Status.LIVE if publish else Paper.Status.DRAFT,
                "delivery_mode": delivery_mode,
                "origin_module": "seed",
                "external_ref": data.get("external_ref", f"mock:{slug}"),
            },
        )

        # 3. PaperVersion
        total_marks = Decimal(str(data.get("total_marks", 100)))
        duration_minutes = data.get("duration_minutes")
        duration_seconds = data.get("duration_seconds") or (duration_minutes * 60 if duration_minutes else 10800)
        reading_minutes = data.get("reading_minutes")
        reading_seconds = data.get("reading_seconds") or (reading_minutes * 60 if reading_minutes else 0)

        version, _ = PaperVersion.objects.update_or_create(
            paper=paper,
            version_no=1,
            defaults={
                "state": PaperVersion.State.LIVE if publish else PaperVersion.State.DRAFT,
                "total_marks": total_marks,
                "duration_seconds": duration_seconds,
                "reading_seconds": reading_seconds,
                "section_timing": data.get("section_timing", PaperVersion.SectionTiming.NONE),
                "scoring_mode": data.get("scoring_mode", PaperVersion.ScoringMode.RULE),
                "instructions_md": data.get("instructions_md", ""),
                "focus_policy": data.get("focus_policy", PaperVersion.FocusPolicy.LOG),
                "created_by": SEED_ACTOR_ID,
                "published_at": timezone.now() if publish else None,
            },
        )
        paper.live_version_id = version.id
        paper.save(update_fields=["live_version_id"])

        # 4. Sections & Choice Groups & Items
        sections_data = data.get("sections", [])
        Section.objects.filter(version=version).delete()

        created_items_count = 0
        all_items_data = []
        all_choice_groups_data = []

        for s_idx, sec_dict in enumerate(sections_data, start=1):
            sec_obj = Section.objects.create(
                version=version,
                key=sec_dict["key"],
                title=sec_dict["title"],
                position=sec_dict.get("position", s_idx),
                kind=sec_dict.get("kind", Section.Kind.OBJECTIVE),
                duration_seconds=sec_dict.get("duration_seconds"),
                instructions_md=sec_dict.get("instructions_md", ""),
                marks_total=Decimal(str(sec_dict.get("marks_total", 0))),
            )

            # Choice groups for this section
            cg_map = {}
            for g_idx, cg_dict in enumerate(sec_dict.get("choice_groups", []), start=1):
                cg_obj = ChoiceGroup.objects.create(
                    section=sec_obj,
                    key=cg_dict["key"],
                    label=cg_dict["label"],
                    required_count=cg_dict.get("required_count", 1),
                    overflow_policy=cg_dict.get("overflow_policy", ChoiceGroup.OverflowPolicy.BLOCK),
                    position=cg_dict.get("position", g_idx),
                )
                cg_map[cg_dict["key"]] = cg_obj
                all_choice_groups_data.append({
                    "section_key": sec_obj.key,
                    "key": cg_obj.key,
                    "label": cg_obj.label,
                    "required_count": cg_obj.required_count,
                    "overflow_policy": cg_obj.overflow_policy,
                })

            # Items for this section
            for it_dict in sec_dict.get("items", []):
                q_data = it_dict.get("question", {})
                external_ref = q_data.get("external_ref") or f"mock:{slug}:{sec_obj.key}:{it_dict['position']}"

                # Upsert into QuestionBank
                qb_payload = {
                    "schema": "artha.question.v1",
                    "kind": q_data.get("kind", "mcq_single"),
                    "stem_md": q_data.get("stem_md", ""),
                    "options": q_data.get("options", []),
                    "explanation_md": q_data.get("explanation_md", ""),
                    "marks": it_dict.get("marks", 1),
                    "negative_marks": it_dict.get("negative_marks"),
                    "numeric_key": q_data.get("numeric_key"),
                    "rubric": q_data.get("rubric"),
                    "labels": {
                        "source_kind": "institute_mtp",
                        "source_name": title,
                        "difficulty": q_data.get("difficulty", 2),
                    },
                    "mapping": [
                        {
                            "course": course_code,
                            "level": level_code,
                            "subject_key": subject_key or "",
                            "chapter_key": q_data.get("chapter_key", ""),
                            "primary": True,
                        }
                    ] if q_data.get("chapter_key") else [],
                }

                upsert_res = qb_services.upsert_from_source(
                    origin_module="mocktest",
                    external_ref=external_ref,
                    payload=qb_payload,
                    ownership="platform",
                    rights_status="institute_material",
                    actor_id=SEED_ACTOR_ID,
                    auto_publish=True,
                )
                question_obj = upsert_res.question
                q_ver = question_obj.live_version or question_obj.current_version

                # Choice group link
                cg_key = it_dict.get("choice_group_key")
                cg_obj = cg_map.get(cg_key)

                item_obj = Item.objects.create(
                    version=version,
                    section=sec_obj,
                    choice_group=cg_obj,
                    position=it_dict["position"],
                    display_label=it_dict.get("display_label", f"Q.{it_dict['position']}"),
                    question=question_obj,
                    question_version_id=q_ver.id if q_ver else None,
                    marks=Decimal(str(it_dict.get("marks", 1))),
                    negative_marks=Decimal(str(it_dict["negative_marks"])) if it_dict.get("negative_marks") is not None else None,
                    suggested_seconds=it_dict.get("suggested_seconds"),
                )
                created_items_count += 1
                all_items_data.append({
                    "section_key": sec_obj.key,
                    "choice_group_key": cg_key,
                    "position": item_obj.position,
                    "display_label": item_obj.display_label,
                    "question_id": question_obj.id,
                    "marks": item_obj.marks,
                    "negative_marks": item_obj.negative_marks,
                })

        # 5. Validate Blueprint
        sections_spec = [
            {
                "key": s.key,
                "title": s.title,
                "position": s.position,
                "kind": s.kind,
                "duration_seconds": s.duration_seconds,
            }
            for s in version.sections.all()
        ]
        is_valid, problems, calculated_marks = blueprint.validate_blueprint(
            sections=sections_spec,
            items=all_items_data,
            choice_groups=all_choice_groups_data,
            section_timing=version.section_timing,
        )

        version.item_count = created_items_count
        version.content_hash = blueprint.compute_content_hash(all_items_data)
        version.save(update_fields=["item_count", "content_hash"])

        self.stdout.write(
            self.style.SUCCESS(
                f"  -> Ingested paper '{paper.title}' (slug: {paper.slug}): "
                f"{len(sections_data)} sections, {created_items_count} items, "
                f"calculated marks: {calculated_marks}/{version.total_marks}. "
                f"Blueprint valid: {is_valid}"
            )
        )
        if problems:
            for p in problems:
                self.stdout.write(self.style.WARNING(f"     [Blueprint Warning] {p}"))
