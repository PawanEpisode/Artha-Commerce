"""
Question bank services (writes, actor-checked) (F-06 ERD 3.2).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from core.events import emit_domain_event

from .domain.content import (
    compute_content_hash,
    extract_search_text,
    lint_explanation,
    lint_option,
    lint_stem,
)
from .domain.difficulty import estimate_difficulty
from .domain.fingerprint import (
    compute_fp_exact,
    compute_fp_template,
    compute_simhash_and_bands,
    hamming_distance,
)
from .domain.payload import QuestionPayload
from .models import (
    AnswerKey,
    AuditLog,
    Collection,
    CollectionItem,
    DuplicateLink,
    Fingerprint,
    Option,
    Question,
    QuestionTopic,
    QuestionVersion,
    Report,
    Review,
    Rubric,
    RubricStep,
    SavedFilter,
    ShareLink,
    Takedown,
    TakedownItem,
    Verification,
)
from .registry import get_kind


class ChecksFailed(Exception):
    def __init__(self, checks: list[str]) -> None:
        self.checks = checks
        super().__init__("; ".join(checks))


@dataclass
class UpsertResult:
    question: Question
    version: QuestionVersion
    outcome: Literal["created", "new_version", "unchanged"]
    # Set when a brand-new row was an exact copy of an existing question and was merged into it. Callers that attach the
    # question to something (a paper, a collection) should attach `canonical` instead.
    duplicate_of: Question | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def canonical(self) -> Question:
        return self.duplicate_of or self.question


@dataclass
class DeleteReport:
    questions_deleted: int
    questions_anonymised: int
    collections_deleted: int
    saved_filters_deleted: int
    share_links_deleted: int


@dataclass
class MappingIn:
    chapter_id: uuid.UUID
    topic_id: uuid.UUID | None = None
    is_primary: bool = False
    origin: str = "editor"
    confidence: Decimal | None = None
    status: str = "confirmed"  # "suggested" for an automatic guess an editor has not confirmed


def _attach_version_children(
    question: Question, version: QuestionVersion, payload: QuestionPayload, actor_id: Any
) -> None:
    """Options, numeric key, rubric and fingerprint of one version. Shared by create_draft and upsert_from_source."""
    stem_md = payload.get("stem_md", "")
    options_data = payload.get("options") or []
    opt_bodies = [opt.get("body_md", "") for opt in options_data]
    marks = version.marks
    kind_name = question.kind
    for pos, opt in enumerate(options_data):
        Option.objects.create(
            version=version,
            position=pos,
            body_md=opt.get("body_md", ""),
            is_correct=bool(opt.get("is_correct", False)),
            feedback_md=opt.get("feedback_md", ""),
            pinned=bool(opt.get("pinned", False)),
        )

    num_key_data = payload.get("numeric_key")
    if num_key_data:
        AnswerKey.objects.create(
            version=version,
            numeric_value=Decimal(str(num_key_data.get("numeric_value", 0))),
            tolerance_abs=Decimal(str(num_key_data.get("tolerance_abs", 0))),
            tolerance_rel=Decimal(str(num_key_data.get("tolerance_rel", 0))),
            accepted_values=[str(v) for v in num_key_data.get("accepted_values", [])],
            unit=num_key_data.get("unit", ""),
            unit_required=bool(num_key_data.get("unit_required", False)),
            key_note=num_key_data.get("key_note", ""),
        )

    rubric_data = payload.get("rubric")
    if rubric_data:
        rubric = Rubric.objects.create(
            version=version,
            reference_solution_md=rubric_data.get("reference_solution_md", ""),
            answer_template_md=rubric_data.get("answer_template_md", ""),
            total_marks=marks,
            keywords=rubric_data.get("keywords", []),
            common_mistakes_md=rubric_data.get("common_mistakes_md", ""),
        )
        for pos, step in enumerate(rubric_data.get("steps", [])):
            RubricStep.objects.create(
                rubric=rubric,
                position=pos,
                title=step.get("title", f"Step {pos + 1}"),
                description_md=step.get("description_md", ""),
                marks=Decimal(str(step.get("marks", 0))),
                kind=step.get("kind", RubricStep.Kind.CONCEPT),
                mandatory=bool(step.get("mandatory", False)),
                partial_allowed=bool(step.get("partial_allowed", True)),
            )

    # The key is part of the fingerprint, so two copies of a stem with different answers never count as the same question.
    key_parts = sorted(o.get("body_md", "") for o in options_data if o.get("is_correct"))
    if num_key_data:
        key_parts.append(str(num_key_data.get("numeric_value", "")))
    key_str = "|".join(key_parts)
    simhash, b0, b1, b2, b3 = compute_simhash_and_bands(stem_md)
    Fingerprint.objects.update_or_create(
        question=question,
        defaults={
            "version_id": version.id,
            "fp_exact": compute_fp_exact(stem_md, opt_bodies, key_str),
            "fp_template": compute_fp_template(stem_md, opt_bodies, key_str),
            "simhash": simhash,
            "b0": b0,
            "b1": b1,
            "b2": b2,
            "b3": b3,
            "scope_owner": actor_id,
            "kind": kind_name,
        },
    )


@transaction.atomic
def create_draft(
    actor_id: uuid.UUID,
    payload: QuestionPayload,
    *,
    client_id: uuid.UUID | None = None,
) -> Question:
    """
    Creates a new draft question and its version 1 from a QuestionPayload (F-06 ERD 3.2).
    Idempotent on (owner_user_id, client_id) if client_id is provided.
    """
    if client_id:
        existing = Question.objects.filter(owner_user_id=actor_id, client_id=client_id).first()
        if existing:
            return existing

    kind_name = payload.get("kind", "mcq_single")
    kind_spec = get_kind(kind_name)
    if not kind_spec:
        raise ValueError(f"Unknown question kind: {kind_name}")

    errors = kind_spec.validate_payload(payload)
    stem_errors = lint_stem(payload.get("stem_md", ""))
    errors.extend(stem_errors)
    if errors:
        raise ChecksFailed(errors)

    stem_md = payload.get("stem_md", "")
    options_data = payload.get("options") or []
    opt_bodies = [opt.get("body_md", "") for opt in options_data]
    explanation_md = payload.get("explanation_md", "")

    stem_head, search_text = extract_search_text(stem_md, opt_bodies, explanation_md)
    marks = Decimal(str(payload.get("marks", 1)))
    content_hash = compute_content_hash(
        stem_md,
        options_data,
        payload.get("numeric_key"),
        payload.get("rubric"),
        marks,
    )

    labels = payload.get("labels") or {}
    question = Question.objects.create(
        kind=kind_name,
        ownership=Question.Ownership.USER_CREATED,
        owner_user_id=actor_id,
        created_by=actor_id,
        rights_status=Question.RightsStatus.ORIGINAL,
        visibility=Question.Visibility.PRIVATE,
        status=Question.Status.ACTIVE,
        client_id=client_id,
        source_kind=labels.get("source_kind", Question.SourceKind.USER),
        source_name=labels.get("source_name", ""),
        source_url=labels.get("source_url", ""),
        source_ref=labels.get("source_ref", ""),
        source_year=labels.get("source_year"),
        source_term_code=labels.get("source_term_code", ""),
        difficulty=(
            {"easy": 1, "medium": 3, "hard": 4}.get(str(labels.get("difficulty")).lower())
            if isinstance(labels.get("difficulty"), str)
            else labels.get("difficulty")
        )
        or estimate_difficulty(
            kind=kind_name, stem=stem_md, options=opt_bodies, marks=marks, solution=payload.get("explanation_md", "")
        ),
        bloom=labels.get("bloom", ""),
        nature=labels.get("nature", ""),
        marks=marks,
        stem_head=stem_head,
        search_text=search_text,
        tag_slugs=labels.get("tags", []),
    )

    neg_marks = payload.get("negative_marks")
    version = QuestionVersion.objects.create(
        question=question,
        version_no=1,
        state=QuestionVersion.State.DRAFT,
        change_kind=QuestionVersion.ChangeKind.CREATE,
        authored_by=actor_id,
        stem_md=stem_md,
        stem_text=stem_head,
        explanation_md=explanation_md,
        explanation_source=payload.get("explanation_source", ""),
        reference_labels=payload.get("reference_labels", []),
        marks=marks,
        negative_marks=Decimal(str(neg_marks)) if neg_marks is not None else None,
        multi_scoring=payload.get("multi_scoring", QuestionVersion.MultiScoring.ALL_OR_NOTHING),
        content_hash=content_hash,
    )

    question.current_version = version
    question.save(update_fields=["current_version", "updated_at"])

    _attach_version_children(question, version, payload, actor_id)

    return question


@transaction.atomic
def save_live(
    actor_id: uuid.UUID,
    question_id: uuid.UUID,
    visibility: Literal["private", "link"],
) -> QuestionVersion:
    """
    Saves a draft as active and live for private or link visibility (author action).
    """
    question = Question.objects.select_for_update().get(id=question_id)
    if str(question.owner_user_id) != str(actor_id):
        raise PermissionError("Only the owner can save question directly.")

    version = question.current_version or question.versions.filter(state=QuestionVersion.State.DRAFT).first()
    if not version:
        raise ValueError("No version to save.")

    if question.live_version and question.live_version_id != version.id:
        QuestionVersion.objects.filter(id=question.live_version_id).update(
            state=QuestionVersion.State.SUPERSEDED, superseded_at=timezone.now()
        )

    version.state = QuestionVersion.State.LIVE
    version.live_at = timezone.now()
    version.save(update_fields=["state", "live_at", "updated_at"])

    question.live_version = version
    question.visibility = visibility
    question.status = Question.Status.ACTIVE
    if not question.published_at and visibility == Question.Visibility.LINK:
        question.published_at = timezone.now()
    question.save(update_fields=["live_version", "visibility", "status", "published_at", "updated_at"])

    return version


@transaction.atomic
def submit_for_review(actor_id: uuid.UUID, question_id: uuid.UUID) -> Review:
    """Submits a draft question version for editorial review to become public."""
    question = Question.objects.select_for_update().get(id=question_id)
    if str(question.owner_user_id) != str(actor_id):
        raise PermissionError("Only the owner can submit for review.")

    version = question.current_version or question.versions.filter(state=QuestionVersion.State.DRAFT).first()
    if not version:
        raise ValueError("No draft version available to submit for review.")

    # Validation checks
    errors: list[str] = []
    kind_spec = get_kind(question.kind)
    if kind_spec:
        for idx, opt_body in enumerate(version.options.order_by("position").values_list("body_md", flat=True), start=1):
            errors.extend(lint_option(opt_body, idx))
        expl_errors = lint_explanation(version.explanation_md, question.kind, is_public=True)
        errors.extend(expl_errors)

    if errors:
        raise ChecksFailed(errors)

    version.state = QuestionVersion.State.IN_REVIEW
    version.submitted_at = timezone.now()
    version.save(update_fields=["state", "submitted_at", "updated_at"])

    now = timezone.now()
    review, _ = Review.objects.update_or_create(
        version=version,
        defaults={
            "question": question,
            "kind": Review.Kind.NEW_PUBLIC if question.live_version is None else Review.Kind.EDIT_PUBLIC,
            "status": Review.Status.PENDING,
            "submitted_by": actor_id,
            "submitted_at": now,
            "sla_due_at": now + timezone.timedelta(hours=24),
        },
    )
    return review


@transaction.atomic
def publish_version(
    editor_id: uuid.UUID,
    version_id: uuid.UUID,
    *,
    visibility: str = "public",
) -> QuestionVersion:
    """
    Publishes a question version (editor or system action), making it live.
    Emits question_version_live.
    """
    version = QuestionVersion.objects.select_for_update().get(id=version_id)
    question = Question.objects.select_for_update().get(id=version.question_id)

    # Supersede older live version if present
    if question.live_version_id and question.live_version_id != version.id:
        QuestionVersion.objects.filter(id=question.live_version_id).update(
            state=QuestionVersion.State.SUPERSEDED, superseded_at=timezone.now()
        )

    now = timezone.now()
    version.state = QuestionVersion.State.LIVE
    version.live_at = now
    version.save(update_fields=["state", "live_at", "updated_at"])

    question.live_version = version
    question.visibility = visibility
    question.status = Question.Status.ACTIVE
    if not question.published_at:
        question.published_at = now
    question.marks = version.marks
    question.save(update_fields=["live_version", "visibility", "status", "published_at", "marks", "updated_at"])

    # Emit domain event (F-06 ERD 3.4)
    emit_domain_event(
        "question_version_live",
        {
            "question_id": str(question.id),
            "version_id": str(version.id),
            "version_no": version.version_no,
            "visibility": question.visibility,
            "ownership": question.ownership,
            "change_kind": version.change_kind,
            "chapter_id": str(question.primary_chapter_id) if question.primary_chapter_id else None,
            "kind": question.kind,
            "collection_ids": [],
        },
        actor_id=editor_id,
        key=f"pub:{version.id}",
    )

    return version


@transaction.atomic
def decide_review(
    editor_id: uuid.UUID,
    review_id: uuid.UUID,
    decision: str,
    *,
    code: str,
    note: str = "",
    field_comments: list | None = None,
) -> Review:
    """Decides a pending moderation review."""
    review = Review.objects.select_for_update().get(id=review_id)
    now = timezone.now()

    if decision == "approved":
        publish_version(editor_id, review.version_id, visibility="public")
        review.status = Review.Status.APPROVED
    elif decision == "changes_requested":
        review.version.state = QuestionVersion.State.DRAFT
        review.version.save(update_fields=["state", "updated_at"])
        review.status = Review.Status.CHANGES_REQUESTED
    elif decision == "rejected":
        review.version.state = QuestionVersion.State.REJECTED
        review.version.save(update_fields=["state", "updated_at"])
        review.status = Review.Status.REJECTED
    else:
        raise ValueError(f"Unknown review decision: {decision}")

    review.decided_by = editor_id
    review.decided_at = now
    review.decision_code = code
    review.decision_note = note
    review.field_comments = field_comments or []
    review.save()

    emit_domain_event(
        "contribution_decided",
        {
            "question_id": str(review.question_id),
            "author_user_id": str(review.submitted_by) if review.submitted_by else None,
            "decision": decision,
            "code": code,
            "note_present": bool(note),
        },
        actor_id=editor_id,
        key=f"rev:{review.id}",
    )

    return review


@transaction.atomic
def set_mapping(actor_id: uuid.UUID, question_id: uuid.UUID, mappings: list[MappingIn]) -> None:
    """Updates syllabus taxonomy mappings for a question."""
    from modules.syllabus.models import Chapter

    question = Question.objects.select_for_update().get(id=question_id)
    QuestionTopic.objects.filter(question=question).delete()

    primary_found = False
    for m in mappings:
        ch = Chapter.objects.select_related("subject__scheme__level__course").get(id=m.chapter_id)
        subj = ch.subject
        scheme = subj.scheme

        QuestionTopic.objects.create(
            question=question,
            chapter=ch,
            topic_id=m.topic_id,
            subject=subj,
            scheme=scheme,
            subject_key=subj.key,
            chapter_key=ch.key,
            is_primary=m.is_primary,
            status=m.status,
            origin=m.origin,
            confidence=m.confidence,
            decided_by=actor_id,
            decided_at=timezone.now(),
        )

        if m.is_primary:
            primary_found = True
            question.primary_chapter = ch
            question.primary_subject = subj
            question.primary_topic_id = m.topic_id
            question.chapter_key = ch.key
            question.subject_key = subj.key
            question.scheme = scheme
            question.level = scheme.level
            question.course = scheme.level.course

    if primary_found:
        question.save()


@transaction.atomic
def report_error(
    user_id: uuid.UUID,
    question_id: uuid.UUID,
    version_id: uuid.UUID,
    kind: str,
    message: str,
    proposed_option_ids: list[uuid.UUID],
) -> Report:
    """Student or reviewer reports an error in a question."""
    report, _ = Report.objects.update_or_create(
        question_id=question_id,
        reporter_user_id=user_id,
        kind=kind,
        status=Report.Status.OPEN,
        defaults={
            "version_id": version_id,
            "message": message[:1000],
            "proposed_option_ids": [str(o) for o in proposed_option_ids],
        },
    )

    open_reports = Report.objects.filter(question_id=question_id, status=Report.Status.OPEN).count()
    if open_reports >= 3:
        Question.objects.filter(id=question_id).update(needs_attention=True)
        emit_domain_event(
            "question_flagged",
            {
                "question_id": str(question_id),
                "report_count": open_reports,
                "kind": kind,
            },
            actor_id=user_id,
            key=f"flag:{question_id}",
        )

    return report


@transaction.atomic
def merge_duplicate(editor_id: uuid.UUID, loser_id: uuid.UUID, canonical_id: uuid.UUID) -> None:
    """Merges a duplicate question into canonical question."""
    loser = Question.objects.select_for_update().get(id=loser_id)
    canonical = Question.objects.get(id=canonical_id)

    loser.status = Question.Status.MERGED
    loser.merged_into = canonical
    loser.save(update_fields=["status", "merged_into", "updated_at"])

    AuditLog.objects.create(
        actor_id=editor_id,
        entity_type="question",
        entity_id=loser_id,
        action="merge_duplicate",
        before={"status": "active"},
        after={"status": "merged", "merged_into_id": str(canonical_id)},
    )


@transaction.atomic
def verify(
    editor_id: uuid.UUID,
    version_id: uuid.UUID,
    level: str,
    source_label: str,
    source_url: str | None,
) -> Verification:
    """Verifies a question version, granting the verified badge."""
    version = QuestionVersion.objects.get(id=version_id)
    now = timezone.now()

    # Revoke any prior unrevoked verification on this version
    Verification.objects.filter(version=version, revoked_at__isnull=True).update(revoked_at=now)

    verification = Verification.objects.create(
        question_id=version.question_id,
        version=version,
        verified_by=editor_id,
        level=level,
        source_label=source_label,
        source_url=source_url or "",
        verified_at=now,
    )

    Question.objects.filter(id=version.question_id).update(is_verified=True)
    return verification


@transaction.atomic
def take_down(admin_id: uuid.UUID, takedown_id: uuid.UUID, question_ids: Sequence[uuid.UUID]) -> None:
    """Takes down questions following a valid copyright or legal takedown."""
    td = Takedown.objects.get(id=takedown_id)
    for q_id in question_ids:
        Question.objects.filter(id=q_id).update(status=Question.Status.TAKEN_DOWN)
        TakedownItem.objects.get_or_create(takedown=td, question_id=q_id)
        emit_domain_event(
            "question_taken_down",
            {"question_id": str(q_id), "reason": "takedown", "session_count_open": 0},
            actor_id=admin_id,
            key=f"td:{q_id}",
        )


@transaction.atomic
def create_collection(
    actor_id: uuid.UUID | None,
    *,
    kind: str,
    title: str,
    visibility: str,
    slug: str | None = None,
    meta: dict | None = None,
) -> Collection:
    """Creates a custom or curated question collection."""
    return Collection.objects.create(
        owner_user_id=actor_id,
        kind=kind,
        title=title,
        visibility=visibility,
        slug=slug,
        meta=meta or {},
    )


@transaction.atomic
def set_collection_items(
    actor_id: uuid.UUID | None,
    collection_id: uuid.UUID,
    question_ids: Sequence[uuid.UUID],
) -> None:
    """Sets items in a collection with ordered gap positions."""
    coll = Collection.objects.select_for_update().get(id=collection_id)
    CollectionItem.objects.filter(collection=coll).delete()

    pos = 1024
    for q_id in question_ids:
        CollectionItem.objects.create(
            collection=coll,
            question_id=q_id,
            position=pos,
            added_by=actor_id,
        )
        pos += 1024

    coll.item_count = len(question_ids)
    coll.save(update_fields=["item_count", "updated_at"])


@transaction.atomic
def create_share_link(
    actor_id: uuid.UUID,
    *,
    collection_id: uuid.UUID | None = None,
    question_id: uuid.UUID | None = None,
    spec: dict | None = None,
    settings: dict | None = None,
    expires_at=None,
) -> ShareLink:
    """Creates a 22-character random capability share link."""
    token = uuid.uuid4().hex[:22]
    kind = "collection" if collection_id else ("question" if question_id else "filter")

    return ShareLink.objects.create(
        token=token,
        kind=kind,
        collection_id=collection_id,
        question_id=question_id,
        spec=spec,
        created_by=actor_id,
        settings=settings or {},
        expires_at=expires_at,
    )


def _labels_to_question(question: Question, payload: QuestionPayload) -> list[str]:
    """Copy source labels, difficulty and search fields from a payload onto the question row. Returns changed fields."""
    labels = payload.get("labels") or {}
    version_marks = Decimal(str(payload.get("marks", 1)))
    stem_md = payload.get("stem_md", "")
    opt_bodies = [o.get("body_md", "") for o in payload.get("options") or []]
    stem_head, search_text = extract_search_text(stem_md, opt_bodies, payload.get("explanation_md", ""))
    difficulty = labels.get("difficulty")
    if isinstance(difficulty, str):
        difficulty = {"easy": 1, "medium": 3, "hard": 4}.get(difficulty.lower())
    question.difficulty = difficulty or estimate_difficulty(
        kind=question.kind,
        stem=stem_md,
        options=opt_bodies,
        marks=version_marks,
        solution=payload.get("explanation_md", ""),
    )
    question.stem_head = stem_head
    question.search_text = search_text
    for attr in (
        "source_kind",
        "source_name",
        "source_url",
        "source_ref",
        "source_year",
        "source_term_code",
        "bloom",
        "nature",
    ):
        if attr in labels and labels[attr] is not None:
            setattr(question, attr, labels[attr])
    if "tags" in labels:
        question.tag_slugs = labels["tags"]
    return [
        "difficulty",
        "stem_head",
        "search_text",
        "source_kind",
        "source_name",
        "source_url",
        "source_ref",
        "source_year",
        "source_term_code",
        "bloom",
        "nature",
        "tag_slugs",
    ]


def _resolve_chapter(mapping: dict[str, Any]):
    from modules.syllabus.models import Chapter

    qs = Chapter.objects.select_related("subject__scheme__level__course").filter(
        subject__scheme__level__course__code=mapping.get("course", "cma"),
        subject__scheme__level__code=mapping.get("level", "final"),
        subject__key=mapping.get("subject_key", ""),
        key=mapping.get("chapter_key", ""),
    )
    return qs.order_by("-subject__scheme__status", "subject__scheme__code").first()


def _apply_import_mapping(
    actor_id: uuid.UUID, question: Question, payload: QuestionPayload, confidence: float | None
) -> list[str]:
    """
    Tag the question with its syllabus chapter from `payload["mapping"]`. Never overwrites a mapping an editor or author made:
    imports only write mappings that came from imports.
    """
    mappings = payload.get("mapping") or []
    if not mappings:
        return []
    if QuestionTopic.objects.filter(question=question, origin__in=["editor", "author"]).exists():
        return []
    warnings: list[str] = []
    resolved: list[MappingIn] = []
    for m in mappings:
        chapter = _resolve_chapter(dict(m))
        if chapter is None:
            warnings.append(
                f"chapter '{m.get('subject_key')}/{m.get('chapter_key')}' not found in the syllabus; question left unmapped"
            )
            continue
        sure = confidence is None or confidence >= 0.5
        resolved.append(
            MappingIn(
                chapter_id=chapter.id,
                is_primary=bool(m.get("primary", True)),
                origin="ingestion",
                confidence=Decimal(str(round(confidence, 2))) if confidence is not None else None,
                status="confirmed" if sure else "suggested",
            )
        )
    if resolved:
        set_mapping(actor_id, question.id, resolved)
    return warnings


def _link_duplicates(question: Question, version: QuestionVersion, actor_id: uuid.UUID) -> Question | None:
    """
    Exact copies (same stem, options and key, same kind and marks) are merged into the oldest existing question.
    Near copies (SimHash within 3 bits) and exact copies that differ in marks are recorded as suspected duplicates for
    an editor; they are never merged automatically. Returns the canonical question when a merge happened.
    """
    fp = Fingerprint.objects.filter(question=question).first()
    if fp is None:
        return None
    live = Q(question__status=Question.Status.ACTIVE, question__deleted_at__isnull=True)
    exact = (
        Fingerprint.objects.filter(live, fp_exact=fp.fp_exact, kind=fp.kind)
        .exclude(question=question)
        .select_related("question")
        .order_by("question__created_at", "question_id")
    )
    for other in exact:
        if other.question.marks == question.marks:
            merge_duplicate(actor_id, question.id, other.question_id)
            DuplicateLink.objects.get_or_create(
                question=other.question,
                other_question=question,
                defaults={
                    "kind": DuplicateLink.Kind.EXACT,
                    "score": Decimal("1.000"),
                    "state": DuplicateLink.State.MERGED,
                },
            )
            question.refresh_from_db()
            return other.question
        DuplicateLink.objects.get_or_create(
            question=other.question,
            other_question=question,
            defaults={"kind": DuplicateLink.Kind.VARIANT, "score": Decimal("1.000")},
        )
    near = (
        Fingerprint.objects.filter(live, kind=fp.kind)
        .filter(Q(b0=fp.b0) | Q(b1=fp.b1) | Q(b2=fp.b2) | Q(b3=fp.b3))
        .exclude(question=question)
        .exclude(fp_exact=fp.fp_exact)
        .select_related("question")[:50]
    )
    linked = 0
    for other in near:
        distance = hamming_distance(fp.simhash, other.simhash)
        if distance <= 3 and linked < 5:
            DuplicateLink.objects.get_or_create(
                question=other.question,
                other_question=question,
                defaults={"kind": DuplicateLink.Kind.NEAR, "score": Decimal(str(round(1 - distance / 64, 3)))},
            )
            linked += 1
    return None


@transaction.atomic
def upsert_from_source(
    *,
    origin_module: str,
    external_ref: str,
    payload: QuestionPayload,
    ownership: str,
    rights_status: str,
    actor_id: uuid.UUID | None,
    provenance: Any | None = None,
    auto_publish: bool = False,
    mapping_confidence: float | None = None,
) -> UpsertResult:
    """
    Idempotent upsert from an external source (MAT, mock papers, PYQ ingestion, CSV, the PDF seeds).
    Matches on (origin_module, external_ref). Returns outcome in {"created", "new_version", "unchanged"}.

    A new version carries everything the first one did (options, numeric key, rubric, fingerprint, difficulty, source
    labels) and keeps `Question.marks` equal to the version's marks, so the list page and the detail page cannot disagree.
    `payload["mapping"]` tags the syllabus chapter, but never over an editor's decision.
    """
    stem_md = payload.get("stem_md", "")
    options_data = payload.get("options") or []
    opt_bodies = [opt.get("body_md", "") for opt in options_data]
    marks = Decimal(str(payload.get("marks", 1)))

    content_hash = compute_content_hash(
        stem_md,
        options_data,
        payload.get("numeric_key"),
        payload.get("rubric"),
        marks,
    )
    actor = actor_id or uuid.uuid4()

    existing = Question.objects.filter(origin_module=origin_module, external_ref=external_ref).first()
    if not existing:
        q = create_draft(actor, payload)
        q.origin_module = origin_module
        q.external_ref = external_ref
        q.ownership = ownership
        q.rights_status = rights_status
        q.save()
        version = q.current_version or q.versions.first()
        warnings = _apply_import_mapping(actor, q, payload, mapping_confidence)
        duplicate_of = _link_duplicates(q, version, actor)
        if auto_publish and actor_id and duplicate_of is None:
            version = publish_version(actor_id, version.id, visibility="public")
        q.refresh_from_db()
        return UpsertResult(q, version, "created", duplicate_of=duplicate_of, warnings=warnings)

    current = existing.current_version or existing.live_version
    if current and current.content_hash == content_hash:
        if auto_publish and actor_id and existing.live_version_id is None and existing.status == Question.Status.ACTIVE:
            current = publish_version(actor_id, current.id, visibility="public")
            existing.refresh_from_db()
        return UpsertResult(existing, current, "unchanged")

    next_ver_no = (existing.versions.order_by("-version_no").values_list("version_no", flat=True).first() or 1) + 1
    neg_marks = payload.get("negative_marks")
    # Only one draft may exist per question: an import that changes an unpublished draft replaces it.
    existing.versions.filter(state=QuestionVersion.State.DRAFT).update(
        state=QuestionVersion.State.SUPERSEDED, superseded_at=timezone.now()
    )
    new_version = QuestionVersion.objects.create(
        question=existing,
        version_no=next_ver_no,
        state=QuestionVersion.State.DRAFT,
        change_kind=QuestionVersion.ChangeKind.IMPORT_UPDATE,
        authored_by=actor_id,
        stem_md=stem_md,
        stem_text=extract_search_text(stem_md, opt_bodies, payload.get("explanation_md", ""))[0],
        explanation_md=payload.get("explanation_md", ""),
        explanation_source=payload.get("explanation_source", ""),
        reference_labels=payload.get("reference_labels", []),
        marks=marks,
        negative_marks=Decimal(str(neg_marks)) if neg_marks is not None else None,
        multi_scoring=payload.get("multi_scoring", QuestionVersion.MultiScoring.ALL_OR_NOTHING),
        content_hash=content_hash,
    )
    _attach_version_children(existing, new_version, payload, actor)

    existing.current_version = new_version
    existing.marks = marks
    changed = _labels_to_question(existing, payload)
    existing.save(update_fields=["current_version", "marks", "updated_at", *changed])
    warnings = _apply_import_mapping(actor, existing, payload, mapping_confidence)

    if auto_publish and actor_id:
        new_version = publish_version(actor_id, new_version.id, visibility="public")
    existing.refresh_from_db()
    return UpsertResult(existing, new_version, "new_version", warnings=warnings)


@transaction.atomic
def delete_all_for_user(user_id: uuid.UUID) -> DeleteReport:
    """DPDP erasure for user-owned questionbank data."""
    # Anonymise public contributions
    anon_count = Question.objects.filter(owner_user_id=user_id, visibility=Question.Visibility.PUBLIC).update(
        owner_user_id=None, owner_anonymised=True
    )

    # Delete private questions and drafts
    user_questions = Question.objects.filter(owner_user_id=user_id)
    user_questions.update(current_version=None, live_version=None)
    QuestionVersion.objects.filter(question__in=user_questions).delete()
    deleted_q = user_questions.delete()[0]

    deleted_coll = Collection.objects.filter(owner_user_id=user_id).delete()[0]
    deleted_sf = SavedFilter.objects.filter(user_id=user_id).delete()[0]
    deleted_sl = ShareLink.objects.filter(created_by=user_id).delete()[0]

    return DeleteReport(
        questions_deleted=deleted_q,
        questions_anonymised=anon_count,
        collections_deleted=deleted_coll,
        saved_filters_deleted=deleted_sf,
        share_links_deleted=deleted_sl,
    )


def export_for_user(user_id: uuid.UUID) -> dict[str, Any]:
    """DPDP export of all user data in question bank."""
    questions = list(
        Question.objects.filter(owner_user_id=user_id).values("public_id", "kind", "visibility", "status", "created_at")
    )
    collections = list(
        Collection.objects.filter(owner_user_id=user_id).values("title", "kind", "visibility", "item_count")
    )
    return {
        "questions": questions,
        "collections": collections,
    }
