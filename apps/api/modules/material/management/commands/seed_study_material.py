"""
Django management command:
    python manage.py seed_study_material [--dir DIR] [--file FILE] [--dry-run] [--publish]

Seeds Institute Study Material works, editions, units, chapters, and items (illustrations, exercises, TYKs)
from structured JSON files in Docs/source-material/study-material/.
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

from modules.material import errors, services as mat_services
from modules.material.domain import labels, term
from modules.material.domain.book_ingest import (
    find_all_paper_books,
    ingest_paper_book,
    resolve_source_path,
)
from modules.material.models import Edition, EditionItem, Item, Provider, Unit, UnitChapter, Work
from modules.syllabus.models import Chapter, Course, Level, Scheme, Subject

SEED_ACTOR_ID = uuid.uuid5(uuid.NAMESPACE_URL, "https://arthacommerce.in/material/seed-loader")


class Command(BaseCommand):
    help = "Seeds Institute Study Material (works, editions, units, items) from JSON files and Paper-Book PDFs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dir",
            default="Docs/source-material/study-material",
            help="Directory containing study material JSON files or PDFs.",
        )
        parser.add_argument(
            "--file",
            help="Path to a single study material JSON or PDF file to ingest.",
        )
        parser.add_argument(
            "--ingest-all-books",
            action="store_true",
            help="Scan and ingest all ICMAI Paper-Book PDFs into Works, Editions, and Chapters.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Limit the number of books to ingest (0 = all).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and validate without committing changes.",
        )
        parser.add_argument(
            "--publish",
            action="store_true",
            help="Publish editions to CURRENT status immediately.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        publish = options["publish"]
        target_file = options.get("file")
        ingest_books = options["ingest_all_books"]
        limit = options.get("limit", 0)
        from contextlib import nullcontext

        ctx = transaction.atomic() if dry_run else nullcontext()
        with ctx:
            if ingest_books:
                self.stdout.write("Scanning for ICMAI Paper-Book PDFs...")
                books = find_all_paper_books(options["dir"])
                if limit > 0:
                    books = books[:limit]
                self.stdout.write(f"Found {len(books)} paper book(s) to process.")
                for idx, book_path in enumerate(books, start=1):
                    self.stdout.write(f"[{idx}/{len(books)}] Ingesting Paper Book: {book_path.name}...")
                    try:
                        work = ingest_paper_book(book_path)
                        self.stdout.write(self.style.SUCCESS(f"  -> Ingested Work '{work.title}' (key: {work.work_key})"))
                    except Exception as exc:
                        self.stdout.write(self.style.ERROR(f"Error ingesting book {book_path.name}: {exc}"))
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
                    self.stdout.write(self.style.WARNING("No study material JSON files found to seed."))
                    return

                self.stdout.write(f"Found {len(files)} study material file(s) to process.")
                for file_path in files:
                    try:
                        self._process_file(file_path, publish=publish)
                    except Exception as exc:
                        self.stdout.write(self.style.ERROR(f"Failed processing {file_path.name}: {exc}"))
                        if dry_run:
                            raise exc

            if dry_run:
                transaction.set_rollback(True)
                self.stdout.write(self.style.SUCCESS("DRY RUN completed. All changes rolled back."))
            else:
                self.stdout.write(self.style.SUCCESS("Study material seeding completed successfully."))

    def _process_file(self, file_path: Path, publish: bool = False):
        self.stdout.write(f"Processing: {file_path.name}...")
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 1. Provider
        prov_slug = data.get("provider", "icai").lower()
        provider = Provider.objects.filter(slug=prov_slug).first()
        if not provider:
            prov_name = data.get("provider_name") or prov_slug.upper()
            provider = mat_services.create_provider(
                actor_id=SEED_ACTOR_ID,
                payload={
                    "name": prov_name,
                    "slug": prov_slug,
                    "kind": Provider.Kind.INSTITUTE,
                    "website_url": data.get("provider_website", ""),
                },
            )

        # 2. Syllabus Resolution
        course_code = data.get("course_code") or data.get("course")
        level_code = data.get("level_code") or data.get("level")
        subject_key = data.get("subject_key") or data.get("subject")

        course = Course.objects.filter(code=course_code).first()
        if not course:
            course, _ = Course.objects.get_or_create(code=course_code, defaults={"name": course_code.upper()})

        level = Level.objects.filter(course=course, code=level_code).first()
        if not level:
            level, _ = Level.objects.get_or_create(
                course=course, code=level_code, defaults={"name": level_code.title(), "sort_order": 1}
            )

        scheme = Scheme.objects.filter(level=level).first()
        if not scheme:
            scheme, _ = Scheme.objects.get_or_create(level=level, code="default", defaults={"name": "Standard Scheme"})

        subject = None
        if subject_key:
            subject = Subject.objects.filter(scheme=scheme, key=subject_key).first()

        # 3. Work
        work_key = data["work_key"]
        title = data["title"]
        work_kind = data.get("kind", Work.Kind.MODULE)

        work, _ = Work.objects.update_or_create(
            provider=provider,
            work_key=work_key,
            defaults={
                "title": title,
                "kind": work_kind,
                "course_id": course.id,
                "level_id": level.id,
                "subject_key": subject_key or (subject.key if subject else ""),
                "subject_id": subject.id if subject else None,
                "visibility": Work.Visibility.PUBLIC,
                "status": Work.Status.ACTIVE,
            },
        )

        # 4. Edition
        ed_data = data.get("edition", {})
        label = ed_data.get("label", "Current Edition")
        applies_from = ed_data.get("applies_from_term", "2024-05")
        applies_to = ed_data.get("applies_to_term")

        from_ord, to_ord = term.validate_term_range(applies_from, applies_to)

        edition, _ = Edition.objects.update_or_create(
            work=work,
            label=label,
            defaults={
                "edition_date": ed_data.get("edition_date"),
                "applies_from_term": applies_from,
                "applies_to_term": applies_to,
                "applies_from_ord": from_ord,
                "applies_to_ord": to_ord,
                "applicability_note": ed_data.get("applicability_note", ""),
                "source_url": ed_data.get("source_url") or data.get("source_url"),
                "source_page_url": ed_data.get("source_page_url") or data.get("source_page_url"),
                "page_offset": ed_data.get("page_offset", 0),
                "status": Edition.Status.DRAFT,
            },
        )

        # 5. Units & Items
        units_data = data.get("units", [])
        total_items_seeded = 0

        for u_idx, u_dict in enumerate(units_data, start=1):
            u_key = u_dict["unit_key"]
            unit_obj, _ = Unit.objects.update_or_create(
                edition=edition,
                unit_key=u_key,
                defaults={
                    "module_label": u_dict.get("module_label", ""),
                    "printed_number": u_dict.get("printed_number", ""),
                    "title": u_dict.get("title", f"Unit {u_idx}"),
                    "page_start": u_dict.get("page_start"),
                    "page_end": u_dict.get("page_end"),
                    "sort_order": u_dict.get("sort_order", u_idx),
                },
            )

            # Map to syllabus chapter
            ch_key = u_dict.get("chapter_key")
            chapter_obj = None
            if ch_key and subject:
                chapter_obj = Chapter.objects.filter(subject=subject, key=ch_key).first()

            if chapter_obj:
                UnitChapter.objects.update_or_create(
                    unit=unit_obj,
                    chapter_id=chapter_obj.id,
                    defaults={
                        "subject_key": subject.key,
                        "chapter_key": chapter_obj.key,
                        "scheme_id": scheme.id,
                        "is_primary": True,
                        "status": UnitChapter.Status.CONFIRMED,
                        "origin": UnitChapter.Origin.EDITOR,
                        "confidence": Decimal("1.00"),
                    },
                )

            # Ingest Unit items
            for it_pos, it_dict in enumerate(u_dict.get("items", []), start=1):
                item_key = it_dict.get("item_key") or f"{u_key}-it-{it_pos}"
                printed_label = it_dict["printed_label"]
                label_norm = labels.normalise_label(printed_label)
                printed_ord = labels.extract_ordinal(printed_label)
                kind = it_dict.get("kind", Item.Kind.ILLUSTRATION)
                descriptor = it_dict.get("descriptor", "").strip() or None

                item_obj, _ = Item.objects.update_or_create(
                    work=work,
                    item_key=item_key,
                    defaults={
                        "kind": kind,
                        "status": Item.Status.ACTIVE,
                        "first_edition": edition,
                        "canonical_key": it_dict.get("canonical_key") or label_norm,
                        "created_by": SEED_ACTOR_ID,
                    },
                )

                # Chapter ID fallback
                resolved_ch_id = chapter_obj.id if chapter_obj else uuid.uuid4()
                resolved_ch_key = chapter_obj.key if chapter_obj else (ch_key or "")

                EditionItem.objects.update_or_create(
                    edition=edition,
                    item=item_obj,
                    defaults={
                        "unit": unit_obj,
                        "printed_label": printed_label,
                        "label_norm": label_norm,
                        "printed_ordinal": printed_ord,
                        "page_start": it_dict.get("page_start") or it_dict.get("printed_page"),
                        "page_end": it_dict.get("page_end"),
                        "position": it_pos * 1024,
                        "descriptor": descriptor,
                        "chapter_id": resolved_ch_id,
                        "subject_key": subject_key or (subject.key if subject else ""),
                        "chapter_key": resolved_ch_key,
                        "map_status": EditionItem.MapStatus.CONFIRMED,
                        "change_kind": EditionItem.ChangeKind.NEW,
                        "match_status": EditionItem.MatchStatus.CONFIRMED,
                    },
                )
                total_items_seeded += 1

        work.item_count_cached = total_items_seeded
        work.save(update_fields=["item_count_cached"])

        if publish:
            try:
                mat_services.publish_edition(actor_id=SEED_ACTOR_ID, edition_id=edition.id)
                self.stdout.write(self.style.SUCCESS(f"  -> Published edition '{edition.label}' to CURRENT."))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  -> Could not auto-publish edition: {e}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"  -> Ingested Work '{work.title}' ({work.work_key}): "
                f"Edition '{edition.label}', {len(units_data)} units, {total_items_seeded} items."
            )
        )
