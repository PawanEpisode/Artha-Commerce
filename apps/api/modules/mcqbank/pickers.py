"""
MCQ Bank question pickers and origin registration (F-05 ERD 3.2, 3.5).
Owns ZERO question rows: delegates to questionbank selectors and collection items.
"""

from __future__ import annotations

import uuid

from modules.practice.models import QuestionState
from modules.practice.registry import (
    OriginSpec,
    PickContext,
    PickedItem,
    register_origin,
    register_picker,
)
from modules.questionbank import selectors as qb_selectors
from modules.questionbank.models import CollectionItem, Question

from .domain.adaptive import compute_item_difficulty, predict_success_probability
from .domain.blueprint import allocate_quotas, apply_smart_mix
from .domain.specs import McqAdaptivePickerSpec, McqBlueprintPickerSpec, McqSetPickerSpec
from .models import AbilityEstimate, AdaptiveRun, McqSet


def pick_mcq_set(ctx: PickContext) -> list[PickedItem]:
    """Picks questions belonging to a published hosted McqSet."""
    validated = McqSetPickerSpec.model_validate(ctx.spec)
    try:
        set_obj = McqSet.objects.get(id=validated.set_id, status=McqSet.Status.PUBLISHED)
    except McqSet.DoesNotExist:
        return []

    if set_obj.delivery != McqSet.Delivery.HOSTED or not set_obj.collection_id:
        return []

    qids = list(
        CollectionItem.objects.filter(collection_id=set_obj.collection_id)
        .order_by("position")
        .values_list("question_id", flat=True)
    )

    if validated.order == "random":
        ctx.rng.shuffle(qids)

    limit = validated.count or len(qids)
    return [PickedItem(question_id=qid) for qid in qids[:limit]]


def pick_mcq_blueprint(ctx: PickContext) -> list[PickedItem]:
    """
    Picks questions according to blueprint quotas and smart mix.
    Always restricts questions to choice kinds (kind_groups=['choice']).
    """
    validated = McqBlueprintPickerSpec.model_validate(ctx.spec)
    total_count = validated.count

    flt = dict(validated.filter or {})
    flt["kind_groups"] = ["choice"]

    # Gather chapter quotas
    quotas: dict[str, int] = {}
    if validated.chapters:
        for cq in validated.chapters:
            key = str(cq.chapter_id) if cq.chapter_id else (cq.chapter_key or "")
            if key:
                quotas[key] = cq.n
    elif validated.subject_key:
        from modules.syllabus.models import Chapter

        chapters = list(
            Chapter.objects.filter(
                subject__code=validated.subject_key,
                scheme__status="published",
            ).order_by("sort_order")
        )
        if not chapters:
            chapters = list(Chapter.objects.filter(subject__code=validated.subject_key).order_by("sort_order"))

        ch_keys = [str(c.id) for c in chapters]
        weights = [float(c.marks_max or c.marks_min or 5) for c in chapters]
        availabilities = [qb_selectors.count_matching(ctx.user_id, {**flt, "chapter_id": c.id}) for c in chapters]
        quotas = allocate_quotas(total_count, ch_keys, weights, availabilities)
    else:
        # Default fallback: pick directly from filter
        seed = ctx.rng.randint(1, 1_000_000_000)
        qids = qb_selectors.search_ids(ctx.user_id, flt, order="random", seed=seed, limit=total_count)
        return [PickedItem(question_id=qid) for qid in qids]

    all_picked_ids: list[uuid.UUID] = []

    for ch_key, quota in quotas.items():
        if quota <= 0:
            continue
        try:
            ch_uuid = uuid.UUID(ch_key)
            ch_filter = {**flt, "chapter_id": ch_uuid}
        except ValueError:
            ch_filter = {**flt, "chapter_key": ch_key}

        # Available question IDs in this chapter
        available_ids = list(qb_selectors.search_ids(ctx.user_id, ch_filter, order="created", limit=500))
        if not available_ids:
            continue

        if validated.mix == "smart":
            # State of these questions for the student
            states = {
                qs.question_id: qs
                for qs in QuestionState.objects.filter(user_id=ctx.user_id, question_id__in=available_ids)
            }
            unseen = [qid for qid in available_ids if qid not in states]
            wrong_last = [
                qid for qid in available_ids if qid in states and states[qid].last_result in ("incorrect", "partial")
            ]
            due = [qid for qid in available_ids if qid in states and states[qid].is_bookmarked]
            others = [qid for qid in available_ids if qid not in unseen and qid not in wrong_last]

            ctx.rng.shuffle(unseen)
            ctx.rng.shuffle(wrong_last)
            ctx.rng.shuffle(due)
            ctx.rng.shuffle(others)

            chosen = apply_smart_mix(unseen, wrong_last, due, others, quota)
            all_picked_ids.extend(chosen)
        else:
            ctx.rng.shuffle(available_ids)
            all_picked_ids.extend(available_ids[:quota])

    return [PickedItem(question_id=qid) for qid in all_picked_ids[:total_count]]


def pick_mcq_adaptive(ctx: PickContext) -> list[PickedItem]:
    """Picks questions for an adaptive round matching target probability p=0.70."""
    validated = McqAdaptivePickerSpec.model_validate(ctx.spec)
    try:
        run = AdaptiveRun.objects.get(id=validated.run_id, user_id=ctx.user_id, status=AdaptiveRun.Status.ACTIVE)
    except AdaptiveRun.DoesNotExist:
        return []

    # Ability estimate for this scope
    try:
        est = AbilityEstimate.objects.get(
            user_id=ctx.user_id,
            scope_type=run.scope_type,
            scope_id=run.scope_id,
        )
        theta = float(est.theta)
    except AbilityEstimate.DoesNotExist:
        theta = 0.0

    flt: dict = {"kind_groups": ["choice"]}
    if run.scope_type == "chapter":
        flt["chapter_id"] = run.scope_id
    else:
        flt["subject_key"] = run.subject_key

    # Exclude already attempted questions in active rounds
    seen_ids = set(QuestionState.objects.filter(user_id=ctx.user_id).values_list("question_id", flat=True))

    candidate_ids = list(qb_selectors.search_ids(ctx.user_id, flt, order="created", limit=2000))
    # Prefer unseen questions
    unseen = [qid for qid in candidate_ids if qid not in seen_ids]
    pool = unseen if len(unseen) >= 20 else candidate_ids
    if not pool:
        pool = candidate_ids
    if not pool:
        return []

    # Score candidates by |P - target_p|
    target_p = float(run.target_p)
    scored = []
    questions_map = {q.id: q for q in Question.objects.filter(id__in=pool[:200])}
    for qid in pool[:200]:
        q = questions_map.get(qid)
        diff = q.difficulty if q else None
        b = compute_item_difficulty(diff)
        p = predict_success_probability(theta, b)
        gap = abs(p - target_p)
        scored.append((gap, qid))

    scored.sort(key=lambda item: item[0])
    chosen = [qid for _, qid in scored[: run.round_size]]
    return [PickedItem(question_id=qid) for qid in chosen]


def register_mcq_pickers_and_origins() -> None:
    """Registers pickers and origins with the practice engine."""
    register_picker(
        "mcq_set",
        pick_mcq_set,
        description="Questions of a published hosted MCQ set",
    )
    register_picker(
        "mcq_blueprint",
        pick_mcq_blueprint,
        description="Per-chapter quotas, difficulty mix, and smart mix",
    )
    register_picker(
        "mcq_adaptive",
        pick_mcq_adaptive,
        description="Questions matched to student ability for adaptive practice",
    )
    register_origin(
        "mcq_bank",
        OriginSpec(
            allowed_modes={"untimed", "timed", "chapter_quiz", "revision", "custom_test"},
            default_feedback_policy=None,
            unique_per_user=False,
        ),
    )
