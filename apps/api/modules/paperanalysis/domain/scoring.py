"""
Pure, versioned scoring engine ps-1 for F-11.
No database, no I/O, no clock, no randomness. Byte-identical deterministic output.
Reference: PRD 6.1 and ERD 3.5.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from .explain import render_reason
from .params import DEFAULT_PARAMS
from .types import ReasonPayload, ScoredChapter


@dataclass(frozen=True)
class PaperSittingInput:
    paper_id: UUID
    term_code: str
    paper_kind: str  # "exam", "mtp", "rtp", "sample"
    age_index: int  # 0 for newest, 1 for second newest, etc.
    effective_marks: float
    is_carried: bool = False


@dataclass(frozen=True)
class ChapterInput:
    chapter_id: UUID
    chapter_key: str
    name: str
    section: str
    sort_order: int
    marks_min: float | None = None
    marks_max: float | None = None
    sittings: list[PaperSittingInput] = field(default_factory=list)
    comparability: str = "native"
    coverage_fraction: float = 0.0  # 0 to 1
    practice_answered: int = 0
    practice_correct: float = 0.0
    weakness_source: str = "practice_accuracy"


@dataclass(frozen=True)
class SubjectScoringInput:
    subject_key: str
    total_subject_marks: float
    chapters: list[ChapterInput]
    days_left: int | None = None


def score_subject(
    inp: SubjectScoringInput,
    params: dict[str, Any] | None = None,
) -> list[ScoredChapter]:
    """
    Computes priority scores, Pareto tiers, confidence, components, and reasons for all chapters in a subject.
    Pure and deterministic.
    """
    p = params or DEFAULT_PARAMS
    recency_lambda = float(p.get("recency_lambda", 0.85))
    kind_weights = p.get("kind_weight", {"exam": 1.0, "mtp": 0.4, "rtp": 0.3, "sample": 0.3})
    carry_weight_discount = float(p.get("carry_weight", 0.7))
    shrink_k = float(p.get("shrink_k", 2.0))
    acc_prior_strength = float(p.get("acc_prior_strength", 5.0))
    urgency_ref_days = float(p.get("urgency_ref_days", 120))
    core_cut = float(p.get("tier_core_share", 0.50))
    next_cut = float(p.get("tier_next_share", 0.80))
    min_exam_for_core = int(p.get("min_exam_papers_for_core", 2))

    # Days left and urgency blend
    days = inp.days_left if inp.days_left is not None else int(p.get("default_days_left", 90))
    u = max(0.0, min(1.0, 1.0 - (days / urgency_ref_days)))

    w_far = p["weights_far"]
    w_near = p["weights_near"]
    wH = w_far["H"] * (1.0 - u) + w_near["H"] * u
    wF = w_far["F"] * (1.0 - u) + w_near["F"] * u
    wT = w_far["T"] * (1.0 - u) + w_near["T"] * u
    wW = w_far["W"] * (1.0 - u) + w_near["W"] * u
    wG = w_far["G"] * (1.0 - u) + w_near["G"] * u

    num_chapters = len(inp.chapters)
    fallback_prior = (inp.total_subject_marks / num_chapters) if num_chapters > 0 else 5.0

    # Step 1: Compute historical expectation E, frequency F, and trend T for each chapter
    intermediate: list[dict[str, Any]] = []
    for ch in inp.chapters:
        # Prior for chapter
        if ch.marks_min is not None and ch.marks_max is not None:
            prior = (ch.marks_min + ch.marks_max) / 2.0
            weight_basis = "official"
        elif ch.marks_max is not None:
            prior = ch.marks_max
            weight_basis = "official"
        elif ch.marks_min is not None:
            prior = ch.marks_min
            weight_basis = "official"
        else:
            prior = fallback_prior
            weight_basis = "inferred"

        # Calculate n_eff, sum(w*m), and sum(w * [m > 0])
        n_eff = 0.0
        weighted_marks_sum = 0.0
        asked_weighted_sum = 0.0
        exam_papers_count = 0
        total_papers_count = len(ch.sittings)
        marks_by_sitting: list[float] = []
        asked_sittings_count = 0
        max_sitting_mark = 0.0
        last_asked_term = None

        # Sort sittings by age_index ascending (0 is newest)
        sorted_sittings = sorted(ch.sittings, key=lambda s: s.age_index)
        for s in sorted_sittings:
            k_w = float(kind_weights.get(s.paper_kind, 0.4))
            c_w = carry_weight_discount if s.is_carried else 1.0
            decay = recency_lambda ** s.age_index
            w_i = decay * k_w * c_w
            n_eff += w_i
            weighted_marks_sum += w_i * s.effective_marks
            marks_by_sitting.append(s.effective_marks)

            if s.paper_kind == "exam":
                exam_papers_count += 1
            if s.effective_marks > 0:
                asked_weighted_sum += w_i
                asked_sittings_count += 1
                if s.effective_marks > max_sitting_mark:
                    max_sitting_mark = s.effective_marks
                if last_asked_term is None:
                    last_asked_term = s.term_code

        if n_eff > 0:
            E_raw = weighted_marks_sum / n_eff
            E = (n_eff * E_raw + shrink_k * prior) / (n_eff + shrink_k)
            F = asked_weighted_sum / n_eff
        else:
            E = prior
            F = 0.0
            weight_basis = "prior_only"

        # Trend T
        if total_papers_count >= 5:
            recent_3 = marks_by_sitting[:3]
            prev_3 = marks_by_sitting[3:6]
            m_rec = sum(recent_3) / len(recent_3)
            m_prev = sum(prev_3) / len(prev_3)
            m_all = sum(marks_by_sitting) / len(marks_by_sitting)
            denom = max(1.0, m_all)
            r = (m_rec - m_prev) / denom
            r_clamped = max(-1.0, min(1.0, r))
            T = (r_clamped + 1.0) / 2.0
            raw_r = r_clamped
        else:
            T = 0.5
            raw_r = 0.0

        # Weakness W = 1 - acc
        # acc = (correct + 5 * 0.5) / (answered + 5)
        ans = ch.practice_answered
        corr = ch.practice_correct
        acc = (corr + acc_prior_strength * 0.5) / (ans + acc_prior_strength)
        W = 1.0 - acc

        # Gap G = 1 - cov
        cov = max(0.0, min(1.0, ch.coverage_fraction))
        G = 1.0 - cov

        # Confidence
        carried_count = sum(1 for s in ch.sittings if s.is_carried)
        if total_papers_count >= 6 and carried_count == 0:
            confidence = "high"
        elif (4 <= total_papers_count <= 5) or (total_papers_count >= 6 and carried_count > 0):
            confidence = "medium"
        elif total_papers_count == 3:
            confidence = "low"
        else:
            confidence = "insufficient"

        intermediate.append({
            "ch": ch,
            "E": E,
            "F": F,
            "T": T,
            "W": W,
            "G": G,
            "raw_r": raw_r,
            "total_papers_count": total_papers_count,
            "exam_papers_count": exam_papers_count,
            "asked_sittings_count": asked_sittings_count,
            "max_sitting_mark": max_sitting_mark,
            "last_asked_term": last_asked_term,
            "confidence": confidence,
            "weight_basis": weight_basis,
            "carried_count": carried_count,
            "cov": cov,
            "ans": ans,
            "corr": corr,
        })

    # Step 2: Compute H relative to max E
    max_E = max((item["E"] for item in intermediate), default=1.0)
    if max_E <= 0:
        max_E = 1.0

    scored_items: list[dict[str, Any]] = []
    for item in intermediate:
        H = item["E"] / max_E
        F = item["F"]
        T = item["T"]
        W = item["W"]
        G = item["G"]

        raw_score = 100.0 * (wH * H + wF * F + wT * T + wW * W + wG * G)
        score = round(raw_score, 1)

        item["H"] = H
        item["score"] = score
        scored_items.append(item)

    # Step 3: Sort by score desc, then E desc, then sort_order, then id
    scored_items.sort(
        key=lambda it: (-it["score"], -it["E"], it["ch"].sort_order, str(it["ch"].chapter_id))
    )

    # Step 4: Pareto Tiers
    total_E = sum(it["E"] for it in scored_items)
    cum_E = 0.0
    for idx, it in enumerate(scored_items):
        it["rank"] = idx + 1
        cum_E += it["E"]
        ratio = (cum_E / total_E) if total_E > 0 else 1.0

        if ratio <= core_cut and it["exam_papers_count"] >= min_exam_for_core:
            it["tier"] = "core"
        elif ratio <= next_cut:
            it["tier"] = "next"
        else:
            it["tier"] = "rest"

    # Step 5: Reasons & Caveats Generation
    results: list[ScoredChapter] = []
    for it in scored_items:
        ch = it["ch"]
        reasons: list[ReasonPayload] = []

        # 1. Yield reason
        if it["asked_sittings_count"] > 0:
            p_code = "asked_in_window"
            p_params = {
                "max": round(it["max_sitting_mark"], 1),
                "asked_n": it["asked_sittings_count"],
                "window_n": it["total_papers_count"],
            }
            reasons.append(ReasonPayload(code=p_code, params=p_params, sentence=render_reason(p_code, p_params)))

        # 2. Trend reason
        if it["total_papers_count"] >= 5 and abs(it["raw_r"]) >= 0.15:
            p_code = "rising_trend" if it["raw_r"] > 0 else "falling_trend"
            # calculate recent vs prev mean
            recent_mean = round(sum([s.effective_marks for s in ch.sittings[:3]]) / 3.0, 1)
            prev_mean = round(sum([s.effective_marks for s in ch.sittings[3:6]]) / len(ch.sittings[3:6]), 1)
            p_params = {"recent": recent_mean, "earlier": prev_mean}
            reasons.append(ReasonPayload(code=p_code, params=p_params, sentence=render_reason(p_code, p_params)))

        # 3. Practice / Weakness reason
        if it["ans"] >= 10:
            p_code = "weak_practice"
            p_params = {"correct": int(it["corr"]), "answered": it["ans"]}
            reasons.append(ReasonPayload(code=p_code, params=p_params, sentence=render_reason(p_code, p_params)))
        elif it["ans"] < 5:
            p_code = "not_enough_practice"
            p_params = {"answered": it["ans"]}
            reasons.append(ReasonPayload(code=p_code, params=p_params, sentence=render_reason(p_code, p_params)))

        # 4. Coverage reason
        cov_pct = int(round(it["cov"] * 100))
        if cov_pct < 40 and len(reasons) < 3:
            p_code = "low_coverage"
            p_params = {"cov_pct": cov_pct}
            reasons.append(ReasonPayload(code=p_code, params=p_params, sentence=render_reason(p_code, p_params)))
        elif cov_pct >= 80 and len(reasons) < 3:
            p_code = "high_coverage"
            p_params = {"cov_pct": cov_pct}
            reasons.append(ReasonPayload(code=p_code, params=p_params, sentence=render_reason(p_code, p_params)))

        # Cap at 3 reasons
        final_reasons = reasons[:3]

        # Caveats
        caveats: list[str] = []
        if it["total_papers_count"] < 4:
            caveats.append(render_reason("limited_history", {"papers_n": it["total_papers_count"]}))
        if it["carried_count"] > 0:
            caveats.append(render_reason("carried_history", {"carried_n": it["carried_count"]}))
        if ch.comparability == "restructured":
            caveats.append(render_reason("restructured", {}))
        elif ch.comparability == "new":
            caveats.append(render_reason("new_chapter", {}))

        results.append(
            ScoredChapter(
                chapter_id=ch.chapter_id,
                chapter_key=ch.chapter_key,
                name=ch.name,
                rank=it["rank"],
                score=it["score"],
                tier=it["tier"],
                confidence=it["confidence"],
                components={
                    "H": round(it["H"], 3),
                    "F": round(it["F"], 3),
                    "T": round(it["T"], 3),
                    "W": round(it["W"], 3),
                    "G": round(it["G"], 3),
                },
                expected_marks=round(it["E"], 1),
                weight_basis=it["weight_basis"],
                comparability=ch.comparability,
                history={
                    "asked_n": it["asked_sittings_count"],
                    "window_n": it["total_papers_count"],
                    "max": round(it["max_sitting_mark"], 1),
                    "last_asked_term_code": it["last_asked_term"],
                },
                student={
                    "coverage_pct": int(round(it["cov"] * 100)),
                    "answered": it["ans"],
                    "correct": it["corr"],
                    "weakness_source": ch.weakness_source,
                },
                reasons=final_reasons,
                caveats=caveats,
                links={
                    "chapter": f"/app/analysis/{inp.subject_key}/{ch.chapter_key}",
                    "practise": f"/app/practice/new?chapter={ch.chapter_id}",
                    "syllabus": f"/app/syllabus/{inp.subject_key}/{ch.chapter_key}",
                },
            )
        )

    return results
