"""
Built-in question pickers (F-06 ERD 3.3).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from modules.questionbank import selectors as qb_selectors
from modules.questionbank.models import CollectionItem

from ..models import QuestionState
from ..registry import PickContext, PickedItem, register_picker


def pick_filter(ctx: PickContext) -> list[PickedItem]:
    flt = ctx.spec.get("filter")
    if flt is None:
        flt = {k: v for k, v in ctx.spec.items() if k not in ("count", "order", "seed")}
    count = ctx.spec.get("count", ctx.limit)
    seed = ctx.spec.get("seed") or ctx.rng.randint(1, 1_000_000_000)
    order = ctx.spec.get("order", "random")
    qids = qb_selectors.search_ids(ctx.user_id, flt, order=order, seed=seed, limit=count)
    return [PickedItem(question_id=qid) for qid in qids]


def pick_wrong_only(ctx: PickContext) -> list[PickedItem]:
    qs = QuestionState.objects.filter(
        user_id=ctx.user_id,
        last_result__in=["incorrect", "partial"],
    )
    if "chapter_id" in ctx.spec and ctx.spec["chapter_id"]:
        qs = qs.filter(chapter_id=ctx.spec["chapter_id"])

    count = ctx.spec.get("count", ctx.limit)
    qids = list(qs.order_by("-last_attempt_at").values_list("question_id", flat=True)[: count * 2])
    if ctx.spec.get("order") == "random":
        ctx.rng.shuffle(qids)
    return [PickedItem(question_id=qid) for qid in qids[:count]]


def pick_unattempted(ctx: PickContext) -> list[PickedItem]:
    flt = dict(ctx.spec.get("filter", {}))
    flt["personal"] = "unattempted"
    count = ctx.spec.get("count", ctx.limit)
    seed = ctx.spec.get("seed") or ctx.rng.randint(1, 1_000_000_000)
    qids = qb_selectors.search_ids(ctx.user_id, flt, order="random", seed=seed, limit=count)
    return [PickedItem(question_id=qid) for qid in qids]


def pick_collection(ctx: PickContext) -> list[PickedItem]:
    collection_id = ctx.spec.get("collection_id")
    if not collection_id:
        raise ValueError("Missing 'collection_id' in collection picker spec.")

    items = list(
        CollectionItem.objects.filter(collection_id=collection_id)
        .order_by("position")
        .values_list("question_id", flat=True)
    )
    if ctx.spec.get("order") == "random":
        ctx.rng.shuffle(items)
    count = ctx.spec.get("count", ctx.limit)
    return [PickedItem(question_id=qid) for qid in items[:count]]


def pick_explicit_items(ctx: PickContext) -> list[PickedItem]:
    raw_items = ctx.spec.get("items", [])
    results: list[PickedItem] = []
    for it in raw_items:
        qid = uuid.UUID(str(it["question_id"]))
        vid = uuid.UUID(str(it["version_id"])) if it.get("version_id") else None
        marks = Decimal(str(it["marks"])) if it.get("marks") is not None else None
        neg = Decimal(str(it["negative_marks"])) if it.get("negative_marks") is not None else None
        label = it.get("section_label")
        results.append(
            PickedItem(question_id=qid, version_id=vid, marks=marks, negative_marks=neg, section_label=label)
        )
    return results


def register_builtin_pickers() -> None:
    register_picker("filter", pick_filter, description="Pick questions matching a QuestionFilter")
    register_picker("wrong_only", pick_wrong_only, description="Pick previous incorrect/partial mistake questions")
    register_picker("unattempted", pick_unattempted, description="Pick unattempted questions matching filters")
    register_picker("collection", pick_collection, description="Pick questions from a collection")
    register_picker(
        "explicit_items", pick_explicit_items, description="Pick an explicit list of ordered question items"
    )
