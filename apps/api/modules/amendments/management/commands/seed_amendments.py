from __future__ import annotations

from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from modules.amendments.models import Amendment, ChangeVersion, RevisionTerm
from modules.amendments.services import (
    create_amendment_draft,
    release_revision,
    set_revision_scope,
    stage_change_card,
)
from modules.syllabus.models import Chapter, Course, Level, Scheme, Subject


class Command(BaseCommand):
    help = "Seeds verified statutory amendments for CA Intermediate Paper 3 Taxation (May 2026 attempt)."

    def handle(self, *args, **options):
        with transaction.atomic():
            # 1. Resolve or create syllabus entities
            course, _ = Course.objects.get_or_create(code="ca", defaults={"name": "Chartered Accountancy"})
            level, _ = Level.objects.get_or_create(
                course=course,
                code="intermediate",
                defaults={"name": "Intermediate", "sort_order": 2},
            )
            scheme, _ = Scheme.objects.get_or_create(
                level=level,
                code="2023",
                defaults={"name": "2023 Scheme", "status": Scheme.Status.PUBLISHED},
            )
            subject, _ = Subject.objects.get_or_create(
                scheme=scheme,
                key="taxation",
                defaults={
                    "name": "Taxation",
                    "paper_number": 3,
                    "total_marks": 100,
                },
            )
            chapter_gst, _ = Chapter.objects.get_or_create(
                subject=subject,
                key="gst-itc",
                defaults={"name": "GST: Input Tax Credit", "sort_order": 1},
            )
            chapter_dt, _ = Chapter.objects.get_or_create(
                subject=subject,
                key="heads-of-income",
                defaults={"name": "Income Tax: Heads of Income", "sort_order": 2},
            )

            # 2. Check if already seeded
            doc_key = "statutory_update:taxation:2026-05:may-2026"
            if Amendment.objects.filter(doc_key=doc_key).exists():
                self.stdout.write(self.style.WARNING("Amendment already seeded. Skipping."))
                return

            # 3. Create draft
            amendment, revision = create_amendment_draft(
                course_id=course.id,
                level_id=level.id,
                title="BOS Statutory Update for May 2026 Examination - Paper 3 Taxation",
                short_title="Statutory Update: Taxation (May 2026)",
                doc_key=doc_key,
                kind=Amendment.Kind.STATUTORY_UPDATE,
                issuer_label="ICAI Board of Studies",
                landing_url="https://boslive.icai.org/announcement_details.php?id=522",
                official_url="https://boslive.icai.org/assets/statutory_update_may2026.pdf",
                issued_on=date(2025, 11, 15),
            )

            # 4. Set paper scope and terms
            set_revision_scope(
                revision_id=revision.id,
                subjects=[
                    {
                        "subject_id": subject.id,
                        "subject_key": subject.key,
                        "scheme_id": scheme.id,
                        "level_id": level.id,
                    }
                ],
                terms=[
                    {
                        "term_code": "2026-05",
                        "applicability": RevisionTerm.Applicability.APPLIES,
                        "cutoff_date": date(2025, 10, 31),
                        "cutoff_note": "Amendments issued up to 31 Oct 2025 are applicable for May 2026 examination.",
                        "source_page": 1,
                    },
                    {
                        "term_code": "2026-11",
                        "applicability": RevisionTerm.Applicability.APPLIES,
                        "source_page": 1,
                    },
                ],
            )

            # 5. Add Cards
            # Card 1: Section 17(5)(d) CGST
            stage_change_card(
                revision_id=revision.id,
                law_key="cgst_act_2017",
                provision_label="Section 17(5)(d)",
                provision_keys=["cgst:17(5)(d)"],
                change_type=ChangeVersion.ChangeType.MODIFICATION,
                title="Input Tax Credit on goods/services received for construction of plant and machinery",
                summary_old="ITC was restricted on goods or services received by a taxable person for construction of an immovable property.",
                summary_new="The scope of plant and machinery is clarified; works contract services for apparatus and equipment fixed to earth by foundation are allowed.",
                effective_from_term_code="2026-05",
                materiality=ChangeVersion.Materiality.HIGH,
                source_page=12,
                evidence_quote="Section 17(5)(d) explanation modified to affirm eligibility for equipment mounted on foundations.",
                chapter_mappings=[
                    {
                        "subject_id": subject.id,
                        "subject_key": subject.key,
                        "chapter_id": chapter_gst.id,
                        "chapter_key": chapter_gst.key,
                        "is_primary": True,
                    }
                ],
            )

            # Card 2: Section 115BAC Income Tax
            stage_change_card(
                revision_id=revision.id,
                law_key="income_tax_act_1961",
                provision_label="Section 115BAC",
                provision_keys=["income_tax:115bac"],
                change_type=ChangeVersion.ChangeType.MODIFICATION,
                title="Revisions to default concessional tax regime rate slabs and standard deduction",
                summary_old="Standard deduction under default regime was ₹50,000 with basic exemption limit of ₹3,00,000.",
                summary_new="Standard deduction increased to ₹75,000 for salaried employees; revised slab tax rates updated under Section 115BAC(1A).",
                effective_from_term_code="2026-05",
                materiality=ChangeVersion.Materiality.HIGH,
                source_page=18,
                evidence_quote="Finance Act revised slabs for Section 115BAC default tax regime applicable from AY 2025-26 onwards.",
                chapter_mappings=[
                    {
                        "subject_id": subject.id,
                        "subject_key": subject.key,
                        "chapter_id": chapter_dt.id,
                        "chapter_key": chapter_dt.key,
                        "is_primary": True,
                    }
                ],
            )

            # Card 3: Section 43B(h) MSME Payment Rule
            stage_change_card(
                revision_id=revision.id,
                law_key="income_tax_act_1961",
                provision_label="Section 43B(h)",
                provision_keys=["income_tax:43b(h)"],
                change_type=ChangeVersion.ChangeType.ADDITION,
                title="Disallowance of expenditure for delayed payments to Micro and Small enterprises",
                summary_old="Payments to MSME suppliers were deductible on accrual basis irrespective of actual payment date within the year.",
                summary_new="Any sum payable to a micro or small enterprise beyond the time limit specified in section 15 of MSMED Act, 2006 is allowed only on actual payment.",
                effective_from_term_code="2026-05",
                materiality=ChangeVersion.Materiality.NORMAL,
                source_page=22,
                evidence_quote="Section 43B clause (h) inserted to enforce 45-day payment window for MSME suppliers.",
                chapter_mappings=[
                    {
                        "subject_id": subject.id,
                        "subject_key": subject.key,
                        "chapter_id": chapter_dt.id,
                        "chapter_key": chapter_dt.key,
                        "is_primary": True,
                    }
                ],
            )

            # Card 4: Clarification - Applicability scope
            stage_change_card(
                revision_id=revision.id,
                provision_label="Applicability Cut-off",
                change_type=ChangeVersion.ChangeType.CLARIFICATION,
                title="Clarification on Finance Act cut-off date for May 2026 examinations",
                summary_old="",
                summary_new="All notifications, circulars and statutory pronouncements issued up to 31 October 2025 are strictly applicable. Any notifications issued after 31 October 2025 are excluded.",
                effective_from_term_code="2026-05",
                materiality=ChangeVersion.Materiality.LOW,
                source_page=2,
                evidence_quote="BOS announcement confirms 31st October 2025 as the firm cut-off date for May 2026 examination sitting.",
                chapter_mappings=[],
            )

            # 6. Release revision atomically
            release_revision(revision_id=revision.id)

            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully seeded and released Amendment '{amendment.public_id}' with 4 change cards."
                )
            )
