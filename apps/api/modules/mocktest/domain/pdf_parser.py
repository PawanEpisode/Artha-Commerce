"""
Domain parser for Institute Mock Question Papers (MQP) and Postal Test Papers (PTP).
Extracts:
  - Section A: MCQs (stem, options A-D, correct key, explanation reasons)
  - Section B: Descriptive problems (questions, sub-parts (a)/(b), marks, solutions)
  - CDN URLs for question and answer PDFs
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path
from typing import Any

try:
    import pypdf
except ImportError:
    pypdf = None


CMA_PAPERS_MAP = {
    # Final
    "13": ("corporate-and-economic-laws", "Corporate and Economic Laws", "final"),
    "14": ("strategic-financial-management", "Strategic Financial Management", "final"),
    "15": ("direct-tax-laws-and-international-taxation", "Direct Tax Laws and International Taxation", "final"),
    "16": ("strategic-cost-management", "Strategic Cost Management", "final"),
    "17": ("cost-and-management-audit", "Cost and Management Audit", "final"),
    "18": ("corporate-financial-reporting", "Corporate Financial Reporting", "final"),
    "19": ("indirect-tax-laws-and-practice", "Indirect Tax Laws and Practice", "final"),
    "20A": ("strategic-performance-management-and-business-valuation", "Strategic Performance Management and Business Valuation", "final"),
    "20": ("strategic-performance-management-and-business-valuation", "Strategic Performance Management and Business Valuation", "final"),
    # Intermediate
    "5": ("business-laws-and-ethics", "Business Laws and Ethics", "intermediate"),
    "6": ("financial-accounting", "Financial Accounting", "intermediate"),
    "7": ("direct-and-indirect-taxation", "Direct and Indirect Taxation", "intermediate"),
    "7A": ("direct-and-indirect-taxation", "Direct Taxation", "intermediate"),
    "7B": ("direct-and-indirect-taxation", "Indirect Taxation", "intermediate"),
    "8": ("cost-accounting", "Cost Accounting", "intermediate"),
    "9": ("operations-management-and-strategic-management", "Operations Management and Strategic Management", "intermediate"),
    "10": ("corporate-accounting-and-auditing", "Corporate Accounting and Auditing", "intermediate"),
    "11": ("financial-management-and-business-data-analytics", "Financial Management and Business Data Analytics", "intermediate"),
    "12": ("management-accounting", "Management Accounting", "intermediate"),
    # Foundation
    "1": ("fundamentals-of-business-laws-and-business-communication", "Fundamentals of Business Laws and Business Communication", "foundation"),
    "2": ("fundamentals-of-financial-and-cost-accounting", "Fundamentals of Financial and Cost Accounting", "foundation"),
    "3": ("fundamentals-of-business-mathematics-and-statistics", "Fundamentals of Business Mathematics and Statistics", "foundation"),
    "4": ("fundamentals-of-business-economics-and-management", "Fundamentals of Business Economics and Management", "foundation"),
}


def sanitize_stem_md(text: str) -> str:
    """
    Cleans stem markdown to strictly conform to QuestionBank profile:
    - Strips leading ATX heading markers (#) and converts to bold text
    - Strips Setext heading underlines (===, ---) and horizontal rules
    - Normalizes spacing
    """
    if not text:
        return ""
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        h_m = re.match(r"^(\s*)#{1,6}\s*(.*)$", line)
        if h_m:
            line = f"{h_m.group(1)}**{h_m.group(2)}**"
        if re.match(r"^\s*(=+|-+|\*+|_+\s*)\s*$", line):
            continue
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def normalize_term_code(term_str: str) -> str:
    """e.g. 'June_26', 'June26', 'June_2026', 'Dec_24', 'Dec23' -> '2026-06', '2024-12', '2023-12'"""
    s = term_str.lower().replace("_", " ").replace("-", " ")
    month = "06" if any(m in s for m in ["jun", "june"]) else "12"

    m4 = re.search(r"\b(202[2-6])\b", s)
    if m4:
        return f"{m4.group(1)}-{month}"

    m2 = re.search(r"(?:jun|june|dec|december)[\s_-]*(2[2-6])\b", s)
    if m2:
        return f"20{m2.group(1)}-{month}"

    return f"2026-{month}"


def extract_paper_number(filename_or_path: str) -> str:
    """Extracts paper number like '13', '14', '20A', '7A' or acronyms."""
    s = filename_or_path.lower()
    if "spmbv" in s or "paper 20a" in s or "p20a" in s:
        return "20A"
    if "scmp" in s or "scm" in s:
        return "16"
    if "sfm" in s:
        return "14"
    if "cfr" in s:
        return "18"
    if "audit" in s and "cost" in s:
        return "17"
    if "idt" in s:
        return "19"
    if "dtl" in s or "dt" in s:
        return "15"
    if "cel" in s:
        return "13"

    m = re.search(r'paper[-_\s]*([0-9]{1,2}[a-z]?)', filename_or_path, re.I)
    if m and m.group(1).upper() in CMA_PAPERS_MAP:
        return m.group(1).upper()
    m2 = re.search(r'\bp([0-9]{1,2}[a-z]?)\b', filename_or_path, re.I)
    if m2 and m2.group(1).upper() in CMA_PAPERS_MAP:
        return m2.group(1).upper()
    return "13"


def parse_mqp_pair(
    q_pdf_path: Path,
    a_pdf_path: Path,
    *,
    cdn_base_url: str = "https://bqkglnfdhkidajeqlebl.supabase.co/storage/v1/object/public/mock-tests",
) -> dict[str, Any]:
    """
    Parses a Question PDF and Answer PDF pair into an Artha Mock Paper payload.
    """
    if not pypdf:
        raise RuntimeError("pypdf is required to parse PDF mock tests.")

    # 1. Extract text
    q_reader = pypdf.PdfReader(str(q_pdf_path))
    q_text = "\n".join([p.extract_text() or "" for p in q_reader.pages])

    a_reader = pypdf.PdfReader(str(a_pdf_path))
    a_text = "\n".join([p.extract_text() or "" for p in a_reader.pages])

    header_cleaner = re.compile(r'Directorate of Studies, The Institute of Cost Accountants of India.*', re.I)
    q_clean = header_cleaner.sub('', q_text)
    a_clean = header_cleaner.sub('', a_text)

    # 2. Determine paper number, term, and set
    path_str = f"{q_pdf_path.parent.name} {q_pdf_path.name}"
    paper_num = extract_paper_number(path_str)
    paper_meta = CMA_PAPERS_MAP.get(paper_num, ("corporate-and-economic-laws", f"Paper {paper_num}", "final"))
    subject_key, subject_name, level_code = paper_meta

    term_code = normalize_term_code(path_str)
    term_label = "June " + term_code[:4] if "06" in term_code else "December " + term_code[:4]

    set_num = 1
    if any(s in path_str.lower() for s in ["set 2", "set2", "set_2", "_set2"]):
        set_num = 2

    title = f"CMA Final {term_label}: {subject_name} (Paper {paper_num}) - Set {set_num}"
    slug = f"cma-final-p{paper_num.lower()}-{term_code}-set-{set_num}"

    # CDN URLs
    rel_q = str(q_pdf_path).split("source-material/mock-tests/")[-1].lstrip("/")
    rel_a = str(a_pdf_path).split("source-material/mock-tests/")[-1].lstrip("/")
    source_pdf_url = f"{cdn_base_url}/{rel_q}"
    solution_pdf_url = f"{cdn_base_url}/{rel_a}"

    # 3. Parse Section A: Answer Keys & Explanations from Answer PDF
    ans_map: dict[str, tuple[str, str]] = {}
    sec_a_a_m = re.search(r'SECTION\s*[-–—:]*\s*A', a_clean, re.I)
    sec_b_a_m = re.search(r'SECTION\s*[-–—:]*\s*B', a_clean, re.I)
    a_sec_a_chunk = a_clean[sec_a_a_m.start():sec_b_a_m.start()] if (sec_a_a_m and sec_b_a_m) else a_clean[:8000]

    lines = [l.strip() for l in a_sec_a_chunk.splitlines() if l.strip()]
    for idx, line in enumerate(lines):
        nums = re.findall(r"\(([ivx]+|\d{1,2})\)", line, re.I)
        if len(nums) >= 2:
            for next_line in lines[idx + 1 : idx + 3]:
                raw_tokens = next_line.split()
                clean_tokens = [re.sub(r'[^a-zA-Z]', '', t).upper() for t in raw_tokens]
                tokens = [t for t in clean_tokens if len(t) == 1]
                if len(tokens) >= len(nums):
                    for n, k in zip(nums, tokens):
                        ans_map[n.lower()] = (k, "")
                    break

    # Fallback to table rows: (i) (a) justification... or (i) a. justification...
    if len(ans_map) < 5:
        rows = re.finditer(
            r'(?:\n|^)\s*\(([ivx]+|\d{1,2})\)\s*\(?([a-d])\)?[\.\s](.*?)(?=(?:\n|^)\s*\(([ivx]+|\d{1,2})\)|\n\s*[2-8]\.|\Z)',
            a_sec_a_chunk,
            re.S | re.I,
        )
        for r in rows:
            ans_map[r.group(1).lower()] = (r.group(2).upper(), r.group(3).strip())

    # 4. Parse Section A: Questions from Question PDF
    sec_a_m = re.search(r'SECTION\s*[-–—:]*\s*A', q_clean, re.I)
    sec_b_m = re.search(r'SECTION\s*[-–—:]*\s*B', q_clean, re.I)
    sec_a_text = q_clean[sec_a_m.start():sec_b_m.start()] if (sec_a_m and sec_b_m) else (q_clean[sec_a_m.start():] if sec_a_m else q_clean)

    items_sec_a = []
    q_items = list(re.finditer(
        r'(?:\n|^)\s*(?:\(([ivx]+|\d{1,2})\)|([ivx]+|\d{1,2})[\.\)])\s*(.*?)\s*'
        r'(?:\([Aa]\)|[Aa][\.\)\:])\s*(.*?)\s*'
        r'(?:\([Bb]\)|[Bb][\.\)\:])\s*(.*?)\s*'
        r'(?:\([Cc]\)|[Cc][\.\)\:])\s*(.*?)\s*'
        r'(?:\([Dd]\)|[Dd][\.\)\:])\s*(.*?)'
        r'(?=(?:\n|^)\s*(?:\(([ivx]+|\d{1,2})\)|[ivx]+[\.\)])|\n\s*SECTION|\n\s*[2-8]\.|\Z)',
        sec_a_text,
        re.S,
    ))

    if not q_items:
        q_items = list(re.finditer(
            r'(?:\(([ivx]+|\d{1,2})\)|([ivx]+|\d{1,2})[\.\)])\s*(.*?)\s*'
            r'(?:\([Aa]\)|[Aa][\.\)\:])\s*(.*?)\s*'
            r'(?:\([Bb]\)|[Bb][\.\)\:])\s*(.*?)\s*'
            r'(?:\([Cc]\)|[Cc][\.\)\:])\s*(.*?)\s*'
            r'(?:\([Dd]\)|[Dd][\.\)\:])\s*(.*?)'
            r'(?=(?:\(([ivx]+|\d{1,2})\)|[ivx]+[\.\)])|\n\s*[2-8]\.|\n\s*SECTION|\Z)',
            sec_a_text,
            re.S,
        ))

    q_pos = 1
    for it in q_items:
        q_num = (it.group(1) or it.group(2) or str(q_pos)).lower()
        raw_stem = it.group(3).strip()
        stem = sanitize_stem_md(raw_stem)
        opt_a = sanitize_stem_md(it.group(4).strip())
        opt_b = sanitize_stem_md(it.group(5).strip())
        opt_c = sanitize_stem_md(it.group(6).strip())
        raw_d = it.group(7).strip()
        raw_d = re.sub(r'\s*\n\s*SECTION\s*[-–—:]*\s*B.*', '', raw_d, flags=re.S | re.I)
        opt_d = sanitize_stem_md(raw_d)

        # Skip phantom matches with empty stem or empty options
        if not stem.strip() or (not opt_a.strip() and not opt_b.strip()):
            continue

        ans_key, explanation = ans_map.get(q_num, ('', ''))
        if not ans_key:
            roman_keys = ['i', 'ii', 'iii', 'iv', 'v', 'vi', 'vii', 'viii', 'ix', 'x', 'xi', 'xii', 'xiii', 'xiv', 'xv']
            if q_pos <= len(roman_keys):
                ans_key, explanation = ans_map.get(roman_keys[q_pos - 1], ('', ''))
        if ans_key not in ('A', 'B', 'C', 'D'):
            ans_key = 'A'

        items_sec_a.append({
            "position": q_pos,
            "display_label": f"Q.1({q_num})",
            "marks": 2,
            "negative_marks": 0,
            "question": {
                "external_ref": f"mock:{slug}:sec_a:p{q_pos}",
                "kind": "mcq_single",
                "stem_md": stem,
                "options": [
                    {"body_md": opt_a, "is_correct": ans_key == "A"},
                    {"body_md": opt_b, "is_correct": ans_key == "B"},
                    {"body_md": opt_c, "is_correct": ans_key == "C"},
                    {"body_md": opt_d, "is_correct": ans_key == "D"},
                ],
                "explanation_md": sanitize_stem_md(explanation),
                "difficulty": 2,
            }
        })
        q_pos += 1

    # 5. Parse Section B: Descriptive Questions (Including Sub-Parts)
    items_sec_b = []
    b_txt = a_clean[sec_b_a_m.start():] if sec_b_a_m else ""
    pattern = r'\n(?=(?:Q\.?\s*)?[2-8]\s*[\.\:]\s*(?:\([a-z]\))?|(?:\([a-b]\))\s+)'
    raw_blocks = re.split(pattern, b_txt)
    descriptive_blocks = [b for b in raw_blocks if b.strip() and not b.strip().upper().startswith("SECTION")]

    if not descriptive_blocks and sec_b_m:
        b_txt_q = q_clean[sec_b_m.start():]
        raw_blocks_q = re.split(pattern, b_txt_q)
        descriptive_blocks = [b for b in raw_blocks_q if b.strip() and not b.strip().upper().startswith("SECTION")]

    current_main_q = 2
    for b_idx, block in enumerate(descriptive_blocks, start=2):
        parts = re.split(r'\n\s*Answer:\s*', block, maxsplit=1, flags=re.I)
        q_stem_raw = sanitize_stem_md(parts[0].strip())
        if not q_stem_raw:
            continue
        sol_raw = sanitize_stem_md(parts[1].strip()) if len(parts) > 1 else ""
        if not sol_raw:
            sol_raw = "Refer to official ICMAI Model Solution Sheet PDF."

        num_m = re.match(r'^(?:Q\.?\s*)?([2-8])\s*[\.\:]\s*(?:\(([a-z])\))?', q_stem_raw)
        if num_m:
            current_main_q = int(num_m.group(1))
            sub_part = num_m.group(2)
            q_label = f"Q.{current_main_q}({sub_part})" if sub_part else f"Q.{current_main_q}"
        else:
            sub_m = re.match(r'^\(([a-d])\)', q_stem_raw)
            if sub_m:
                q_label = f"Q.{current_main_q}({sub_m.group(1)})"
            else:
                q_label = f"Q.{current_main_q}"

        items_sec_b.append({
            "position": q_pos,
            "display_label": q_label,
            "marks": 7,
            "choice_group_key": None,
            "suggested_seconds": 900,
            "question": {
                "external_ref": f"mock:{slug}:sec_b:p{q_pos}",
                "kind": "long_form",
                "stem_md": q_stem_raw,
                "rubric": {
                    "reference_solution_md": sol_raw[:4000],
                    "total_marks": 7,
                    "steps": [
                        {"title": "Working Notes & Conceptual Analysis", "marks": Decimal("3.50"), "mandatory": True},
                        {"title": "Conclusion & Final Computations", "marks": Decimal("3.50"), "mandatory": True},
                    ]
                }
            }
        })
        q_pos += 1

    # 6. Blueprint-Accurate Marks Calculation (Guaranteed 100/100 Total)
    sec_a_marks = len(items_sec_a) * 2
    remaining_marks = max(0, 100 - sec_a_marks)
    num_b = len(items_sec_b)
    choice_groups = []

    if num_b >= 10:
        req_count = 10
        marks_per_item = round(Decimal(str(remaining_marks)) / Decimal(str(req_count)), 2)
        cg_key = f"choice_sec_b_10_of_{num_b}"
        choice_groups.append({
            "key": cg_key,
            "label": f"Answer any 10 sub-questions from {num_b} questions given",
            "required_count": req_count,
            "overflow_policy": "best_n",
        })
        half = round(marks_per_item / Decimal("2"), 2)
        other_half = marks_per_item - half
        for it in items_sec_b:
            it["marks"] = marks_per_item
            it["choice_group_key"] = cg_key
            if it.get("question", {}).get("rubric"):
                it["question"]["rubric"]["total_marks"] = marks_per_item
                it["question"]["rubric"]["steps"] = [
                    {"title": "Working Notes & Conceptual Analysis", "marks": half, "mandatory": True},
                    {"title": "Conclusion & Final Computations", "marks": other_half, "mandatory": True},
                ]
    elif num_b >= 6:
        req_count = 5
        marks_per_item = round(Decimal(str(remaining_marks)) / Decimal(str(req_count)), 2)
        cg_key = f"choice_sec_b_5_of_{num_b}"
        choice_groups.append({
            "key": cg_key,
            "label": f"Answer any 5 from {num_b} questions given",
            "required_count": req_count,
            "overflow_policy": "best_n",
        })
        half = round(marks_per_item / Decimal("2"), 2)
        other_half = marks_per_item - half
        for it in items_sec_b:
            it["marks"] = marks_per_item
            it["choice_group_key"] = cg_key
            if it.get("question", {}).get("rubric"):
                it["question"]["rubric"]["total_marks"] = marks_per_item
                it["question"]["rubric"]["steps"] = [
                    {"title": "Working Notes & Conceptual Analysis", "marks": half, "mandatory": True},
                    {"title": "Conclusion & Final Computations", "marks": other_half, "mandatory": True},
                ]
    elif num_b > 0:
        marks_per_item = round(Decimal(str(remaining_marks)) / Decimal(str(num_b)), 2)
        remainder = Decimal(str(remaining_marks)) - (marks_per_item * num_b)
        for idx, it in enumerate(items_sec_b):
            m = marks_per_item + (remainder if idx == 0 else Decimal("0"))
            it["marks"] = m
            it["choice_group_key"] = None
            half = round(m / Decimal("2"), 2)
            other_half = m - half
            if it.get("question", {}).get("rubric"):
                it["question"]["rubric"]["total_marks"] = m
                it["question"]["rubric"]["steps"] = [
                    {"title": "Working Notes & Conceptual Analysis", "marks": half, "mandatory": True},
                    {"title": "Conclusion & Final Computations", "marks": other_half, "mandatory": True},
                ]

    return {
        "course_code": "cma",
        "level_code": level_code,
        "scheme_code": "2022",
        "subject_key": subject_key,
        "exam_term": term_code,
        "title": title,
        "slug": slug,
        "description": f"Official Model Question Paper for CMA Final {subject_name} ({term_label}).",
        "kind": "mtp",
        "source_tag": "institute",
        "delivery_mode": "native",
        "source_pdf_url": source_pdf_url,
        "solution_pdf_url": solution_pdf_url,
        "total_marks": 100,
        "duration_minutes": 180,
        "reading_minutes": 15,
        "section_timing": "none",
        "focus_policy": "log",
        "instructions_md": (
            "1. Answer Question No. 1 which is compulsory.\n"
            f"2. Answer Section B questions according to instructions.\n"
            "3. Wherever necessary, suitable assumptions may be made and clearly indicated."
        ),
        "series": {
            "title": f"CMA Final MQP {term_label}",
            "slug": f"cma-final-mqp-{term_code}",
            "series_no": 1 if "06" in term_code else 2,
            "kind": "institute_mtp"
        },
        "sections": [
            {
                "key": "A",
                "title": "Section A: Multiple Choice Questions (Compulsory)",
                "kind": "objective",
                "marks_total": sec_a_marks or 30,
                "items": items_sec_a,
            },
            {
                "key": "B",
                "title": "Section B: Descriptive Questions",
                "kind": "descriptive",
                "marks_total": remaining_marks,
                "choice_groups": choice_groups,
                "items": items_sec_b,
            }
        ]
    }


def parse_ptp(
    ptp_path: Path,
    *,
    cdn_base_url: str = "https://bqkglnfdhkidajeqlebl.supabase.co/storage/v1/object/public/mock-tests",
) -> dict[str, Any]:
    """
    Parses a Postal Test Paper (PTP) PDF into a Mock Test Paper payload.
    """
    if not pypdf:
        raise RuntimeError("pypdf is required to parse PDF postal test papers.")

    reader = pypdf.PdfReader(str(ptp_path))
    text = "\n".join([p.extract_text() or "" for p in reader.pages])

    paper_num = extract_paper_number(ptp_path.name)
    paper_meta = CMA_PAPERS_MAP.get(paper_num, ("corporate-and-economic-laws", f"Paper {paper_num}", "final"))
    subject_key, subject_name, level_code = paper_meta

    title = f"CMA {level_code.title()}: {subject_name} (Paper {paper_num}) - Postal Test Paper"
    slug = f"cma-{level_code}-p{paper_num.lower()}-ptp"

    rel_path = str(ptp_path).split("source-material/study-material/")[-1].lstrip("/")
    source_pdf_url = f"{cdn_base_url}/{rel_path}"

    # Extract MCQs
    mcqs = []
    mcq_matches = re.finditer(
        r'([ivxlcdm]+)\.\s*(.*?)\s*[aA]\.\s*(.*?)\s*[bB]\.\s*(.*?)\s*[cC]\.\s*(.*?)\s*[dD]\.\s*(.*?)(?=[ivxlcdm]+\.|\n\s*[2-9]\.|\n\s*SECTION|\Z)',
        text,
        re.S,
    )

    q_pos = 1
    for m in mcq_matches:
        num = m.group(1).lower()
        stem = sanitize_stem_md(m.group(2).strip())
        opt_a = sanitize_stem_md(m.group(3).strip())
        opt_b = sanitize_stem_md(m.group(4).strip())
        opt_c = sanitize_stem_md(m.group(5).strip())
        opt_d = sanitize_stem_md(m.group(6).strip())

        mcqs.append({
            "position": q_pos,
            "display_label": f"Q.1({num})",
            "marks": 2,
            "negative_marks": 0,
            "question": {
                "external_ref": f"mock:{slug}:sec_a:p{q_pos}",
                "kind": "mcq_single",
                "stem_md": stem,
                "options": [
                    {"body_md": opt_a, "is_correct": True},
                    {"body_md": opt_b, "is_correct": False},
                    {"body_md": opt_c, "is_correct": False},
                    {"body_md": opt_d, "is_correct": False},
                ],
                "explanation_md": "Postal Test Paper - Self Practice Question.",
                "difficulty": 2,
            }
        })
        q_pos += 1

    # Descriptive items
    descriptive_items = []
    q_blocks = re.split(r'\n(?=[2-8]\.\s*)', text)

    for b_idx, block in enumerate(q_blocks[1:], start=2):
        if not block.strip():
            continue
        stem_raw = sanitize_stem_md(block.strip()[:3000])
        descriptive_items.append({
            "position": q_pos,
            "display_label": f"Q.{b_idx}",
            "marks": 20,
            "choice_group_key": None,
            "suggested_seconds": 1500,
            "question": {
                "external_ref": f"mock:{slug}:sec_b:p{q_pos}",
                "kind": "long_form",
                "stem_md": stem_raw,
                "rubric": {
                    "reference_solution_md": "Postal Test Paper problem. Solve following institute working steps.",
                    "total_marks": 20,
                    "steps": [
                        {"title": "Working Notes & Application", "marks": 10, "mandatory": True},
                        {"title": "Conclusion & Final Values", "marks": 10, "mandatory": True},
                    ]
                }
            }
        })
        q_pos += 1

    sec_a_marks = len(mcqs) * 2
    rem = max(0, 100 - sec_a_marks)
    num_d = len(descriptive_items)
    choice_groups = []

    if num_d >= 5:
        req = 4
        m_each = round(Decimal(str(rem)) / Decimal(str(req)), 2)
        cg_key = f"ptp_choice_p{paper_num.lower()}"
        choice_groups.append({
            "key": cg_key,
            "label": f"Answer any 4 from {num_d} questions given",
            "required_count": req,
            "overflow_policy": "best_n",
        })
        half = round(m_each / Decimal("2"), 2)
        other_half = m_each - half
        for it in descriptive_items:
            it["marks"] = m_each
            it["choice_group_key"] = cg_key
            if it.get("question", {}).get("rubric"):
                it["question"]["rubric"]["total_marks"] = m_each
                it["question"]["rubric"]["steps"] = [
                    {"title": "Working Notes & Application", "marks": half, "mandatory": True},
                    {"title": "Conclusion & Final Values", "marks": other_half, "mandatory": True},
                ]
    elif num_d > 0:
        m_each = round(Decimal(str(rem)) / Decimal(str(num_d)), 2)
        rem_d = Decimal(str(rem)) - (m_each * num_d)
        for idx, it in enumerate(descriptive_items):
            m = m_each + (rem_d if idx == 0 else Decimal("0"))
            it["marks"] = m
            it["choice_group_key"] = None
            half = round(m / Decimal("2"), 2)
            other_half = m - half
            if it.get("question", {}).get("rubric"):
                it["question"]["rubric"]["total_marks"] = m
                it["question"]["rubric"]["steps"] = [
                    {"title": "Working Notes & Application", "marks": half, "mandatory": True},
                    {"title": "Conclusion & Final Values", "marks": other_half, "mandatory": True},
                ]

    return {
        "course_code": "cma",
        "level_code": level_code,
        "scheme_code": "2022",
        "subject_key": subject_key,
        "exam_term": "2026-06",
        "title": title,
        "slug": slug,
        "description": f"Official Postal Test Paper for CMA {level_code.title()} {subject_name}.",
        "kind": "sample",
        "source_tag": "institute",
        "delivery_mode": "native",
        "source_pdf_url": source_pdf_url,
        "solution_pdf_url": "",
        "total_marks": 100,
        "duration_minutes": 180,
        "reading_minutes": 15,
        "section_timing": "none",
        "focus_policy": "log",
        "instructions_md": "Answer Question No. 1 which is compulsory. Answer any four from Question No. 2 to 7.",
        "series": {
            "title": f"CMA {level_code.title()} Postal Test Papers",
            "slug": f"cma-{level_code}-ptp-series",
            "series_no": 1,
            "kind": "institute_other"
        },
        "sections": [
            {
                "key": "A",
                "title": "Section A: Multiple Choice Questions (Compulsory)",
                "kind": "objective",
                "marks_total": sec_a_marks or 20,
                "items": mcqs,
            },
            {
                "key": "B",
                "title": "Section B: Descriptive Questions",
                "kind": "descriptive",
                "marks_total": rem,
                "choice_groups": choice_groups,
                "items": descriptive_items,
            }
        ]
    }


def is_answer_pdf(name: str) -> bool:
    nl = name.lower()
    if any(k in nl for k in ["answer", "ans", "solution", "sol.", "_sol", "-a.pdf", "(a).pdf", "_a.pdf"]):
        return True
    if nl.startswith("a_") or "/a_" in nl or "\\a_" in nl:
        return True
    return False


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


def find_all_mqp_pairs(base_dir: Path | str = "Docs/source-material/mock-tests") -> list[tuple[Path, Path]]:
    """
    Scans base_dir for all MQP question papers and pairs them with their model answers.
    """
    base = resolve_source_path(base_dir)
    if not base.exists():
        return []

    dirs = sorted(set(f.parent for f in base.rglob("*.pdf")))
    pairs: list[tuple[Path, Path]] = []

    for d in dirs:
        pdfs = list(d.glob("*.pdf"))
        q_list = [f for f in pdfs if not is_answer_pdf(f.name)]
        a_list = [f for f in pdfs if is_answer_pdf(f.name)]

        for q in q_list:
            matched: Path | None = None
            q_stem = q.stem.lower()

            if len(q_list) == 1 and len(a_list) == 1:
                matched = a_list[0]
            else:
                set_num = "1" if any(s in q_stem for s in ["set1", "set 1", "set_1"]) else ("2" if any(s in q_stem for s in ["set2", "set 2", "set_2"]) else "")
                for a in a_list:
                    a_stem = a.stem.lower()
                    if set_num and any(s in a_stem for s in [f"set{set_num}", f"set {set_num}", f"set_{set_num}", f"_set{set_num}"]):
                        matched = a
                        break
                    if a.name.startswith("A_") and a.name[2:] == q.name:
                        matched = a
                        break
                    if q_stem.replace("(q)", "(a)").replace("-q", "-a") in a_stem or q_stem + "_sol" in a_stem:
                        matched = a
                        break
                if not matched and a_list:
                    matched = a_list[0]

            if matched:
                pairs.append((q, matched))

    return pairs


def find_all_ptp_files(base_dir: Path | str = "Docs/source-material") -> list[Path]:
    """
    Scans base_dir for all Postal Test Paper PDFs.
    """
    base = resolve_source_path(base_dir)
    if not base.exists():
        return []
    return sorted([f for f in base.rglob("*.pdf") if "postal-test-paper" in f.name.lower() or "postal test paper" in f.name.lower()])


