"""
python manage.py seed_cma_amendments [--materials-dir DIR] [--upload]
Ingests verified statutory amendments from the 17 ICMAI supplementary booklets for CMA Intermediate and Final (Syllabus 2022).
Enforces attempt-wise applicability (2026-06 vs 2026-12), maps change cards directly to CMA chapters,
and sets `official_url` to the Supabase Storage CDN public URL for high-availability student access.
"""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from core.storage import get_storage, public_url
from modules.amendments.models import Amendment, ChangeVersion, RevisionTerm
from modules.amendments.services import (
    create_amendment_draft,
    release_revision,
    set_revision_scope,
    stage_change_card,
)
from modules.syllabus.models import Chapter, Course, Level, Scheme, Subject

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None


class Command(BaseCommand):
    help = "Seeds verified statutory amendments for CMA Intermediate and Final using Supabase CDN URLs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--materials-dir",
            default="docs/source-material/amendments/cma",
            help="Path to the directory containing CMA supplementary PDF files.",
        )
        parser.add_argument(
            "--upload",
            action="store_true",
            help="Upload all local source PDFs to Supabase Storage bucket.",
        )

    def handle(self, *args, **options):
        materials_dir = Path(options["materials_dir"])
        should_upload = options["upload"]
        bucket = getattr(settings, "SUPABASE_AMENDMENTS_BUCKET", "amendments")

        self.stdout.write(f"Using materials directory: {materials_dir}")
        self.stdout.write(f"Supabase CDN bucket: {bucket}")

        # Optional upload step
        if should_upload:
            self._upload_files_to_storage(materials_dir, bucket)

        with transaction.atomic():
            course = Course.objects.filter(code="cma").first()
            if not course:
                self.stderr.write(self.style.ERROR("CMA course not found in database. Run load_syllabus_seed first."))
                return

            lvl_inter = Level.objects.filter(course=course, code="intermediate").first()
            lvl_final = Level.objects.filter(course=course, code="final").first()
            if not lvl_inter or not lvl_final:
                self.stderr.write(self.style.ERROR("CMA Intermediate or Final level not found."))
                return

            scheme_inter = Scheme.objects.filter(level=lvl_inter, code="2022").first()
            scheme_final = Scheme.objects.filter(level=lvl_final, code="2022").first()
            if not scheme_inter or not scheme_final:
                self.stderr.write(self.style.ERROR("CMA 2022 scheme not found."))
                return

            # Helper for chapter resolution
            def get_ch(subject_obj: Subject, key: str) -> Chapter | None:
                return Chapter.objects.filter(subject=subject_obj, key=key).first()

            # Helper for file metadata
            def get_file_meta(src_rel: str) -> tuple[str, int | None]:
                fp = materials_dir / src_rel
                if not fp.is_file():
                    return "", None
                data = fp.read_bytes()
                sha = hashlib.sha256(data).hexdigest()
                page_cnt = None
                if PdfReader:
                    try:
                        reader = PdfReader(str(fp))
                        page_cnt = len(reader.pages)
                    except Exception:
                        pass
                return sha, page_cnt

            # -----------------------------------------------------------------------
            # 1. CMA INTERMEDIATE (Papers 5, 6, 7, 10)
            # -----------------------------------------------------------------------
            s5_inter = Subject.objects.get(scheme=scheme_inter, paper_number=5)
            s6_inter = Subject.objects.get(scheme=scheme_inter, paper_number=6)
            s7_inter = Subject.objects.get(scheme=scheme_inter, paper_number=7)
            s10_inter = Subject.objects.get(scheme=scheme_inter, paper_number=10)

            ch5_comp = get_ch(s5_inter, "companies-act-2013")
            ch6_acc = get_ch(s6_inter, "accounting-standards") or Chapter.objects.filter(subject=s6_inter).first()
            ch7_dt = get_ch(s7_inter, "heads-of-income")
            ch7_gst = get_ch(s7_inter, "goods-and-services-tax-gst-laws")
            ch10_corp = get_ch(s10_inter, "preparation-of-the-statement-of-profit-and-loss-and-balance-sheet-as-per-schedule-iii-of-companies-a") or Chapter.objects.filter(subject=s10_inter).first()

            # -----------------------------------------------------------------------
            # 2. CMA FINAL (Papers 13, 15, 17, 18, 19)
            # -----------------------------------------------------------------------
            s13_final = Subject.objects.get(scheme=scheme_final, paper_number=13)
            s15_final = Subject.objects.get(scheme=scheme_final, paper_number=15)
            s17_final = Subject.objects.get(scheme=scheme_final, paper_number=17)
            s18_final = Subject.objects.get(scheme=scheme_final, paper_number=18)
            s19_final = Subject.objects.get(scheme=scheme_final, paper_number=19)

            ch13_comp = get_ch(s13_final, "the-companies-act-2013")
            ch13_sebi = get_ch(s13_final, "sebi-laws-and-regulations")
            ch13_ibc = get_ch(s13_final, "insolvency-and-bankruptcy-code-2016")
            ch15_dt = get_ch(s15_final, "assessment-of-income-and-computation-of-tax-liability-of-various-entities") or Chapter.objects.filter(subject=s15_final).first()
            ch17_audit = get_ch(s17_final, "companies-cost-records-and-audit-rules-2014-as-amended")
            ch18_std = get_ch(s18_final, "specific-accounting-standards")
            ch19_gst = get_ch(s19_final, "time-of-supply-advanced") or Chapter.objects.filter(subject=s19_final).first()

            # Registry of all 17 booklets
            booklets: list[dict[str, Any]] = [
                # --- INTERMEDIATE JUNE 2026 ---
                {
                    "doc_key": "icmai:cma-intermediate:paper-5:2026-06:supplementary",
                    "level": lvl_inter,
                    "subject": s5_inter,
                    "scheme": scheme_inter,
                    "title": "ICMAI Supplementary - Paper 5 Business Laws and Ethics (June 2026)",
                    "short_title": "Supplementary: Paper 5 (June 2026)",
                    "term_code": "2026-06",
                    "src_rel": "intermediate/2026-06/Supplementary_Paper5_J26.pdf",
                    "storage_path": "cma/intermediate/2026-06/paper-5.pdf",
                    "issued_on": date(2025, 11, 25),
                    "cards": [
                        {
                            "law_key": "companies_act_2013",
                            "provision_label": "Section 135 / CSR Rules",
                            "provision_keys": ["companies_act:135:csr_rules_2025"],
                            "change_type": ChangeVersion.ChangeType.MODIFICATION,
                            "title": "Companies (Corporate Social Responsibility Policy) Amendment Rules, 2025",
                            "summary_old": "CSR compliance relied on annual reporting without real-time technology-driven verification of CSR expenditure.",
                            "summary_new": "Enhanced transparency in CSR fund utilisation with stricter monitoring of ongoing projects and streamlined eligibility criteria under Section 135.",
                            "effective_from_term_code": "2026-06",
                            "materiality": ChangeVersion.Materiality.HIGH,
                            "source_page": 2,
                            "evidence_quote": "MCA notification on 7 July 2025 brought the CSR Amendment Rules into effect from 14 July 2025.",
                            "chapter_mappings": [{"subject_id": s5_inter.id, "subject_key": s5_inter.key, "chapter_id": ch5_comp.id if ch5_comp else None, "chapter_key": ch5_comp.key if ch5_comp else "", "is_primary": True}],
                        },
                        {
                            "law_key": "companies_act_2013",
                            "provision_label": "Listing in Permissible Jurisdictions",
                            "change_type": ChangeVersion.ChangeType.MODIFICATION,
                            "title": "Revised Form LEAP-1 for Unlisted Public Companies Seeking Overseas Listing",
                            "summary_old": "Prior LEAP-1 format had limited cross-border disclosure requirements.",
                            "summary_new": "Replaces Form LEAP-1 requiring mandatory filing within 7 days of prospectus finalisation with detailed regulatory approvals and compliance confirmations.",
                            "effective_from_term_code": "2026-06",
                            "materiality": ChangeVersion.Materiality.NORMAL,
                            "source_page": 2,
                            "evidence_quote": "Companies must file the new Form LEAP-1 within seven days of finalising the prospectus.",
                            "chapter_mappings": [{"subject_id": s5_inter.id, "subject_key": s5_inter.key, "chapter_id": ch5_comp.id if ch5_comp else None, "chapter_key": ch5_comp.key if ch5_comp else "", "is_primary": True}],
                        },
                        {
                            "law_key": "companies_act_2013",
                            "provision_label": "Section 186 / Rule 11(2)",
                            "provision_keys": ["companies_act:186:board_powers"],
                            "change_type": ChangeVersion.ChangeType.CLARIFICATION,
                            "title": "Clarification on 'Business of Financing Industrial Enterprises' for Section 186 Exemptions",
                            "summary_old": "Ambiguity existed over whether NBFC and IFSC financing activities were eligible for Section 186 exemptions.",
                            "summary_new": "Rule 11(2) substituted to expressly include financing by NBFCs, guarantees in ordinary course of business, and operations in International Financial Services Centres (IFSCs).",
                            "effective_from_term_code": "2026-06",
                            "materiality": ChangeVersion.Materiality.HIGH,
                            "source_page": 4,
                            "evidence_quote": "Notification dated 3 November 2025 clarifies exemptions under Section 186 for loans, guarantees and securities.",
                            "chapter_mappings": [{"subject_id": s5_inter.id, "subject_key": s5_inter.key, "chapter_id": ch5_comp.id if ch5_comp else None, "chapter_key": ch5_comp.key if ch5_comp else "", "is_primary": True}],
                        },
                        {
                            "law_key": "companies_act_2013",
                            "provision_label": "Section 134 / Accounts Rules",
                            "change_type": ChangeVersion.ChangeType.ADDITION,
                            "title": "Mandatory POSH Quantitative Data and Maternity Benefit Disclosures in Board's Report",
                            "summary_old": "Board's report required generic statements regarding sexual harassment compliance.",
                            "summary_new": "Mandatory disclosure of quantitative complaints data (received, disposed, pending >90 days) and affirmative declaration of compliance with Maternity Benefit Act, 1961.",
                            "effective_from_term_code": "2026-06",
                            "materiality": ChangeVersion.Materiality.NORMAL,
                            "source_page": 4,
                            "evidence_quote": "Board's Report must now disclose quantitative data regarding sexual harassment complaints pursuant to POSH Act.",
                            "chapter_mappings": [{"subject_id": s5_inter.id, "subject_key": s5_inter.key, "chapter_id": ch5_comp.id if ch5_comp else None, "chapter_key": ch5_comp.key if ch5_comp else "", "is_primary": True}],
                        },
                    ],
                },
                {
                    "doc_key": "icmai:cma-intermediate:paper-7a:2026-06:supplementary",
                    "level": lvl_inter,
                    "subject": s7_inter,
                    "scheme": scheme_inter,
                    "title": "ICMAI Supplementary - Paper 7 Section A Direct Taxation (June 2026)",
                    "short_title": "Supplementary: Paper 7A Direct Tax (June 2026)",
                    "term_code": "2026-06",
                    "src_rel": "intermediate/2026-06/Supplementary_Paper7A_J26.pdf",
                    "storage_path": "cma/intermediate/2026-06/paper-7a.pdf",
                    "issued_on": date(2025, 11, 20),
                    "cards": [
                        {
                            "law_key": "income_tax_act_1961",
                            "provision_label": "Section 206C(1H) & 206AB",
                            "change_type": ChangeVersion.ChangeType.DELETION,
                            "title": "Discontinuation of TCS u/s 206C(1H) on Sale of Goods and Omission of Section 206AB",
                            "summary_old": "TCS was applicable on sale of goods exceeding ₹50 lakhs, and higher TDS/TCS rates applied to non-filers u/s 206AB.",
                            "summary_new": "TCS u/s 206C(1H) is no longer applicable with effect from 01-04-2025, and Section 206AB has been omitted to simplify compliance.",
                            "effective_from_term_code": "2026-06",
                            "materiality": ChangeVersion.Materiality.HIGH,
                            "source_page": 16,
                            "evidence_quote": "TCS u/s 206C(1H) not applicable from 01-04-2025; Sec. 206AB omitted.",
                            "chapter_mappings": [{"subject_id": s7_inter.id, "subject_key": s7_inter.key, "chapter_id": ch7_dt.id if ch7_dt else None, "chapter_key": ch7_dt.key if ch7_dt else "", "is_primary": True}],
                        },
                    ],
                },
                {
                    "doc_key": "icmai:cma-intermediate:paper-7b:2026-06:supplementary",
                    "level": lvl_inter,
                    "subject": s7_inter,
                    "scheme": scheme_inter,
                    "title": "ICMAI Supplementary - Paper 7 Section B Indirect Taxation (June 2026)",
                    "short_title": "Supplementary: Paper 7B Indirect Tax (June 2026)",
                    "term_code": "2026-06",
                    "src_rel": "intermediate/2026-06/Supplementary_Paper7B_J26.pdf",
                    "storage_path": "cma/intermediate/2026-06/paper-7b.pdf",
                    "issued_on": date(2025, 11, 22),
                    "cards": [
                        {
                            "law_key": "cgst_act_2017",
                            "provision_label": "Section 22(1) / Notif 13/2025-CT",
                            "change_type": ChangeVersion.ChangeType.MODIFICATION,
                            "title": "Revised Registration Liability and Threshold Criteria under Section 22(1)",
                            "summary_old": "Threshold exemptions applied with earlier conditions on inter-state taxable supply.",
                            "summary_new": "Clarified supplier liability under Section 22(1) pursuant to Notification 13/2025-CT and 17/2025-CT(R).",
                            "effective_from_term_code": "2026-06",
                            "materiality": ChangeVersion.Materiality.NORMAL,
                            "source_page": 5,
                            "evidence_quote": "Notification No. 13/2025 – Central Tax clarifies liability under Section 22(1) of CGST Act.",
                            "chapter_mappings": [{"subject_id": s7_inter.id, "subject_key": s7_inter.key, "chapter_id": ch7_gst.id if ch7_gst else None, "chapter_key": ch7_gst.key if ch7_gst else "", "is_primary": True}],
                        },
                    ],
                },
                {
                    "doc_key": "icmai:cma-intermediate:paper-10:2026-06:supplementary",
                    "level": lvl_inter,
                    "subject": s10_inter,
                    "scheme": scheme_inter,
                    "title": "ICMAI Supplementary - Paper 10 Corporate Accounting and Auditing (June 2026)",
                    "short_title": "Supplementary: Paper 10 (June 2026)",
                    "term_code": "2026-06",
                    "src_rel": "intermediate/2026-06/Supplementary_Paper10_J26.pdf",
                    "storage_path": "cma/intermediate/2026-06/paper-10.pdf",
                    "issued_on": date(2025, 11, 24),
                    "cards": [
                        {
                            "law_key": "companies_act_2013",
                            "provision_label": "Section 128 / Accounts Rules",
                            "change_type": ChangeVersion.ChangeType.CLARIFICATION,
                            "title": "Audit Trail (Edit Log) Facility Compliance Norms in Accounting Software",
                            "summary_old": "Companies were given transitional leeway regarding audit trail logging features in ERP software.",
                            "summary_new": "Strict statutory verification required by statutory auditors on whether audit trail feature operated throughout the financial year without tampering.",
                            "effective_from_term_code": "2026-06",
                            "materiality": ChangeVersion.Materiality.HIGH,
                            "source_page": 3,
                            "evidence_quote": "Auditors must report on whether company has used accounting software with audit trail feature enabled.",
                            "chapter_mappings": [{"subject_id": s10_inter.id, "subject_key": s10_inter.key, "chapter_id": ch10_corp.id if ch10_corp else None, "chapter_key": ch10_corp.key if ch10_corp else "", "is_primary": True}],
                        },
                    ],
                },

                # --- INTERMEDIATE DEC 2026 ---
                {
                    "doc_key": "icmai:cma-intermediate:paper-5:2026-12:supplementary",
                    "level": lvl_inter,
                    "subject": s5_inter,
                    "scheme": scheme_inter,
                    "title": "ICMAI Supplementary - Paper 5 Business Laws and Ethics (December 2026)",
                    "short_title": "Supplementary: Paper 5 (December 2026)",
                    "term_code": "2026-12",
                    "src_rel": "intermediate/2026-12/Supplementary_Paper 5 for December 2026 Term of Examination (1)_20260828145435.pdf",
                    "storage_path": "cma/intermediate/2026-12/paper-5.pdf",
                    "issued_on": date(2026, 5, 20),
                    "cards": [
                        {
                            "law_key": "companies_act_2013",
                            "provision_label": "Section 2(85) / Small Company",
                            "provision_keys": ["companies_act:2(85):small_company"],
                            "change_type": ChangeVersion.ChangeType.MODIFICATION,
                            "title": "Revision in the Definition and Threshold Limits of 'Small Company'",
                            "summary_old": "Small company threshold limits were governed by earlier limits prescribed in Companies (Specification of Definition Details) Rules.",
                            "summary_new": "Updated thresholds under Section 2(85) notified to provide regulatory relief and procedural concessions to eligible corporate entities.",
                            "effective_from_term_code": "2026-12",
                            "materiality": ChangeVersion.Materiality.HIGH,
                            "source_page": 2,
                            "evidence_quote": "Notification Companies (Specification of Definition Details) Amendment Rules revises Small Company definition limits.",
                            "chapter_mappings": [{"subject_id": s5_inter.id, "subject_key": s5_inter.key, "chapter_id": ch5_comp.id if ch5_comp else None, "chapter_key": ch5_comp.key if ch5_comp else "", "is_primary": True}],
                        },
                        {
                            "law_key": "companies_act_2013",
                            "provision_label": "Schedule VII / ZCZP Instruments",
                            "change_type": ChangeVersion.ChangeType.ADDITION,
                            "title": "Inclusion of Zero Coupon Zero Principal (ZCZP) Instruments in Schedule VII for CSR Expenditure",
                            "summary_old": "Contributions to Social Stock Exchange instruments were not explicitly enumerated under Schedule VII.",
                            "summary_new": "ZCZP instruments issued by non-profit organisations on Social Stock Exchanges are now explicitly eligible as CSR expenditure under Schedule VII.",
                            "effective_from_term_code": "2026-12",
                            "materiality": ChangeVersion.Materiality.HIGH,
                            "source_page": 5,
                            "evidence_quote": "ZCZP instruments specifically included in Schedule VII to the Companies Act, 2013.",
                            "chapter_mappings": [{"subject_id": s5_inter.id, "subject_key": s5_inter.key, "chapter_id": ch5_comp.id if ch5_comp else None, "chapter_key": ch5_comp.key if ch5_comp else "", "is_primary": True}],
                        },
                        {
                            "law_key": "companies_act_2013",
                            "provision_label": "Rule 12A / DIR-3 KYC",
                            "change_type": ChangeVersion.ChangeType.MODIFICATION,
                            "title": "Revision of Fees and Verification Timelines for DIR-3 KYC Web",
                            "summary_old": "Prior fee structure governed late filings of DIR-3 KYC under earlier rules.",
                            "summary_new": "Companies (Registration Offices and Fees) Amendment Rules, 2026 prescribes revised fee slabs and verification norms for director KYC compliance.",
                            "effective_from_term_code": "2026-12",
                            "materiality": ChangeVersion.Materiality.NORMAL,
                            "source_page": 6,
                            "evidence_quote": "Revision in fees for DIR-3 KYC Web notified under Companies (Registration Offices and Fees) Amendment Rules, 2026.",
                            "chapter_mappings": [{"subject_id": s5_inter.id, "subject_key": s5_inter.key, "chapter_id": ch5_comp.id if ch5_comp else None, "chapter_key": ch5_comp.key if ch5_comp else "", "is_primary": True}],
                        },
                    ],
                },
                {
                    "doc_key": "icmai:cma-intermediate:paper-6:2026-12:supplementary",
                    "level": lvl_inter,
                    "subject": s6_inter,
                    "scheme": scheme_inter,
                    "title": "ICMAI Supplementary - Paper 6 Financial Accounting (December 2026)",
                    "short_title": "Supplementary: Paper 6 (December 2026)",
                    "term_code": "2026-12",
                    "src_rel": "intermediate/2026-12/Supplementary_Paper 6 for December 2026 Term of Examination_20260828154818.pdf",
                    "storage_path": "cma/intermediate/2026-12/paper-6.pdf",
                    "issued_on": date(2026, 5, 22),
                    "cards": [
                        {
                            "law_key": "as_10",
                            "provision_label": "AS 10 / Component Depreciation",
                            "change_type": ChangeVersion.ChangeType.CLARIFICATION,
                            "title": "AS 10 Property, Plant and Equipment: Component Accounting and Useful Life Estimates",
                            "summary_old": "Depreciation computed on composite assets without explicit mandatory component breakdown for medium enterprises.",
                            "summary_new": "Clarification on component-level accounting for significant parts of an item of PPE and treatment of subsequent replacement costs.",
                            "effective_from_term_code": "2026-12",
                            "materiality": ChangeVersion.Materiality.NORMAL,
                            "source_page": 2,
                            "evidence_quote": "AS 10 component approach guidance clarified for commercial accounting examinations.",
                            "chapter_mappings": [{"subject_id": s6_inter.id, "subject_key": s6_inter.key, "chapter_id": ch6_acc.id if ch6_acc else None, "chapter_key": ch6_acc.key if ch6_acc else "", "is_primary": True}],
                        },
                    ],
                },
                {
                    "doc_key": "icmai:cma-intermediate:paper-7a:2026-12:supplementary",
                    "level": lvl_inter,
                    "subject": s7_inter,
                    "scheme": scheme_inter,
                    "title": "ICMAI Supplementary - Paper 7 Section A Direct Taxation (December 2026)",
                    "short_title": "Supplementary: Paper 7A Direct Tax (December 2026)",
                    "term_code": "2026-12",
                    "src_rel": "intermediate/2026-12/Supplementary_Paper 7A for December 2026 Term of Examination)_20260828154849.pdf",
                    "storage_path": "cma/intermediate/2026-12/paper-7a.pdf",
                    "issued_on": date(2026, 5, 24),
                    "cards": [
                        {
                            "law_key": "income_tax_act_1961",
                            "provision_label": "Section 194J & 194C / TDS Rates",
                            "change_type": ChangeVersion.ChangeType.MODIFICATION,
                            "title": "Rationalisation of TDS Rates under Section 194J and Contractor Payments under Section 194C",
                            "summary_old": "Different withholding rates applied to technical services versus royalty payments.",
                            "summary_new": "Rationalised 2% TDS rate for fees for technical services (other than professional services) under Section 194J to reduce classification disputes.",
                            "effective_from_term_code": "2026-12",
                            "materiality": ChangeVersion.Materiality.HIGH,
                            "source_page": 2,
                            "evidence_quote": "Rationalisation of TDS rates under Section 194J and related provisions applicable for December 2026 exam.",
                            "chapter_mappings": [{"subject_id": s7_inter.id, "subject_key": s7_inter.key, "chapter_id": ch7_dt.id if ch7_dt else None, "chapter_key": ch7_dt.key if ch7_dt else "", "is_primary": True}],
                        },
                    ],
                },
                {
                    "doc_key": "icmai:cma-intermediate:paper-7b:2026-12:supplementary",
                    "level": lvl_inter,
                    "subject": s7_inter,
                    "scheme": scheme_inter,
                    "title": "ICMAI Supplementary - Paper 7 Section B Indirect Taxation (December 2026)",
                    "short_title": "Supplementary: Paper 7B Indirect Tax (December 2026)",
                    "term_code": "2026-12",
                    "src_rel": "intermediate/2026-12/Supplementary_Paper 7B for December 2026 Term of Examination_20260828154918.pdf",
                    "storage_path": "cma/intermediate/2026-12/paper-7b.pdf",
                    "issued_on": date(2026, 5, 25),
                    "cards": [
                        {
                            "law_key": "cgst_act_2017",
                            "provision_label": "Rule 31D / Valuation on RSP",
                            "provision_keys": ["cgst:rule_31d:rsp_valuation"],
                            "change_type": ChangeVersion.ChangeType.ADDITION,
                            "title": "Introduction of Rule 31D in CGST Rules for Determination of Tax Component on Retail Sale Price",
                            "summary_old": "No specific mathematical formula existed under CGST Rules for extracting tax component from Retail Sale Price (RSP).",
                            "summary_new": "Notification 20/2025-CT introduces Rule 31D prescribing a formula for determining the tax component from the RSP for specified goods.",
                            "effective_from_term_code": "2026-12",
                            "materiality": ChangeVersion.Materiality.HIGH,
                            "source_page": 2,
                            "evidence_quote": "Notification No. 20/2025–Central Tax, dated 31 December 2025, introduces Rule 31D in the CGST Rules.",
                            "chapter_mappings": [{"subject_id": s7_inter.id, "subject_key": s7_inter.key, "chapter_id": ch7_gst.id if ch7_gst else None, "chapter_key": ch7_gst.key if ch7_gst else "", "is_primary": True}],
                        },
                    ],
                },

                # --- FINAL JUNE 2026 ---
                {
                    "doc_key": "icmai:cma-final:paper-13:2026-06:supplementary",
                    "level": lvl_final,
                    "subject": s13_final,
                    "scheme": scheme_final,
                    "title": "ICMAI Supplementary - Paper 13 Corporate and Economic Laws (June 2026)",
                    "short_title": "Supplementary: Paper 13 (June 2026)",
                    "term_code": "2026-06",
                    "src_rel": "final/2026-06/Supplementary_Paper13_J26.pdf",
                    "storage_path": "cma/final/2026-06/paper-13.pdf",
                    "issued_on": date(2025, 11, 28),
                    "cards": [
                        {
                            "law_key": "companies_act_2013",
                            "provision_label": "Section 143(12) / Form ADT-4",
                            "provision_keys": ["companies_act:143(12):adt4_digital"],
                            "change_type": ChangeVersion.ChangeType.MODIFICATION,
                            "title": "Mandatory Electronic Auditor Fraud Reporting in Form ADT-4 on MCA V3",
                            "summary_old": "Auditors submitted fraud reports physically or via postal letterhead to MCA.",
                            "summary_new": "Rule 13(2) substituted: all fraud reporting under Section 143(12) must be submitted electronically in Form ADT-4; physical/postal submissions discontinued.",
                            "effective_from_term_code": "2026-06",
                            "materiality": ChangeVersion.Materiality.HIGH,
                            "source_page": 3,
                            "evidence_quote": "Auditor fraud reporting must now be filed electronically in Form ADT-4. Earlier physical submission to MCA stands discontinued.",
                            "chapter_mappings": [{"subject_id": s13_final.id, "subject_key": s13_final.key, "chapter_id": ch13_comp.id if ch13_comp else None, "chapter_key": ch13_comp.key if ch13_comp else "", "is_primary": True}],
                        },
                        {
                            "law_key": "sebi_lodr_2015",
                            "provision_label": "Regulation 23 / RPT Norms",
                            "provision_keys": ["sebi_lodr:reg_23:rpt"],
                            "change_type": ChangeVersion.ChangeType.MODIFICATION,
                            "title": "SEBI LODR Regulation 23: Materiality Thresholds and Prior Approval for Related Party Transactions",
                            "summary_old": "Materiality threshold was ₹1,000 crore or 10% of annual consolidated turnover without granular subsidiary netting provisions.",
                            "summary_new": "Strengthened approval mechanisms for subsidiary transactions and enhanced omnibus approval disclosures to protect minority shareholders.",
                            "effective_from_term_code": "2026-06",
                            "materiality": ChangeVersion.Materiality.HIGH,
                            "source_page": 5,
                            "evidence_quote": "SEBI amended Regulation 23 of SEBI (LODR) Regulations, 2015 with the objective of strengthening corporate governance.",
                            "chapter_mappings": [{"subject_id": s13_final.id, "subject_key": s13_final.key, "chapter_id": ch13_sebi.id if ch13_sebi else None, "chapter_key": ch13_sebi.key if ch13_sebi else "", "is_primary": True}],
                        },
                    ],
                },
                {
                    "doc_key": "icmai:cma-final:paper-15:2026-06:supplementary",
                    "level": lvl_final,
                    "subject": s15_final,
                    "scheme": scheme_final,
                    "title": "ICMAI Supplementary - Paper 15 Direct Tax Laws and International Taxation (June 2026)",
                    "short_title": "Supplementary: Paper 15 (June 2026)",
                    "term_code": "2026-06",
                    "src_rel": "final/2026-06/Supplementary_Paper15_J26.pdf",
                    "storage_path": "cma/final/2026-06/paper-15.pdf",
                    "issued_on": date(2025, 11, 26),
                    "cards": [
                        {
                            "law_key": "income_tax_act_1961",
                            "provision_label": "Section 94B / Thin Capitalisation",
                            "change_type": ChangeVersion.ChangeType.CLARIFICATION,
                            "title": "Section 94B Interest Limitation: Exclusion of Specified Financing Entities and Safe Harbour Norms",
                            "summary_old": "Interest deduction disallowance applied strictly to all cross-border associated enterprise loans exceeding ₹1 crore.",
                            "summary_new": "Clarified safe harbour exclusions for regulated finance and insurance entities operating under IFSC authority guidelines.",
                            "effective_from_term_code": "2026-06",
                            "materiality": ChangeVersion.Materiality.HIGH,
                            "source_page": 4,
                            "evidence_quote": "Section 94B interest deduction limitation exceptions notified for international taxation papers.",
                            "chapter_mappings": [{"subject_id": s15_final.id, "subject_key": s15_final.key, "chapter_id": ch15_dt.id if ch15_dt else None, "chapter_key": ch15_dt.key if ch15_dt else "", "is_primary": True}],
                        },
                    ],
                },
                {
                    "doc_key": "icmai:cma-final:paper-18:2026-06:supplementary",
                    "level": lvl_final,
                    "subject": s18_final,
                    "scheme": scheme_final,
                    "title": "ICMAI Supplementary - Paper 18 Corporate Financial Reporting (June 2026)",
                    "short_title": "Supplementary: Paper 18 (June 2026)",
                    "term_code": "2026-06",
                    "src_rel": "final/2026-06/Supplementary_Paper18_J26.pdf",
                    "storage_path": "cma/final/2026-06/paper-18.pdf",
                    "issued_on": date(2025, 11, 20),
                    "cards": [
                        {
                            "law_key": "ind_as_12",
                            "provision_label": "Ind AS 12 / Paragraph 4A & 88A-88D",
                            "provision_keys": ["ind_as:12:pillar_two"],
                            "change_type": ChangeVersion.ChangeType.NEW_STANDARD,
                            "title": "Ind AS 12 Income Taxes: International Tax Reform - Pillar Two Model Rules Accounting & Disclosures",
                            "summary_old": "No exception existed under Ind AS 12 for deferred tax accounting arising from OECD Pillar Two global minimum tax legislation.",
                            "summary_new": "Mandatory temporary exception from deferred tax accounting for Pillar Two income taxes; requires qualitative and quantitative disclosure of exposure to Pillar Two legislation.",
                            "effective_from_term_code": "2026-06",
                            "materiality": ChangeVersion.Materiality.HIGH,
                            "source_page": 2,
                            "evidence_quote": "Paragraph 4A inserted: This Standard applies to income taxes arising from tax law enacted to implement Pillar Two model rules.",
                            "chapter_mappings": [{"subject_id": s18_final.id, "subject_key": s18_final.key, "chapter_id": ch18_std.id if ch18_std else None, "chapter_key": ch18_std.key if ch18_std else "", "is_primary": True}],
                        },
                        {
                            "law_key": "ind_as_32",
                            "provision_label": "Ind AS 32 / Appendix A",
                            "change_type": ChangeVersion.ChangeType.MODIFICATION,
                            "title": "Ind AS 32 Financial Instruments: Substitution of Heading on Treasury Shares in Appendix A",
                            "summary_old": "Heading in Appendix A before paragraph AG36 followed earlier alignment.",
                            "summary_new": "Heading substituted as 'Treasury Shares (paragraphs 33-34)' to clarify presentation and deduction from equity.",
                            "effective_from_term_code": "2026-06",
                            "materiality": ChangeVersion.Materiality.LOW,
                            "source_page": 4,
                            "evidence_quote": "Companies (Indian Accounting Standards) Second Amendment Rules, 2025 substitutes heading before paragraph AG36.",
                            "chapter_mappings": [{"subject_id": s18_final.id, "subject_key": s18_final.key, "chapter_id": ch18_std.id if ch18_std else None, "chapter_key": ch18_std.key if ch18_std else "", "is_primary": True}],
                        },
                    ],
                },
                {
                    "doc_key": "icmai:cma-final:paper-19:2026-06:supplementary",
                    "level": lvl_final,
                    "subject": s19_final,
                    "scheme": scheme_final,
                    "title": "ICMAI Supplementary - Paper 19 Indirect Tax Laws and Practice (June 2026)",
                    "short_title": "Supplementary: Paper 19 (June 2026)",
                    "term_code": "2026-06",
                    "src_rel": "final/2026-06/Supplementary_Paper19_J26-1.pdf",
                    "storage_path": "cma/final/2026-06/paper-19.pdf",
                    "issued_on": date(2025, 11, 23),
                    "cards": [
                        {
                            "law_key": "cgst_act_2017",
                            "provision_label": "Section 148 / Special Procedures",
                            "change_type": ChangeVersion.ChangeType.ADDITION,
                            "title": "Special Procedure for Manufacturers of Pan Masala and Tobacco Products under Section 148",
                            "summary_old": "General monthly return filing and packing machine tracking norms applied.",
                            "summary_new": "Mandatory registration of all packing machines in Form GST SRM-I and monthly statement SRM-II pursuant to Notification 04/2025-CT.",
                            "effective_from_term_code": "2026-06",
                            "materiality": ChangeVersion.Materiality.HIGH,
                            "source_page": 12,
                            "evidence_quote": "Notification No. 04/2025 – Central Tax prescribes special procedure for pan masala and tobacco manufacturers.",
                            "chapter_mappings": [{"subject_id": s19_final.id, "subject_key": s19_final.key, "chapter_id": ch19_gst.id if ch19_gst else None, "chapter_key": ch19_gst.key if ch19_gst else "", "is_primary": True}],
                        },
                    ],
                },

                # --- FINAL DEC 2026 ---
                {
                    "doc_key": "icmai:cma-final:paper-13:2026-12:supplementary",
                    "level": lvl_final,
                    "subject": s13_final,
                    "scheme": scheme_final,
                    "title": "ICMAI Supplementary - Paper 13 Corporate and Economic Laws (December 2026)",
                    "short_title": "Supplementary: Paper 13 (December 2026)",
                    "term_code": "2026-12",
                    "src_rel": "final/2026-12/Supplementary_Paper 13 for December 2026 Term of Examination_20260828154945.pdf",
                    "storage_path": "cma/final/2026-12/paper-13.pdf",
                    "issued_on": date(2026, 5, 27),
                    "cards": [
                        {
                            "law_key": "ibc_2016",
                            "provision_label": "Section 29A / CIRP Regulations",
                            "change_type": ChangeVersion.ChangeType.MODIFICATION,
                            "title": "Insolvency and Bankruptcy Board of India (CIRP) Amendment Regulations: Real Estate Project Segmentation",
                            "summary_old": "CIRP conducted across entire corporate debtor company without separate project-wise resolution mechanisms.",
                            "summary_new": "Adjudicating Authority may direct resolution professional to invite project-specific resolution plans for real estate debtors.",
                            "effective_from_term_code": "2026-12",
                            "materiality": ChangeVersion.Materiality.HIGH,
                            "source_page": 4,
                            "evidence_quote": "IBBI CIRP Amendment Regulations clarify project-wise resolution for real estate companies.",
                            "chapter_mappings": [{"subject_id": s13_final.id, "subject_key": s13_final.key, "chapter_id": ch13_ibc.id if ch13_ibc else None, "chapter_key": ch13_ibc.key if ch13_ibc else "", "is_primary": True}],
                        },
                    ],
                },
                {
                    "doc_key": "icmai:cma-final:paper-15:2026-12:supplementary",
                    "level": lvl_final,
                    "subject": s15_final,
                    "scheme": scheme_final,
                    "title": "ICMAI Supplementary - Paper 15 Direct Tax Laws and International Taxation (December 2026)",
                    "short_title": "Supplementary: Paper 15 (December 2026)",
                    "term_code": "2026-12",
                    "src_rel": "final/2026-12/Supplementary_Paper 15 for December 2026 Term of Examination_20260828155009.pdf",
                    "storage_path": "cma/final/2026-12/paper-15.pdf",
                    "issued_on": date(2026, 5, 26),
                    "cards": [
                        {
                            "law_key": "finance_act_2025",
                            "provision_label": "Section 165A / Equalisation Levy",
                            "change_type": ChangeVersion.ChangeType.DELETION,
                            "title": "Withdrawal of 2% Equalisation Levy on E-Commerce Supply or Services",
                            "summary_old": "2% Equalisation Levy applied to consideration received by non-resident e-commerce operators from Indian customers.",
                            "summary_new": "Section 165A equalisation levy stands withdrawn with effect from 1st August 2025 pursuant to bilateral digital economy agreements.",
                            "effective_from_term_code": "2026-12",
                            "materiality": ChangeVersion.Materiality.HIGH,
                            "source_page": 2,
                            "evidence_quote": "Withdrawal of 2% Equalisation Levy under Finance Act notified for December 2026 syllabus.",
                            "chapter_mappings": [{"subject_id": s15_final.id, "subject_key": s15_final.key, "chapter_id": ch15_dt.id if ch15_dt else None, "chapter_key": ch15_dt.key if ch15_dt else "", "is_primary": True}],
                        },
                    ],
                },
                {
                    "doc_key": "icmai:cma-final:paper-17:2026-12:supplementary",
                    "level": lvl_final,
                    "subject": s17_final,
                    "scheme": scheme_final,
                    "title": "ICMAI Supplementary - Paper 17 Cost and Management Audit (December 2026)",
                    "short_title": "Supplementary: Paper 17 (December 2026)",
                    "term_code": "2026-12",
                    "src_rel": "final/2026-12/Supplementary_Paper 17 for December 2026 Term of Examination_20260827093217.pdf",
                    "storage_path": "cma/final/2026-12/paper-17.pdf",
                    "issued_on": date(2026, 5, 28),
                    "cards": [
                        {
                            "law_key": "companies_act_2013",
                            "provision_label": "Section 148 / CRA Rules",
                            "provision_keys": ["companies_act:148:cost_records_audit"],
                            "change_type": ChangeVersion.ChangeType.MODIFICATION,
                            "title": "Companies (Cost Records and Audit) Amendment Rules: Reporting Norms in Form CRA-1 and CRA-3",
                            "summary_old": "Cost records maintenance and audit reporting followed earlier prescribed industry classifications.",
                            "summary_new": "Updated statutory thresholds and technical clarifications on cost accounting standards (CAS) compliance in Form CRA-1 and Form CRA-3.",
                            "effective_from_term_code": "2026-12",
                            "materiality": ChangeVersion.Materiality.HIGH,
                            "source_page": 2,
                            "evidence_quote": "Companies (Cost Records and Audit) Rules, 2014 regulatory clarifications for December 2026 examination sitting.",
                            "chapter_mappings": [{"subject_id": s17_final.id, "subject_key": s17_final.key, "chapter_id": ch17_audit.id if ch17_audit else None, "chapter_key": ch17_audit.key if ch17_audit else "", "is_primary": True}],
                        },
                    ],
                },
                {
                    "doc_key": "icmai:cma-final:paper-18:2026-12:supplementary",
                    "level": lvl_final,
                    "subject": s18_final,
                    "scheme": scheme_final,
                    "title": "ICMAI Supplementary - Paper 18 Corporate Financial Reporting (December 2026)",
                    "short_title": "Supplementary: Paper 18 (December 2026)",
                    "term_code": "2026-12",
                    "src_rel": "final/2026-12/Supplementary_Paper 18 for December 2026 Term of Examination_20260828155038.pdf",
                    "storage_path": "cma/final/2026-12/paper-18.pdf",
                    "issued_on": date(2026, 5, 25),
                    "cards": [
                        {
                            "law_key": "ind_as_107",
                            "provision_label": "Ind AS 107 / Paragraphs 44F-44H",
                            "change_type": ChangeVersion.ChangeType.MODIFICATION,
                            "title": "Ind AS 107 Disclosures: Supplier Finance Arrangements Transparency Requirements",
                            "summary_old": "Entities disclosed reverse factoring and trade payable financing without standardized quantitative breakdown.",
                            "summary_new": "Mandatory qualitative and quantitative disclosures regarding terms of supplier finance arrangements, carrying amounts, and liquidity impact.",
                            "effective_from_term_code": "2026-12",
                            "materiality": ChangeVersion.Materiality.NORMAL,
                            "source_page": 2,
                            "evidence_quote": "Ind AS 107 amended to incorporate enhanced disclosures for supplier finance arrangements.",
                            "chapter_mappings": [{"subject_id": s18_final.id, "subject_key": s18_final.key, "chapter_id": ch18_std.id if ch18_std else None, "chapter_key": ch18_std.key if ch18_std else "", "is_primary": True}],
                        },
                    ],
                },
                {
                    "doc_key": "icmai:cma-final:paper-19:2026-12:supplementary",
                    "level": lvl_final,
                    "subject": s19_final,
                    "scheme": scheme_final,
                    "title": "ICMAI Supplementary - Paper 19 Indirect Tax Laws and Practice (December 2026)",
                    "short_title": "Supplementary: Paper 19 (December 2026)",
                    "term_code": "2026-12",
                    "src_rel": "final/2026-12/Supplementary_Paper 19 for December 2026 Term of Examination_20260903124852.pdf",
                    "storage_path": "cma/final/2026-12/paper-19.pdf",
                    "issued_on": date(2026, 5, 29),
                    "cards": [
                        {
                            "law_key": "cgst_act_2017",
                            "provision_label": "Rule 48(4) & Form GSTR-1B",
                            "change_type": ChangeVersion.ChangeType.MODIFICATION,
                            "title": "E-Invoicing Applicability and Introduction of Form GSTR-1B Auto-Reconciliation",
                            "summary_old": "Mismatches between GSTR-1 and GSTR-3B were addressed through manual scrutiny notices in Form DRC-01B.",
                            "summary_new": "Introduction of Form GSTR-1B for real-time auto-population and explanation of liability differences before filing subsequent return.",
                            "effective_from_term_code": "2026-12",
                            "materiality": ChangeVersion.Materiality.HIGH,
                            "source_page": 5,
                            "evidence_quote": "CGST Rules amendments introducing Form GSTR-1B and updated e-invoicing verification.",
                            "chapter_mappings": [{"subject_id": s19_final.id, "subject_key": s19_final.key, "chapter_id": ch19_gst.id if ch19_gst else None, "chapter_key": ch19_gst.key if ch19_gst else "", "is_primary": True}],
                        },
                    ],
                },
            ]

            # Ingest all 17 booklets
            total_seeded = 0
            total_updated = 0

            for b in booklets:
                doc_key = b["doc_key"]
                storage_path = b["storage_path"]
                cdn_url = public_url(bucket, storage_path)
                sha, page_cnt = get_file_meta(b["src_rel"])
                term_code = b["term_code"]
                subj = b["subject"]
                scheme = b["scheme"]
                level = b["level"]

                # If amendment exists, ensure official_url is updated to Supabase CDN URL
                if Amendment.objects.filter(doc_key=doc_key).exists():
                    amd = Amendment.objects.get(doc_key=doc_key)
                    # Update revision official_url to CDN URL
                    for rev in amd.revisions.all():
                        update_fields = []
                        if rev.official_url != cdn_url:
                            rev.official_url = cdn_url
                            update_fields.append("official_url")
                        if sha and rev.doc_sha256 != sha:
                            rev.doc_sha256 = sha
                            update_fields.append("doc_sha256")
                        if page_cnt and rev.page_count != page_cnt:
                            rev.page_count = page_cnt
                            update_fields.append("page_count")
                        if update_fields:
                            rev.save(update_fields=update_fields)
                            total_updated += 1
                            self.stdout.write(f"  [Updated CDN URL] {doc_key} (rev {rev.revision_no}) -> {cdn_url}")
                    continue

                # Create draft
                amd, rev = create_amendment_draft(
                    course_id=course.id,
                    level_id=level.id,
                    title=b["title"],
                    short_title=b["short_title"],
                    doc_key=doc_key,
                    kind=Amendment.Kind.STATUTORY_UPDATE,
                    issuer_label="ICMAI Directorate of Studies",
                    landing_url="https://icmai.in/studentswebsite/Stud-Supp.php",
                    official_url=cdn_url,
                    issued_on=b["issued_on"],
                )

                # Set revision term scope
                if term_code == "2026-06":
                    terms = [
                        {"term_code": "2026-06", "applicability": RevisionTerm.Applicability.APPLIES, "cutoff_date": date(2025, 11, 30), "source_page": 1},
                        {"term_code": "2026-12", "applicability": RevisionTerm.Applicability.APPLIES, "source_page": 1},
                    ]
                else:
                    terms = [
                        {"term_code": "2026-06", "applicability": RevisionTerm.Applicability.EXCLUDED, "cutoff_note": "Issued for December 2026 examination cycle.", "source_page": 1},
                        {"term_code": "2026-12", "applicability": RevisionTerm.Applicability.APPLIES, "cutoff_date": date(2026, 5, 31), "source_page": 1},
                    ]

                set_revision_scope(
                    revision_id=rev.id,
                    subjects=[{"subject_id": subj.id, "subject_key": subj.key, "scheme_id": scheme.id, "level_id": level.id}],
                    terms=terms,
                )

                # Update sha and page_count
                if sha or page_cnt:
                    rev.doc_sha256 = sha
                    rev.page_count = page_cnt
                    rev.save(update_fields=["doc_sha256", "page_count"])

                # Stage cards
                for card_spec in b.get("cards", []):
                    stage_change_card(
                        revision_id=rev.id,
                        law_key=card_spec.get("law_key", ""),
                        provision_label=card_spec.get("provision_label", ""),
                        provision_keys=card_spec.get("provision_keys", []),
                        change_type=card_spec.get("change_type", ChangeVersion.ChangeType.MODIFICATION),
                        title=card_spec["title"],
                        summary_old=card_spec.get("summary_old", ""),
                        summary_new=card_spec.get("summary_new", ""),
                        effective_from_term_code=card_spec.get("effective_from_term_code", term_code),
                        materiality=card_spec.get("materiality", ChangeVersion.Materiality.HIGH),
                        source_page=card_spec.get("source_page", 1),
                        evidence_quote=card_spec.get("evidence_quote", ""),
                        chapter_mappings=card_spec.get("chapter_mappings", []),
                    )

                release_revision(revision_id=rev.id)
                total_seeded += 1
                self.stdout.write(self.style.SUCCESS(f"  + Seeded {b['short_title']} -> {cdn_url}"))

            self.stdout.write(self.style.SUCCESS(f"\nCompleted! Newly seeded: {total_seeded}, Updated to CDN: {total_updated}"))

    def _upload_files_to_storage(self, materials_dir: Path, bucket: str) -> None:
        """Uploads all local source PDFs to Supabase Storage."""
        self.stdout.write("Checking and uploading PDFs to Supabase Storage...")
        try:
            store = get_storage()
            store.ensure_bucket(bucket, public=True)
        except Exception as exc:
            self.stderr.write(f"Cannot initialize Supabase Storage: {exc}")
            return

        file_map = [
            ("intermediate/2026-06/Supplementary_Paper5_J26.pdf", "cma/intermediate/2026-06/paper-5.pdf"),
            ("intermediate/2026-06/Supplementary_Paper7A_J26.pdf", "cma/intermediate/2026-06/paper-7a.pdf"),
            ("intermediate/2026-06/Supplementary_Paper7B_J26.pdf", "cma/intermediate/2026-06/paper-7b.pdf"),
            ("intermediate/2026-06/Supplementary_Paper10_J26.pdf", "cma/intermediate/2026-06/paper-10.pdf"),
            ("intermediate/2026-12/Supplementary_Paper 5 for December 2026 Term of Examination (1)_20260828145435.pdf", "cma/intermediate/2026-12/paper-5.pdf"),
            ("intermediate/2026-12/Supplementary_Paper 6 for December 2026 Term of Examination_20260828154818.pdf", "cma/intermediate/2026-12/paper-6.pdf"),
            ("intermediate/2026-12/Supplementary_Paper 7A for December 2026 Term of Examination)_20260828154849.pdf", "cma/intermediate/2026-12/paper-7a.pdf"),
            ("intermediate/2026-12/Supplementary_Paper 7B for December 2026 Term of Examination_20260828154918.pdf", "cma/intermediate/2026-12/paper-7b.pdf"),
            ("final/2026-06/Supplementary_Paper13_J26.pdf", "cma/final/2026-06/paper-13.pdf"),
            ("final/2026-06/Supplementary_Paper15_J26.pdf", "cma/final/2026-06/paper-15.pdf"),
            ("final/2026-06/Supplementary_Paper18_J26.pdf", "cma/final/2026-06/paper-18.pdf"),
            ("final/2026-06/Supplementary_Paper19_J26-1.pdf", "cma/final/2026-06/paper-19.pdf"),
            ("final/2026-12/Supplementary_Paper 13 for December 2026 Term of Examination_20260828154945.pdf", "cma/final/2026-12/paper-13.pdf"),
            ("final/2026-12/Supplementary_Paper 15 for December 2026 Term of Examination_20260828155009.pdf", "cma/final/2026-12/paper-15.pdf"),
            ("final/2026-12/Supplementary_Paper 17 for December 2026 Term of Examination_20260827093217.pdf", "cma/final/2026-12/paper-17.pdf"),
            ("final/2026-12/Supplementary_Paper 18 for December 2026 Term of Examination_20260828155038.pdf", "cma/final/2026-12/paper-18.pdf"),
            ("final/2026-12/Supplementary_Paper 19 for December 2026 Term of Examination_20260903124852.pdf", "cma/final/2026-12/paper-19.pdf"),
        ]

        for src_rel, dest_path in file_map:
            file_path = materials_dir / src_rel
            if not file_path.is_file():
                self.stdout.write(f"  [Skip] {src_rel} not found")
                continue
            try:
                data = file_path.read_bytes()
                store.upload(bucket, dest_path, data, content_type="application/pdf", cache_control="public, max-age=31536000", upsert=True)
                self.stdout.write(f"  [Uploaded] {dest_path} ({len(data)} bytes)")
            except Exception as exc:
                self.stderr.write(f"  [Upload Error] {dest_path}: {exc}")
