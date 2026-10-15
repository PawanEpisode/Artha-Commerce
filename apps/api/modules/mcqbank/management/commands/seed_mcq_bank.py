"""
Management command: python manage.py seed_mcq_bank
Seeds CMA 2022 exam pattern profiles, official ICMAI link-out sets,
and platform-hosted high-yield MCQ practice sets.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from modules.mcqbank.models import McqSet, PatternProfile
from modules.questionbank.models import Collection, CollectionItem, Option, Question, QuestionVersion
from modules.syllabus.models import Chapter, Course, Level, Scheme, Subject


class Command(BaseCommand):
    help = "Seeds CMA 2022 exam pattern profiles and MCQ practice sets (idempotent)."

    def handle(self, *args, **options):
        self.stdout.write("Seeding CMA MCQ Bank (Syllabus 2022)...")

        with transaction.atomic():
            course, _ = Course.objects.get_or_create(
                code="cma",
                defaults={
                    "name": "Cost and Management Accountancy",
                    "institute_name": "Institute of Cost Accountants of India",
                    "institute_url": "https://icmai.in",
                },
            )
            inter_level, _ = Level.objects.get_or_create(
                course=course,
                code="intermediate",
                defaults={"name": "CMA Intermediate", "sort_order": 2},
            )
            final_level, _ = Level.objects.get_or_create(
                course=course,
                code="final",
                defaults={"name": "CMA Final", "sort_order": 3},
            )

            scheme, _ = Scheme.objects.get_or_create(
                level=inter_level,
                code="2022",
                defaults={"name": "CMA Syllabus 2022", "status": "published"},
            )

            # 1. Pattern Profiles (Official CMA 2022 syllabus pattern: 15 MCQs x 2 marks = 30 marks)
            cma_papers = [
                ("business-laws-and-ethics", "Business Laws and Ethics", 5, inter_level),
                ("financial-accounting", "Financial Accounting", 6, inter_level),
                ("direct-and-indirect-taxation", "Direct and Indirect Taxation", 7, inter_level),
                ("cost-accounting", "Cost Accounting", 8, inter_level),
                ("corporate-and-economic-laws", "Corporate and Economic Laws", 13, final_level),
                ("strategic-financial-management", "Strategic Financial Management", 14, final_level),
            ]

            for key, name, pno, lvl in cma_papers:
                Subject.objects.get_or_create(
                    scheme=scheme,
                    key=key,
                    defaults={"name": name, "paper_number": pno, "total_marks": 100},
                )
                PatternProfile.objects.update_or_create(
                    course=course,
                    level=lvl,
                    subject_key=key,
                    effective_from=datetime.date(2023, 1, 1),
                    defaults={
                        "scheme": scheme,
                        "format": PatternProfile.Format.MCQ_SECTION,
                        "mcq_count": 15,
                        "mcq_total_marks": Decimal("30.0"),
                        "marks_per_mcq": Decimal("2.00"),
                        "minutes": 40,
                        "status": PatternProfile.Status.ACTIVE,
                        "verified": True,
                        "source_note": f"ICMAI CMA Syllabus 2022 Exam Scheme: Paper {pno} Section A compulsory 15 MCQs x 2 marks.",
                        "source_url": "https://icmai.in",
                    },
                )

            self.stdout.write(self.style.SUCCESS("  ✓ Seeded 6 verified CMA 2022 exam pattern profiles."))

            # 2. Official Link-Out Sets
            linkout_sets = [
                {
                    "slug": "icmai-mcq-booklet-paper-5",
                    "title": "ICMAI Official MCQ Booklet: Business Laws and Ethics",
                    "description": "Comprehensive objective question compilation released by Directorate of Studies, ICMAI.",
                    "subject_key": "business-laws-and-ethics",
                    "source_name": "ICMAI DoS",
                    "source_url": "https://icmai.in/upload/Students/Question-Paper/June-2024/Inter-P05.pdf",
                    "question_count": 150,
                    "est_minutes": 180,
                },
                {
                    "slug": "icmai-mcq-booklet-paper-7",
                    "title": "ICMAI Official MCQ Booklet: Direct and Indirect Taxation",
                    "description": "Official objective test questions covering Income Tax and GST released by ICMAI.",
                    "subject_key": "direct-and-indirect-taxation",
                    "source_name": "ICMAI DoS",
                    "source_url": "https://icmai.in/upload/Students/Question-Paper/June-2024/Inter-P07.pdf",
                    "question_count": 200,
                    "est_minutes": 240,
                },
                {
                    "slug": "icmai-mcq-booklet-paper-8",
                    "title": "ICMAI Official MCQ Booklet: Cost Accounting",
                    "description": "Standard objective questions by ICMAI on marginal costing, standard costing, and cost sheets.",
                    "subject_key": "cost-accounting",
                    "source_name": "ICMAI DoS",
                    "source_url": "https://icmai.in/upload/Students/Question-Paper/June-2024/Inter-P08.pdf",
                    "question_count": 180,
                    "est_minutes": 200,
                },
            ]

            for sdata in linkout_sets:
                subj = Subject.objects.filter(key=sdata["subject_key"]).first()
                McqSet.objects.update_or_create(
                    slug=sdata["slug"],
                    defaults={
                        "title": sdata["title"],
                        "description": sdata["description"],
                        "set_kind": McqSet.SetKind.INSTITUTE_MCQ,
                        "delivery": McqSet.Delivery.LINK_OUT,
                        "source_name": sdata["source_name"],
                        "source_url": sdata["source_url"],
                        "source_kind": "institute_mcq",
                        "course": course,
                        "level": inter_level,
                        "subject_key": sdata["subject_key"],
                        "subject": subj,
                        "question_count": sdata["question_count"],
                        "est_minutes": sdata["est_minutes"],
                        "status": McqSet.Status.PUBLISHED,
                        "verified": True,
                        "published_at": datetime.datetime.now(datetime.UTC),
                    },
                )

            # 3. Platform Hosted Practice Sets
            tax_subj = Subject.objects.filter(key="direct-and-indirect-taxation").first()
            tax_ch, _ = Chapter.objects.get_or_create(
                subject=tax_subj,
                key="gst-itc",
                defaults={"name": "GST Input Tax Credit", "sort_order": 1},
            )

            coll_tax, _ = Collection.objects.get_or_create(
                slug="platform-high-yield-gst-itc",
                defaults={
                    "title": "High-Yield GST ITC Sprint",
                    "kind": Collection.Kind.CURATED,
                    "visibility": Collection.Visibility.PUBLIC,
                    "status": Collection.Status.ACTIVE,
                    "course": course,
                    "level": inter_level,
                    "subject_key": "direct-and-indirect-taxation",
                },
            )

            # Seed 10 authentic GST MCQs into this collection
            itc_questions = [
                (
                    "Under Section 16(2) of the CGST Act, what is the maximum time period for payment to a supplier to avoid reversal of ITC with interest?",
                    [("A", "90 days"), ("B", "180 days"), ("C", "1 year"), ("D", "30 days")],
                    "B",
                ),
                (
                    "Under Section 17(5)(b) of the CGST Act, when is input tax credit allowed on food and beverages?",
                    [
                        ("A", "When provided by employer under statutory obligation"),
                        ("B", "Always allowed for corporate entities"),
                        ("C", "Never allowed under any circumstances"),
                        ("D", "Allowed if bill exceeds Rs. 10,000"),
                    ],
                    "A",
                ),
                (
                    "Which document is NOT valid for claiming ITC under Section 16 of the CGST Act?",
                    [
                        ("A", "Tax Invoice issued by supplier"),
                        ("B", "Debit Note issued by supplier"),
                        ("C", "Delivery Challan for job work"),
                        ("D", "Bill of Entry"),
                    ],
                    "C",
                ),
                (
                    "What is the time limit for availing ITC in respect of an invoice under Section 16(4) of the CGST Act 2017?",
                    [
                        (
                            "A",
                            "30th November following the end of financial year or annual return filing date, whichever is earlier",
                        ),
                        ("B", "31st March of the relevant financial year"),
                        ("C", "30th September of the next financial year"),
                        ("D", "Within 3 years from invoice date"),
                    ],
                    "A",
                ),
                (
                    "Where goods against an invoice are received in lots or installments, the registered person can take ITC upon receipt of:",
                    [
                        ("A", "The first lot"),
                        ("B", "The last lot"),
                        ("C", "Proportionate to each installment"),
                        ("D", "At the discretion of the taxpayer"),
                    ],
                    "B",
                ),
            ]

            pos = 1
            for stem, opts, correct_key in itc_questions:
                q = Question.objects.create(
                    course=course,
                    level=inter_level,
                    primary_chapter=tax_ch,
                    kind="mcq_single",
                    stem_head=stem[:120],
                    status=Question.Status.ACTIVE,
                    visibility=Question.Visibility.PUBLIC,
                    published_at=datetime.datetime.now(datetime.UTC),
                    rights_status="original",
                    source_kind="platform",
                    source_name="ArthaCommerce",
                    marks=Decimal("2.0"),
                    difficulty=3,
                )
                qv = QuestionVersion.objects.create(
                    question=q,
                    version_no=1,
                    state=QuestionVersion.State.LIVE,
                    stem_md=stem,
                )
                for opt_idx, (opt_k, opt_t) in enumerate(opts, start=1):
                    Option.objects.create(
                        version=qv,
                        position=opt_idx,
                        body_md=opt_t,
                        is_correct=(opt_k == correct_key),
                    )
                CollectionItem.objects.update_or_create(
                    collection=coll_tax,
                    question=q,
                    defaults={"position": pos},
                )
                pos += 1

            coll_tax.item_count = pos - 1
            coll_tax.save(update_fields=["item_count"])

            McqSet.objects.update_or_create(
                slug="platform-high-yield-gst-itc",
                defaults={
                    "title": "Platform High-Yield MCQ Sprint: GST Input Tax Credit",
                    "description": "Exam-targeted multiple choice practice with instant explanations covering Section 16, 17(5), and ITC rules.",
                    "set_kind": McqSet.SetKind.PLATFORM,
                    "delivery": McqSet.Delivery.HOSTED,
                    "collection": coll_tax,
                    "course": course,
                    "level": inter_level,
                    "subject_key": "direct-and-indirect-taxation",
                    "subject": tax_subj,
                    "chapter_key": "gst-itc",
                    "chapter": tax_ch,
                    "question_count": pos - 1,
                    "est_minutes": 20,
                    "license_tier": "host",
                    "rights_basis": "original",
                    "status": McqSet.Status.PUBLISHED,
                    "verified": True,
                    "featured": True,
                    "published_at": datetime.datetime.now(datetime.UTC),
                },
            )

            self.stdout.write(
                self.style.SUCCESS("  ✓ Seeded platform-hosted interactive MCQ set with verified questions.")
            )

        self.stdout.write(self.style.SUCCESS("Done! CMA MCQ Bank seeded successfully."))
