"""
Domain service to ingest ICMAI Study Material Paper-Books into F-12 models.
Maps Foundation, Intermediate, and Final paper books to their syllabus subjects,
creates Works, Editions, Units, and connects them with PDF reader CDN URLs.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any

from django.db import transaction
from django.utils import timezone

from modules.material import services as mat_services
from modules.material.domain import labels, term
from modules.material.models import Edition, EditionItem, Item, Provider, Unit, UnitChapter, Work
from modules.syllabus.models import Chapter, Course, Level, Scheme, Subject

CMA_BOOKS_MAP = {
    # Final (Papers 13 to 20A)
    "13": ("corporate-and-economic-laws", "Paper 13: Corporate and Economic Laws", "final"),
    "14": ("strategic-financial-management", "Paper 14: Strategic Financial Management", "final"),
    "15": ("direct-tax-laws-and-international-taxation", "Paper 15: Direct Tax Laws and International Taxation", "final"),
    "16": ("strategic-cost-management", "Paper 16: Strategic Cost Management", "final"),
    "17": ("cost-and-management-audit", "Paper 17: Cost and Management Audit", "final"),
    "18": ("corporate-financial-reporting", "Paper 18: Corporate Financial Reporting", "final"),
    "19": ("indirect-tax-laws-and-practice", "Paper 19: Indirect Tax Laws and Practice", "final"),
    "20A": ("strategic-performance-management-and-business-valuation", "Paper 20A: Strategic Performance Management and Business Valuation", "final"),
    # Intermediate (Papers 5 to 12)
    "5": ("business-laws-and-ethics", "Paper 5: Business Laws and Ethics", "intermediate"),
    "6": ("financial-accounting", "Paper 6: Financial Accounting", "intermediate"),
    "7": ("direct-and-indirect-taxation", "Paper 7: Direct and Indirect Taxation", "intermediate"),
    "7A": ("direct-and-indirect-taxation", "Paper 7A: Direct Taxation", "intermediate"),
    "7B": ("direct-and-indirect-taxation", "Paper 7B: Indirect Taxation", "intermediate"),
    "8": ("cost-accounting", "Paper 8: Cost Accounting", "intermediate"),
    "9": ("operations-management-and-strategic-management", "Paper 9: Operations Management and Strategic Management", "intermediate"),
    "10": ("corporate-accounting-and-auditing", "Paper 10: Corporate Accounting and Auditing", "intermediate"),
    "11": ("financial-management-and-business-data-analytics", "Paper 11: Financial Management and Business Data Analytics", "intermediate"),
    "12": ("management-accounting", "Paper 12: Management Accounting", "intermediate"),
    # Foundation (Papers 1 to 4)
    "1": ("fundamentals-of-business-laws-and-business-communication", "Paper 1: Fundamentals of Business Laws and Business Communication", "foundation"),
    "2": ("fundamentals-of-financial-and-cost-accounting", "Paper 2: Fundamentals of Financial and Cost Accounting", "foundation"),
    "3": ("fundamentals-of-business-mathematics-and-statistics", "Paper 3: Fundamentals of Business Mathematics and Statistics", "foundation"),
    "4": ("fundamentals-of-business-economics-and-management", "Paper 4: Fundamentals of Business Economics and Management", "foundation"),
}

SEED_ACTOR_ID = uuid.uuid5(uuid.NAMESPACE_URL, "https://arthacommerce.in/material/seed-loader")


def extract_book_paper_num(file_path: Path) -> str:
    name = file_path.name.lower()
    m = re.search(r'paper[-_\s]*([0-9]{1,2}[a-z]?)', name)
    if m:
        return m.group(1).upper()
    m2 = re.search(r'p([0-9]{1,2}[a-z]?)', name)
    if m2:
        return m2.group(1).upper()
    return "13"


def ingest_paper_book(
    book_pdf_path: Path,
    *,
    cdn_base_url: str = "https://bqkglnfdhkidajeqlebl.supabase.co/storage/v1/object/public/study-material",
) -> Work:
    """
    Ingests a single ICMAI paper book PDF into Work and Edition models.
    """
    paper_num = extract_book_paper_num(book_pdf_path)
    paper_meta = CMA_BOOKS_MAP.get(paper_num, ("corporate-and-economic-laws", f"Paper {paper_num}", "final"))
    subject_key, work_title, level_code = paper_meta

    rel_path = str(book_pdf_path).split("source-material/study-material/")[-1].lstrip("/")
    cdn_url = f"{cdn_base_url}/{rel_path}"

    with transaction.atomic():
        # 1. Provider
        provider, _ = Provider.objects.get_or_create(
            slug="icmai",
            defaults={
                "name": "Institute of Cost Accountants of India",
                "normalised_name": "institute of cost accountants of india",
                "kind": Provider.Kind.INSTITUTE,
                "ingestion_source_id": uuid.uuid5(uuid.NAMESPACE_URL, "https://icmai.in"),
                "status": Provider.Status.ACTIVE,
                "website_url": "https://icmai.in",
            },
        )

        # 2. Syllabus Entities
        course, _ = Course.objects.get_or_create(code="cma", defaults={"name": "CMA"})
        level, _ = Level.objects.get_or_create(course=course, code=level_code, defaults={"name": level_code.title()})
        scheme = Scheme.objects.filter(level=level, code="2022").first() or Scheme.objects.filter(level=level).first()
        subject = Subject.objects.filter(scheme=scheme, key=subject_key).first() if scheme else None

        # 3. Work
        work_key = f"cma-{level_code}-p{paper_num.lower()}-study-material"
        work, _ = Work.objects.update_or_create(
            provider=provider,
            work_key=work_key,
            defaults={
                "title": f"CMA {level_code.title()} {work_title} - Study Material",
                "kind": Work.Kind.BOOK,
                "course_id": course.id,
                "level_id": level.id,
                "subject_key": subject_key,
                "subject_id": subject.id if subject else None,
                "visibility": Work.Visibility.PUBLIC,
                "status": Work.Status.ACTIVE,
            },
        )

        # 4. Edition
        from_ord, to_ord = term.validate_term_range("2022-01", None)
        edition, _ = Edition.objects.update_or_create(
            work=work,
            label="Syllabus 2022 Official Edition",
            defaults={
                "applies_from_term": "2022-01",
                "applies_from_ord": from_ord,
                "applies_to_term": None,
                "applies_to_ord": to_ord,
                "applicability_note": "Official ICMAI Study Material for Syllabus 2022 examinations.",
                "source_url": cdn_url,
                "source_page_url": "https://icmai.in/studentswebsite/bos.php",
                "page_offset": 10,
                "status": Edition.Status.CURRENT,
                "published_at": timezone.now(),
                "published_by": SEED_ACTOR_ID,
            },
        )

        # 5. Populate chapters from Syllabus
        if subject:
            chapters = Chapter.objects.filter(subject=subject).order_by("sort_order")
            for idx, ch in enumerate(chapters, start=1):
                unit_key = f"u-{ch.key[:100]}"
                unit_obj, _ = Unit.objects.update_or_create(
                    edition=edition,
                    unit_key=unit_key,
                    defaults={
                        "module_label": "Study Material",
                        "printed_number": f"Chapter {idx}",
                        "title": ch.name,
                        "sort_order": idx,
                    },
                )
                UnitChapter.objects.update_or_create(
                    unit=unit_obj,
                    chapter_id=ch.id,
                    defaults={
                        "subject_key": subject.key[:80],
                        "chapter_key": ch.key[:100],
                        "scheme_id": scheme.id if scheme else uuid.uuid4(),
                        "is_primary": True,
                        "status": UnitChapter.Status.CONFIRMED,
                        "origin": UnitChapter.Origin.EDITOR,
                    },
                )

        return work


def resolve_source_path(target: Path | str) -> Path:
    """
    Resolves target path whether running from repo root or apps/api directory.
    """
    p = Path(target)
    if p.is_absolute() and p.exists():
        return p
    cwd = Path.cwd()
    for candidate in [cwd, cwd.parent, cwd.parent.parent]:
        attempt = candidate / p
        if attempt.exists():
            return attempt
    return p


def find_all_paper_books(base_dir: Path | str = "Docs/source-material/study-material") -> list[Path]:
    """
    Scans base_dir for all ICMAI Paper-Book PDFs.
    """
    base = resolve_source_path(base_dir)
    if not base.exists():
        return []
    return sorted([
        f for f in base.rglob("*.pdf")
        if "postal" not in f.name.lower() and "amendment" not in str(f).lower()
    ])

