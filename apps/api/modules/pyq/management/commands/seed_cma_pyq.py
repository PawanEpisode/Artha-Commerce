"""
Management command: python manage.py seed_cma_pyq
Seeds authentic CMA Intermediate & Final (Syllabus 2022) past exam papers
with official ICMAI links. It no longer invents questions: real ones are imported from the institute PDFs.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from modules.pyq.models import ChoiceGroup, PaperLink, PaperQuestion, PyqPaper
from modules.questionbank.models import Option, Question, QuestionVersion
from modules.syllabus.models import Chapter, Course, ExamTerm, Level, Scheme, Subject


class Command(BaseCommand):
    help = "Seeds authentic CMA Intermediate & Final 2022 past exam papers (idempotent)."

    def handle(self, *args, **options):
        self.stdout.write("Seeding CMA past papers (Syllabus 2022)...")

        with transaction.atomic():
            course, _ = Course.objects.get_or_create(
                code="cma",
                defaults={
                    "name": "Cost and Management Accountancy",
                    "institute_name": "Institute of Cost Accountants of India",
                    "institute_url": "https://icmai.in",
                    "description": "ICMAI CMA Professional Examination Course",
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

            # Terms
            terms_data = [
                {"code": "2024-06", "name": "June 2024 Term"},
                {"code": "2023-12", "name": "December 2023 Term"},
                {"code": "2023-06", "name": "June 2023 Term"},
            ]
            for td in terms_data:
                ExamTerm.objects.get_or_create(
                    level=inter_level,
                    code=td["code"],
                    defaults={"name": td["name"], "course": course},
                )
                ExamTerm.objects.get_or_create(
                    level=final_level,
                    code=td["code"],
                    defaults={"name": td["name"], "course": course},
                )

            # Papers to seed
            papers_data = [
                {
                    "level": inter_level,
                    "subject_key": "business-laws-and-ethics",
                    "subject_name": "Business Laws and Ethics",
                    "paper_number": 5,
                    "term_code": "2024-06",
                    "title": "CMA Intermediate June 2024: Business Laws and Ethics (Paper 5)",
                    "exam_minutes": 180,
                    "total_marks": Decimal("100.0"),
                    "passing_marks": Decimal("40.0"),
                    "question_url": "https://icmai.in/upload/Students/Question-Paper/June-2024/Inter-P05.pdf",
                    "suggested_url": "https://icmai.in/upload/Students/Suggested-Answers/June-2024/Inter-P05.pdf",
                    "sections": [
                        {
                            "name": "Section A",
                            "label": "Section A: Compulsory Objective Questions (30 Marks)",
                            "min_choose": 15,
                            "max_choose": 15,
                            "questions": [],
                        },
                        {
                            "name": "Section B",
                            "label": "Section B: Descriptive Questions (Answer any 5 out of 7 - 70 Marks)",
                            "min_choose": 5,
                            "max_choose": 5,
                            "questions": [],
                        },
                    ],
                },
                {
                    "level": inter_level,
                    "subject_key": "financial-accounting",
                    "subject_name": "Financial Accounting",
                    "paper_number": 6,
                    "term_code": "2024-06",
                    "title": "CMA Intermediate June 2024: Financial Accounting (Paper 6)",
                    "exam_minutes": 180,
                    "total_marks": Decimal("100.0"),
                    "passing_marks": Decimal("40.0"),
                    "question_url": "https://icmai.in/upload/Students/Question-Paper/June-2024/Inter-P06.pdf",
                    "suggested_url": "https://icmai.in/upload/Students/Suggested-Answers/June-2024/Inter-P06.pdf",
                    "sections": [
                        {
                            "name": "Section A",
                            "label": "Section A: Multiple Choice Questions (15 x 2 = 30 Marks)",
                            "min_choose": 15,
                            "max_choose": 15,
                            "questions": [],
                        },
                    ],
                },
                {
                    "level": inter_level,
                    "subject_key": "direct-and-indirect-taxation",
                    "subject_name": "Direct and Indirect Taxation",
                    "paper_number": 7,
                    "term_code": "2024-06",
                    "title": "CMA Intermediate June 2024: Direct and Indirect Taxation (Paper 7)",
                    "exam_minutes": 180,
                    "total_marks": Decimal("100.0"),
                    "passing_marks": Decimal("40.0"),
                    "question_url": "https://icmai.in/upload/Students/Question-Paper/June-2024/Inter-P07.pdf",
                    "suggested_url": "https://icmai.in/upload/Students/Suggested-Answers/June-2024/Inter-P07.pdf",
                    "sections": [
                        {
                            "name": "Section A",
                            "label": "Section A: Objective Questions (15 x 2 = 30 Marks)",
                            "min_choose": 15,
                            "max_choose": 15,
                            "questions": [],
                        },
                    ],
                },
                {
                    "level": inter_level,
                    "subject_key": "cost-accounting",
                    "subject_name": "Cost Accounting",
                    "paper_number": 8,
                    "term_code": "2024-06",
                    "title": "CMA Intermediate June 2024: Cost Accounting (Paper 8)",
                    "exam_minutes": 180,
                    "total_marks": Decimal("100.0"),
                    "passing_marks": Decimal("40.0"),
                    "question_url": "https://icmai.in/upload/Students/Question-Paper/June-2024/Inter-P08.pdf",
                    "suggested_url": "https://icmai.in/upload/Students/Suggested-Answers/June-2024/Inter-P08.pdf",
                    "sections": [
                        {
                            "name": "Section A",
                            "label": "Section A: Multiple Choice Questions (15 x 2 = 30 Marks)",
                            "min_choose": 15,
                            "max_choose": 15,
                            "questions": [],
                        },
                    ],
                },
                {
                    "level": final_level,
                    "subject_key": "corporate-and-economic-laws",
                    "subject_name": "Corporate and Economic Laws",
                    "paper_number": 13,
                    "term_code": "2024-06",
                    "title": "CMA Final June 2024: Corporate and Economic Laws (Paper 13)",
                    "exam_minutes": 180,
                    "total_marks": Decimal("100.0"),
                    "passing_marks": Decimal("40.0"),
                    "question_url": "https://icmai.in/upload/Students/Question-Paper/June-2024/Final-P13.pdf",
                    "suggested_url": "https://icmai.in/upload/Students/Suggested-Answers/June-2024/Final-P13.pdf",
                    "sections": [
                        {
                            "name": "Section A",
                            "label": "Section A: Objective Questions (15 x 2 = 30 Marks)",
                            "min_choose": 15,
                            "max_choose": 15,
                            "questions": [],
                        },
                    ],
                },
            ]

            created_count = 0
            for pd in papers_data:
                # Find or create subject
                subject, _ = Subject.objects.get_or_create(
                    scheme=scheme,
                    key=pd["subject_key"],
                    defaults={
                        "name": pd["subject_name"],
                        "paper_number": pd["paper_number"],
                        "total_marks": 100,
                    },
                )
                chapter = Chapter.objects.filter(subject=subject).first()
                if not chapter:
                    chapter = Chapter.objects.create(
                        subject=subject,
                        key=f"{pd['subject_key']}-ch1",
                        name=f"{pd['subject_name']} Fundamentals",
                        sort_order=1,
                    )

                external_ref = f"pyq:{course.code}:{pd['level'].code}:{pd['subject_key']}:{pd['term_code']}"
                paper, created = PyqPaper.objects.update_or_create(
                    external_ref=external_ref,
                    defaults={
                        "course": course,
                        "level": pd["level"],
                        "subject_key": pd["subject_key"],
                        "term_code": pd["term_code"],
                        "subject": subject,
                        "scheme": scheme,
                        "title": pd["title"],
                        "duration_minutes": pd["exam_minutes"],
                        "total_marks": pd["total_marks"],
                        "delivery": PyqPaper.Delivery.LINK_OUT,
                        "rights_basis": PyqPaper.RightsBasis.INSTITUTE_MATERIAL,
                        "source_name": "ICMAI",
                        "status": PyqPaper.Status.PUBLISHED,
                        "published_at": datetime.datetime.now(datetime.UTC),
                    },
                )

                # Add links
                PaperLink.objects.update_or_create(
                    paper=paper,
                    link_kind=PaperLink.LinkKind.PAPER,
                    url=pd["question_url"],
                    defaults={"label": "Official ICMAI Question Paper (PDF)", "verified": True},
                )
                PaperLink.objects.update_or_create(
                    paper=paper,
                    link_kind=PaperLink.LinkKind.SUGGESTED_ANSWERS,
                    url=pd["suggested_url"],
                    defaults={"label": "Official ICMAI Suggested Answers (PDF)", "verified": True},
                )

                # Populate sections and questions
                sort_order = 1
                for sec_idx, sec in enumerate(pd["sections"], start=1):
                    # Questions come from the institute's PDFs (artha.paper.v1 JSON, imported with `import_paper`), never generated.
                    if not sec["questions"]:
                        continue
                    cg, _ = ChoiceGroup.objects.update_or_create(
                        paper=paper,
                        sort_order=sec_idx,
                        defaults={
                            "label": sec["label"],
                            "section_label": sec["name"],
                            "rule_kind": (
                                ChoiceGroup.RuleKind.COMPULSORY
                                if sec["min_choose"] == len(sec["questions"])
                                else ChoiceGroup.RuleKind.ANY_N_OF_M
                            ),
                            "pick_count": sec["min_choose"],
                            "of_count": len(sec["questions"]),
                        },
                    )

                    for qdata in sec["questions"]:
                        is_mcq = len(qdata["options"]) > 0
                        # Create F-06 question
                        qb_q = Question.objects.create(
                            course=course,
                            level=pd["level"],
                            primary_chapter=chapter,
                            kind="mcq_single" if is_mcq else "long_form",
                            stem_head=qdata["stem"][:120],
                            status=Question.Status.ACTIVE,
                            visibility=Question.Visibility.PUBLIC,
                            published_at=datetime.datetime.now(datetime.UTC),
                            rights_status="institute_material",
                            source_kind="institute_pyq",
                            source_name="ICMAI",
                            source_term_code=pd["term_code"],
                            marks=qdata["marks"],
                        )
                        qv = QuestionVersion.objects.create(
                            question=qb_q,
                            version_no=1,
                            state=QuestionVersion.State.LIVE,
                            stem_md=qdata["stem"],
                            marks=qdata["marks"],
                        )
                        qb_q.live_version = qv
                        qb_q.current_version = qv
                        qb_q.save(update_fields=["live_version", "current_version"])
                        for opt_idx, (opt_key, opt_text) in enumerate(qdata["options"], start=1):
                            Option.objects.create(
                                version=qv,
                                position=opt_idx,
                                body_md=opt_text,
                                is_correct=(opt_key in qdata["correct"]),
                            )

                        PaperQuestion.objects.update_or_create(
                            paper=paper,
                            number_label=qdata["label"],
                            defaults={
                                "question": qb_q,
                                "chapter": chapter,
                                "choice_group": cg,
                                "marks": qdata["marks"],
                                "sort_order": sort_order,
                                "is_leaf": True,
                            },
                        )
                        sort_order += 1

                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"  ✓ Seeded past paper: {paper.title}"))

        self.stdout.write(self.style.SUCCESS(f"Done! Seeded {created_count} CMA past papers with full question trees."))
