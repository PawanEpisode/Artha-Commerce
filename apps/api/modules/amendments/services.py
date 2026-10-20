from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from core.events import emit_domain_event

from .domain.card_key import generate_card_key
from .domain.checklist import validate_revision_release
from .errors import (
    ChangeNotFoundError,
    OpenRevisionExistsError,
    ReleaseChecklistFailedError,
    RevisionNotLiveError,
    RevisionNotOpenError,
)
from .models import (
    Amendment,
    AmendmentAuditLog,
    CardState,
    Change,
    ChangeMap,
    ChangeVersion,
    Revision,
    RevisionSubject,
    RevisionTerm,
)


def create_amendment_draft(
    course_id: uuid.UUID,
    level_id: uuid.UUID,
    title: str,
    doc_key: str,
    kind: str = Amendment.Kind.STATUTORY_UPDATE,
    issuer_label: str = "ICAI Board of Studies",
    short_title: str = "",
    landing_url: str = "",
    official_url: str = "",
    issued_on: date | None = None,
    actor_id: uuid.UUID | None = None,
) -> tuple[Amendment, Revision]:
    """
    Creates a new Amendment stream and its initial staged Revision (r1).
    """
    with transaction.atomic():
        slug_base = slugify(f"{kind}-{title}")[:140]
        # Ensure slug uniqueness
        unique_slug = slug_base
        counter = 1
        while Amendment.objects.filter(slug=unique_slug).exists():
            unique_slug = f"{slug_base[:130]}-{counter}"
            counter += 1

        amendment = Amendment.objects.create(
            course_id=course_id,
            level_id=level_id,
            doc_key=doc_key,
            kind=kind,
            title=title,
            short_title=short_title or title[:120],
            issuer_label=issuer_label,
            landing_url=landing_url,
            slug=unique_slug,
            created_by=actor_id,
        )

        revision = Revision.objects.create(
            amendment=amendment,
            revision_no=1,
            state=Revision.State.STAGED,
            revision_kind=Revision.Kind.INITIAL,
            issued_on=issued_on or timezone.now().date(),
            official_url=official_url,
        )

        amendment.current_revision = revision
        amendment.save(update_fields=["current_revision", "updated_at"])

        AmendmentAuditLog.objects.create(
            amendment=amendment,
            revision=revision,
            actor_id=actor_id,
            action="create_draft",
            metadata={"title": title, "doc_key": doc_key},
        )

        return amendment, revision


def set_revision_scope(
    revision_id: uuid.UUID,
    subjects: list[dict[str, Any]],
    terms: list[dict[str, Any]],
    actor_id: uuid.UUID | None = None,
) -> None:
    """
    Sets the paper scope and term applicability for an open revision.
    subjects: list of {"subject_id": UUID, "subject_key": str, "scheme_id": UUID, "level_id": UUID}
    terms: list of {"term_code": str, "applicability": str, "cutoff_date": date|None, "cutoff_note": str, "source_page": int|None}
    """
    with transaction.atomic():
        revision = Revision.objects.select_for_update().get(id=revision_id)
        if revision.state not in (Revision.State.STAGED, Revision.State.IN_REVIEW):
            raise RevisionNotOpenError(f"Cannot edit scope on revision in state '{revision.state}'.")

        # Replace subjects
        RevisionSubject.objects.filter(revision=revision).delete()
        for s in subjects:
            RevisionSubject.objects.create(
                revision=revision,
                subject_id=s["subject_id"],
                subject_key=s["subject_key"],
                scheme_id=s["scheme_id"],
                level_id=s["level_id"],
            )

        # Replace terms
        RevisionTerm.objects.filter(revision=revision).delete()
        for t in terms:
            RevisionTerm.objects.create(
                revision=revision,
                term_code=t["term_code"],
                exam_term_id=t.get("exam_term_id"),
                applicability=t.get("applicability", RevisionTerm.Applicability.APPLIES),
                cutoff_date=t.get("cutoff_date"),
                cutoff_note=t.get("cutoff_note", ""),
                source_page=t.get("source_page"),
                origin=t.get("origin", RevisionTerm.Origin.INSTITUTE_EXPLICIT),
                confirmed_by=actor_id,
                confirmed_at=timezone.now(),
            )

        AmendmentAuditLog.objects.create(
            amendment=revision.amendment,
            revision=revision,
            actor_id=actor_id,
            action="set_scope",
            metadata={"subjects_count": len(subjects), "terms_count": len(terms)},
        )


def stage_change_card(
    revision_id: uuid.UUID,
    title: str,
    provision_label: str,
    change_type: str,
    summary_new: str,
    law_key: str = "",
    summary_old: str = "",
    provision_keys: list[str] | None = None,
    effective_from_term_code: str = "",
    effective_text: str = "",
    materiality: str = ChangeVersion.Materiality.NORMAL,
    source_page: int | None = None,
    anchor: dict[str, Any] | None = None,
    evidence_quote: str = "",
    chapter_mappings: list[dict[str, Any]] | None = None,
    mappings: list[dict[str, Any]] | None = None,
    actor_id: uuid.UUID | None = None,
) -> ChangeVersion:
    """
    Adds or updates a ChangeVersion in an open revision.
    Finds or creates the parent Change stream using the deterministic card_key.
    """
    mappings_to_use = chapter_mappings if chapter_mappings is not None else mappings
    with transaction.atomic():
        revision = Revision.objects.select_for_update().get(id=revision_id)
        if revision.state not in (Revision.State.STAGED, Revision.State.IN_REVIEW):
            raise RevisionNotOpenError(f"Cannot add card to revision in state '{revision.state}'.")

        amendment = revision.amendment
        card_key = generate_card_key(
            law_key=law_key,
            provision_label=provision_label,
            change_type=change_type,
            title=title,
        )

        change, _ = Change.objects.get_or_create(
            amendment=amendment,
            card_key=card_key,
        )

        # Check if version exists in this revision
        cver = ChangeVersion.objects.filter(change=change, revision=revision).first()
        if cver:
            cver.title = title
            cver.provision_label = provision_label
            cver.change_type = change_type
            cver.summary_new = summary_new
            cver.summary_old = summary_old
            cver.law_key = law_key
            cver.provision_keys = provision_keys or []
            cver.effective_from_term_code = effective_from_term_code
            cver.materiality = materiality
            cver.source_page = source_page
            cver.anchor = anchor or {}
            cver.evidence_quote = evidence_quote
            cver.save()
        else:
            cver = ChangeVersion.objects.create(
                change=change,
                revision=revision,
                title=title,
                provision_label=provision_label,
                change_type=change_type,
                summary_new=summary_new,
                summary_old=summary_old,
                law_key=law_key,
                provision_keys=provision_keys or [],
                effective_from_term_code=effective_from_term_code,
                materiality=materiality,
                source_page=source_page,
                anchor=anchor or {},
                evidence_quote=evidence_quote,
            )

        change.current_version = cver
        change.save(update_fields=["current_version", "updated_at"])

        # Map to chapters/topics
        if mappings_to_use:
            ChangeMap.objects.filter(change_version=cver).delete()
            for m in mappings_to_use:
                ChangeMap.objects.create(
                    change_version=cver,
                    subject_id=m["subject_id"],
                    chapter_id=m.get("chapter_id"),
                    topic_id=m.get("topic_id"),
                    scheme_id=m.get("scheme_id"),
                    subject_key=m["subject_key"][:100],
                    chapter_key=(m.get("chapter_key") or "")[:120],
                    is_primary=m.get("is_primary", True),
                    status=m.get("status", ChangeMap.Status.CONFIRMED),
                    origin=m.get("origin", ChangeMap.Origin.MANUAL),
                )

        AmendmentAuditLog.objects.create(
            amendment=amendment,
            revision=revision,
            change=change,
            actor_id=actor_id,
            action="stage_card",
            metadata={"card_key": card_key, "provision_label": provision_label},
        )

        return cver


def release_revision(
    revision_id: uuid.UUID,
    actor_id: uuid.UUID | None = None,
) -> Revision:
    """
    Atomically releases a revision under row lock on the parent Amendment.
    Validates the release checklist, supersedes any prior live revision,
    marks cards as live, updates the Amendment, and emits domain events.
    """
    with transaction.atomic():
        revision = Revision.objects.select_for_update().get(id=revision_id)
        amendment = Amendment.objects.select_for_update().get(id=revision.amendment_id)

        # 1. Validate release checklist
        change_versions = list(revision.change_versions.select_related("change").prefetch_related("maps").all())
        cv_payloads = [
            {
                "title": cv.title,
                "provision_label": cv.provision_label,
                "change_type": cv.change_type,
                "has_mapping": cv.maps.exists(),
                "summary_new": cv.summary_new,
                "summary_old": cv.summary_old,
                "evidence_quote": cv.evidence_quote,
            }
            for cv in change_versions
        ]

        chk = validate_revision_release(
            state=revision.state,
            subject_count=revision.subjects.count(),
            term_count=revision.terms.count(),
            change_versions=cv_payloads,
            official_url=revision.official_url,
        )

        if not chk.is_valid:
            raise ReleaseChecklistFailedError(chk.errors)

        # 2. Supersede old live revision if present
        old_live = amendment.live_revision
        if old_live:
            old_live.state = Revision.State.SUPERSEDED
            old_live.save(update_fields=["state", "updated_at"])
            revision.supersedes = old_live

        # 3. Mark revision live
        now = timezone.now()
        revision.state = Revision.State.LIVE
        revision.released_by = actor_id
        revision.released_at = now
        revision.save(update_fields=["state", "released_by", "released_at", "supersedes", "updated_at"])

        # 4. Mark all change versions and changes live
        for cv in change_versions:
            cv.is_live = True
            cv.save(update_fields=["is_live"])
            cv.change.live_version = cv
            cv.change.status = Change.Status.ACTIVE
            cv.change.save(update_fields=["live_version", "status", "updated_at"])

        # 5. Update Amendment
        amendment.live_revision = revision
        amendment.current_revision = revision
        amendment.status = Amendment.Status.ACTIVE
        amendment.last_released_at = now
        if not amendment.first_released_at:
            amendment.first_released_at = now
        amendment.save(
            update_fields=[
                "live_revision",
                "current_revision",
                "status",
                "first_released_at",
                "last_released_at",
                "updated_at",
            ]
        )

        # 6. Build event payload
        high_cnt = sum(1 for cv in change_versions if cv.materiality == ChangeVersion.Materiality.HIGH)
        norm_cnt = sum(1 for cv in change_versions if cv.materiality == ChangeVersion.Materiality.NORMAL)
        low_cnt = sum(1 for cv in change_versions if cv.materiality == ChangeVersion.Materiality.LOW)

        chapter_map: dict[uuid.UUID, dict[str, Any]] = {}
        for cv in change_versions:
            if cv.materiality in (ChangeVersion.Materiality.HIGH, ChangeVersion.Materiality.NORMAL):
                for m in cv.maps.all():
                    if m.chapter_id:
                        if m.chapter_id not in chapter_map:
                            chapter_map[m.chapter_id] = {
                                "chapter_id": str(m.chapter_id),
                                "chapter_key": m.chapter_key,
                                "subject_key": m.subject_key,
                                "scheme_id": str(m.scheme_id)
                                if m.scheme_id
                                else str(revision.subjects.first().scheme_id),
                                "cards": 0,
                                "high": 0,
                                "normal": 0,
                                "updated": 1 if cv.revision_effect == ChangeVersion.RevisionEffect.UPDATED else 0,
                            }
                        chapter_map[m.chapter_id]["cards"] += 1
                        if cv.materiality == ChangeVersion.Materiality.HIGH:
                            chapter_map[m.chapter_id]["high"] += 1
                        else:
                            chapter_map[m.chapter_id]["normal"] += 1

        terms_data = [
            {
                "term_code": t.term_code,
                "applicability": t.applicability,
                "cutoff_date": t.cutoff_date.isoformat() if t.cutoff_date else None,
            }
            for t in revision.terms.all()
        ]

        subjects_data = [
            {
                "subject_id": str(s.subject_id),
                "subject_key": s.subject_key,
                "scheme_id": str(s.scheme_id),
            }
            for s in revision.subjects.all()
        ]

        payload = {
            "amendment_id": str(amendment.id),
            "revision_id": str(revision.id),
            "revision_no": revision.revision_no,
            "revision_kind": revision.revision_kind,
            "kind": amendment.kind,
            "course": amendment.course.code,
            "level": amendment.level.code,
            "level_id": str(amendment.level_id),
            "title": amendment.title,
            "issued_on": revision.issued_on.isoformat() if revision.issued_on else None,
            "terms": terms_data,
            "subjects": subjects_data,
            "counts": {
                "cards": len(change_versions),
                "high": high_cnt,
                "normal": norm_cnt,
                "low": low_cnt,
                "new": sum(1 for cv in change_versions if cv.revision_effect == ChangeVersion.RevisionEffect.NEW),
                "updated": sum(
                    1 for cv in change_versions if cv.revision_effect == ChangeVersion.RevisionEffect.UPDATED
                ),
                "removed": 0,
            },
            "chapters": list(chapter_map.values()),
            "paper_level_cards": [],
            "is_reissue": revision.revision_kind == Revision.Kind.REISSUE,
            "path": f"/amendments/documents/{amendment.slug}",
        }

        # 7. Emit domain event
        if revision.revision_kind == Revision.Kind.OUR_CORRECTION:
            payload["material"] = high_cnt > 0
            emit_domain_event("amendment_corrected", payload, actor_id=actor_id, key=str(revision.id))
        else:
            emit_domain_event("amendment_published", payload, actor_id=actor_id, key=str(revision.id))

        AmendmentAuditLog.objects.create(
            amendment=amendment,
            revision=revision,
            actor_id=actor_id,
            action="release",
            metadata={"cards_count": len(change_versions), "high_materiality": high_cnt},
        )

        return revision


def reissue_document(
    amendment_id: uuid.UUID,
    new_official_url: str,
    doc_sha256: str = "",
    issued_on: date | None = None,
    page_count: int | None = None,
    actor_id: uuid.UUID | None = None,
) -> Revision:
    """
    Creates a new staged Revision of an existing Amendment (e.g. when the Institute re-issues a PDF).
    Copies scope, terms, and cards from the previous live revision, marking cards as 'unchanged'.
    """
    with transaction.atomic():
        amendment = Amendment.objects.select_for_update().get(id=amendment_id)
        if not amendment.live_revision:
            raise RevisionNotLiveError("Cannot reissue an amendment that has no live revision.")

        # Ensure no open revision exists
        open_rev = amendment.revisions.filter(state__in=[Revision.State.STAGED, Revision.State.IN_REVIEW]).first()
        if open_rev:
            raise OpenRevisionExistsError(f"Open revision {open_rev.revision_no} already exists.")

        old_live = amendment.live_revision
        new_rev_no = old_live.revision_no + 1

        new_rev = Revision.objects.create(
            amendment=amendment,
            revision_no=new_rev_no,
            state=Revision.State.STAGED,
            revision_kind=Revision.Kind.REISSUE,
            issued_on=issued_on or timezone.now().date(),
            official_url=new_official_url,
            doc_sha256=doc_sha256,
            page_count=page_count,
        )

        # Copy subjects
        for s in old_live.subjects.all():
            RevisionSubject.objects.create(
                revision=new_rev,
                subject=s.subject,
                subject_key=s.subject_key,
                scheme=s.scheme,
                level=s.level,
            )

        # Copy terms
        for t in old_live.terms.all():
            RevisionTerm.objects.create(
                revision=new_rev,
                term_code=t.term_code,
                exam_term=t.exam_term,
                applicability=t.applicability,
                cutoff_date=t.cutoff_date,
                cutoff_note=t.cutoff_note,
                source_page=t.source_page,
                origin=t.origin,
            )

        # Copy change versions as UNCHANGED
        for old_cv in old_live.change_versions.all():
            new_cv = ChangeVersion.objects.create(
                change=old_cv.change,
                revision=new_rev,
                title=old_cv.title,
                provision_label=old_cv.provision_label,
                change_type=old_cv.change_type,
                summary_new=old_cv.summary_new,
                summary_old=old_cv.summary_old,
                law_key=old_cv.law_key,
                provision_keys=old_cv.provision_keys,
                effective_from_term_code=old_cv.effective_from_term_code,
                materiality=old_cv.materiality,
                source_page=old_cv.source_page,
                anchor=old_cv.anchor,
                evidence_quote=old_cv.evidence_quote,
                revision_effect=ChangeVersion.RevisionEffect.UNCHANGED,
            )
            # Copy mappings
            for m in old_cv.maps.all():
                ChangeMap.objects.create(
                    change_version=new_cv,
                    subject=m.subject,
                    chapter=m.chapter,
                    topic=m.topic,
                    scheme=m.scheme,
                    subject_key=m.subject_key,
                    chapter_key=m.chapter_key,
                    is_primary=m.is_primary,
                    status=m.status,
                    origin=m.origin,
                )

        amendment.current_revision = new_rev
        amendment.save(update_fields=["current_revision", "updated_at"])

        AmendmentAuditLog.objects.create(
            amendment=amendment,
            revision=new_rev,
            actor_id=actor_id,
            action="reissue",
            metadata={"new_revision_no": new_rev_no, "official_url": new_official_url},
        )

        return new_rev


def retract_revision(
    revision_id: uuid.UUID,
    reason: str = Revision.RetractionReason.INSTITUTE_WITHDREW,
    note: str = "",
    actor_id: uuid.UUID | None = None,
) -> Revision:
    """
    Retracts a live revision. If it was the only live revision, marks Amendment retracted.
    Emits amendment_retracted domain event.
    """
    with transaction.atomic():
        revision = Revision.objects.select_for_update().get(id=revision_id)
        amendment = Amendment.objects.select_for_update().get(id=revision.amendment_id)

        if revision.state != Revision.State.LIVE:
            raise RevisionNotLiveError(f"Cannot retract revision in state '{revision.state}'.")

        revision.state = Revision.State.RETRACTED
        revision.retraction_reason = reason
        revision.save(update_fields=["state", "retraction_reason", "updated_at"])

        if amendment.live_revision_id == revision.id:
            amendment.live_revision = None
            amendment.status = Amendment.Status.RETRACTED
            amendment.save(update_fields=["live_revision", "status", "updated_at"])

        chapter_ids = list(
            ChangeMap.objects.filter(change_version__revision=revision, chapter__isnull=False)
            .values_list("chapter_id", flat=True)
            .distinct()
        )
        subject_keys = list(revision.subjects.values_list("subject_key", flat=True).distinct())
        term_codes = list(revision.terms.values_list("term_code", flat=True).distinct())

        payload = {
            "amendment_id": str(amendment.id),
            "revision_id": str(revision.id),
            "reason": reason,
            "note": note,
            "chapter_ids": [str(cid) for cid in chapter_ids],
            "subject_keys": subject_keys,
            "term_codes": term_codes,
        }
        emit_domain_event("amendment_retracted", payload, actor_id=actor_id, key=str(revision.id))

        AmendmentAuditLog.objects.create(
            amendment=amendment,
            revision=revision,
            actor_id=actor_id,
            action="retract",
            metadata={"reason": reason, "note": note},
        )

        return revision


def delete_all_for_user(user_id: uuid.UUID) -> dict[str, int]:
    """
    DPDP central account erasure hook (audit AUD-004).
    Deletes all student card interaction states.
    """
    count, _ = CardState.objects.filter(user_id=user_id).delete()
    return {"card_states_deleted": count}


def export_for_user(user_id: uuid.UUID) -> dict[str, Any]:
    """
    DPDP central account export hook.
    Returns all card review and saved statuses for this student.
    """
    states = list(
        CardState.objects.filter(user_id=user_id)
        .select_related("change")
        .values("change__card_key", "change__public_id", "reviewed_at", "saved", "first_seen_at")
    )
    return {"amendments_card_states": states}


def set_card_state(
    user_id: uuid.UUID,
    public_id: str,
    *,
    reviewed: bool | None = None,
    saved: bool | None = None,
    client_id: uuid.UUID | None = None,
    client_ts: Any = None,
) -> CardState:
    """
    Sets the student interaction state for a change card (reviewed or saved).
    """
    change = Change.objects.filter(public_id=public_id).first()
    if not change:
        raise ChangeNotFoundError(f"Change card '{public_id}' not found.")

    with transaction.atomic():
        card_state, _ = CardState.objects.get_or_create(
            user_id=user_id,
            change=change,
            defaults={"first_seen_at": timezone.now()},
        )
        update_fields = ["updated_at"]

        if reviewed is not None:
            if reviewed:
                card_state.reviewed_at = timezone.now()
                card_state.reviewed_version = change.live_version
            else:
                card_state.reviewed_at = None
                card_state.reviewed_version = None
            update_fields.extend(["reviewed_at", "reviewed_version"])

        if saved is not None:
            card_state.saved = saved
            update_fields.append("saved")

        card_state.save(update_fields=update_fields)
        return card_state


def bulk_set_reviewed(
    user_id: uuid.UUID,
    public_ids: list[str],
    *,
    reviewed: bool,
    client_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """
    Bulk marks cards as reviewed or unreviewed.
    """
    changes = list(Change.objects.filter(public_id__in=public_ids))
    now = timezone.now()
    count = 0
    with transaction.atomic():
        for change in changes:
            card_state, _ = CardState.objects.get_or_create(
                user_id=user_id,
                change=change,
                defaults={"first_seen_at": now},
            )
            if reviewed:
                card_state.reviewed_at = now
                card_state.reviewed_version = change.live_version
            else:
                card_state.reviewed_at = None
                card_state.reviewed_version = None
            card_state.save(update_fields=["reviewed_at", "reviewed_version", "updated_at"])
            count += 1
    return {"updated": count, "reviewed": reviewed}


def file_report(
    user_id: uuid.UUID | None,
    anon_key: str | None,
    *,
    public_id: str,
    kind: str,
    message: str,
) -> dict[str, Any]:
    """
    Files a user report on a change card.
    """
    change = Change.objects.filter(public_id=public_id).first()
    if not change:
        raise ChangeNotFoundError(f"Change card '{public_id}' not found.")

    AmendmentAuditLog.objects.create(
        amendment=change.amendment,
        change=change,
        actor_id=user_id,
        action="report",
        metadata={
            "kind": kind,
            "message": message[:1000],
            "anon_key": anon_key,
        },
    )
    return {"status": "received", "public_id": public_id, "kind": kind}
