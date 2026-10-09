"""
Platform decks, the editor side (PRD 4.5, ERD 3.6). The Django admin and `load_recall_seed` both go through these functions, so
the rules (kind validation, version numbers, the rights gate, atomic publish) exist once.

Items and deck versions are immutable once live. An edit is a new draft `RecallItemVersion`; a deck version is a snapshot of
exact item versions. `publish_deck_version` makes a snapshot live in ONE transaction: it promotes the draft item versions,
supersedes what they replace, computes `change_vs_prev`, supersedes the previous live deck version and writes the audit row.
If anything fails nothing changes and the previous live version keeps being served. Students never see a draft.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from core import events

from .. import registry
from ..adapters import syllabus as syllabus_adapter
from ..domain import cards as domain_cards
from ..domain import decks as domain
from ..errors import (
    DeckNotFound,
    EmptyDeckVersion,
    ItemNotPublishable,
    RightsBlocked,
    VersionNotPublishable,
)
from ..models import (
    RecallAuditLog,
    RecallDeck,
    RecallDeckVersion,
    RecallDeckVersionItem,
    RecallItem,
    RecallItemVersion,
)
from .cards import (
    SEARCH_TEXT_MAX,
    check_fields,
    clean_fields,
    clean_reference_keys,
    clean_tags,
    content_hash,
    plain_text_of,
)

DECK_PUBLISHED = "recall_deck_published"


def _faces(item: RecallItem, version: RecallItemVersion) -> int:
    spec = registry.get_kind(item.kind)
    return len(spec.ordinals({k: v for k, v in version.fields.items() if k != "v"}))


# ------------------------------------------------------------------------------------------------ items


def create_platform_item(
    editor_id,
    *,
    kind: str,
    fields: dict,
    importance: str = "bullet",
    chapter_id: UUID | None = None,
    topic_id: UUID | None = None,
    tags: Sequence = (),
    reference_keys: Sequence = (),
    rights_status: str = "unknown",
    source_label: str = "",
    source_url: str | None = None,
    external_ref: str | None = None,
) -> RecallItem:
    """A platform item with its first DRAFT version. It is not served until a deck version containing it is published."""
    from .cards import clean_importance

    spec = registry.get_kind(kind)
    clean = clean_fields(spec, fields)
    check_fields(spec, clean)
    link = syllabus_adapter.link_columns(chapter_id, topic_id)
    with transaction.atomic():
        item = RecallItem.objects.create(
            kind=kind,
            ownership="platform",
            owner_user_id=None,
            origin="editor",
            status="active",
            importance=clean_importance(importance),
            rights_status=rights_status,
            source_label=source_label[:200],
            source_url=source_url or None,
            tags=clean_tags(tags),
            reference_keys=clean_reference_keys(reference_keys),
            fingerprint=domain_cards.fingerprint(kind, clean),
            search_text=plain_text_of(spec, clean)[:SEARCH_TEXT_MAX],
            external_ref=external_ref,
            created_by=editor_id,
            **link,
        )
        version = _insert_version(item, spec, clean, version_no=1, change_kind="create", note="", editor_id=editor_id)
        item.current_version = version
        item.save(update_fields=["current_version", "updated_at"])
    return item


def _insert_version(item, spec, clean, *, version_no, change_kind, note, editor_id) -> RecallItemVersion:
    return RecallItemVersion.objects.create(
        item=item,
        version_no=version_no,
        state="draft",
        change_kind=change_kind,
        change_note=note,
        fields={"v": domain_cards.FIELDS_VERSION, **clean},
        fields_schema=domain_cards.FIELDS_VERSION,
        cloze_count=len(spec.ordinals(clean)) if item.kind == "cloze" else 0,
        content_hash=content_hash(clean),
        plain_text=plain_text_of(spec, clean),
        authored_by=editor_id,
    )


def new_item_version(
    editor_id, item: RecallItem, fields: dict, *, change_kind: str, note: str = ""
) -> RecallItemVersion:
    """
    A new DRAFT version of a platform item (an edit never touches the live one). Refused when the text is the same as the
    newest version, so a repeated seed load makes no versions.
    """
    if item.ownership != "platform":
        raise ItemNotPublishable(extra={"item_ids": [str(item.id)]})
    spec = registry.get_kind(item.kind)
    clean = clean_fields(spec, fields)
    check_fields(spec, clean)
    with transaction.atomic():
        locked = RecallItem.objects.select_for_update().get(pk=item.pk)
        latest = locked.versions.order_by("-version_no").first()
        if latest is not None and latest.content_hash == content_hash(clean):
            return latest
        drafts = locked.versions.filter(state="draft")
        if drafts.exists():  # one draft at a time: editing replaces it, so a deck never offers two
            draft = drafts.get()
            draft.fields = {"v": domain_cards.FIELDS_VERSION, **clean}
            draft.content_hash = content_hash(clean)
            draft.plain_text = plain_text_of(spec, clean)
            draft.cloze_count = len(spec.ordinals(clean)) if item.kind == "cloze" else 0
            draft.change_kind, draft.change_note = change_kind, note
            draft.authored_by = editor_id
            draft.save()
            return draft
        number = (latest.version_no if latest else 0) + 1
        version = _insert_version(
            locked, spec, clean, version_no=number, change_kind=change_kind, note=note, editor_id=editor_id
        )
        locked.current_version = version
        locked.save(update_fields=["current_version", "updated_at"])
        return version


# ------------------------------------------------------------------------------------------------ decks


def get_platform_deck(deck_id) -> RecallDeck:
    deck = RecallDeck.objects.filter(pk=deck_id, kind="platform").first()
    if deck is None:
        raise DeckNotFound
    return deck


def start_draft_version(editor_id, deck: RecallDeck, *, from_live: bool = True) -> RecallDeckVersion:
    """
    The draft deck version of a deck: the existing one, or a new one numbered after the highest version. A new draft starts
    as a copy of the live snapshot (each row pointing at the item's newest version), so editors change what differs.
    """
    with transaction.atomic():
        locked = RecallDeck.objects.select_for_update().get(pk=deck.pk)
        existing = locked.versions.filter(state__in=("draft", "in_review")).order_by("-version_no").first()
        if existing is not None:
            return existing
        top = locked.versions.aggregate(m=Max("version_no"))["m"] or 0
        draft = RecallDeckVersion.objects.create(deck=locked, version_no=top + 1, state="draft")
        if from_live and locked.live_version_id:
            rows = RecallDeckVersionItem.objects.filter(deck_version_id=locked.live_version_id).select_related("item")
            RecallDeckVersionItem.objects.bulk_create(
                RecallDeckVersionItem(
                    deck_version=draft,
                    item_id=r.item_id,
                    item_version_id=r.item.current_version_id or r.item_version_id,
                    position=r.position,
                )
                for r in rows
            )
        locked.draft_version = draft
        locked.save(update_fields=["draft_version", "updated_at"])
        return draft


def set_draft_rows(version: RecallDeckVersion, entries: Sequence[tuple[RecallItem, RecallItemVersion | None]]) -> None:
    """Replace the rows of a DRAFT deck version with these items, in this order (an item version of None means its newest)."""
    if version.state not in ("draft", "in_review"):
        raise VersionNotPublishable
    with transaction.atomic():
        RecallDeckVersionItem.objects.filter(deck_version=version).delete()
        newest = dict(
            RecallItem.objects.filter(id__in=[item.id for item, _ in entries]).values_list("id", "current_version_id")
        )
        RecallDeckVersionItem.objects.bulk_create(
            RecallDeckVersionItem(
                deck_version=version,
                item=item,
                item_version_id=chosen.id if chosen else newest[item.id],
                position=position,
            )
            for position, (item, chosen) in enumerate(entries)
        )


# ----------------------------------------------------------------------------------------------- publish


@dataclass(frozen=True)
class _Plan:
    rows: list[RecallDeckVersionItem]
    snapshot: list[domain.SnapshotRow]
    previous: dict[str, str] | None


def _plan(deck: RecallDeck, version: RecallDeckVersion) -> _Plan:
    rows = list(
        RecallDeckVersionItem.objects.filter(deck_version=version)
        .select_related("item", "item_version")
        .order_by("position", "item_id")
    )
    if not rows:
        raise EmptyDeckVersion
    bad = [
        str(r.item_id)
        for r in rows
        if r.item.ownership != "platform"
        or r.item.status != "active"
        or r.item.deleted_at is not None
        or r.item_version.item_id != r.item_id
        or r.item_version.state not in ("draft", "live")
    ]
    if bad:
        raise ItemNotPublishable(extra={"item_ids": sorted(bad)})
    blocked = domain.rights_blockers({str(r.item_id): r.item.rights_status for r in rows})
    if blocked:
        raise RightsBlocked(extra={"item_ids": blocked})
    snapshot = [
        domain.SnapshotRow(
            item_id=str(r.item_id),
            item_version_id=str(r.item_version_id),
            importance=r.item.importance,
            faces=_faces(r.item, r.item_version),
            change_kind=r.item_version.change_kind,
        )
        for r in rows
    ]
    previous = None
    if deck.live_version_id:
        previous = {
            str(i): str(v)
            for i, v in RecallDeckVersionItem.objects.filter(deck_version_id=deck.live_version_id).values_list(
                "item_id", "item_version_id"
            )
        }
    return _Plan(rows, snapshot, previous)


def publish_deck_version(editor_id, deck_id, version_id, *, changelog_md: str = "") -> RecallDeckVersion:
    """
    Make a draft deck version live, atomically (FR-F15-45). Needs the scope `recall.deck.publish`, checked by the caller
    (admin or API). Raises 404 `deck_not_found`, 409 `version_not_publishable`, 422 `empty_deck_version`,
    `item_not_publishable` or `rights_blocked` (item ids only), before anything is written.
    """
    now = timezone.now()
    with transaction.atomic():
        deck = RecallDeck.objects.select_for_update().filter(pk=deck_id, kind="platform").first()
        if deck is None:
            raise DeckNotFound
        version = RecallDeckVersion.objects.select_for_update().filter(pk=version_id, deck=deck).first()
        previous_live = (
            RecallDeckVersion.objects.filter(pk=deck.live_version_id).first() if deck.live_version_id else None
        )
        if (
            version is None
            or version.state not in ("draft", "in_review")
            or (previous_live is not None and version.version_no <= previous_live.version_no)
        ):
            raise VersionNotPublishable
        plan = _plan(deck, version)

        # Promote the draft item versions: what they replace is superseded first (one live version per item).
        drafts = [r for r in plan.rows if r.item_version.state == "draft"]
        draft_item_ids = [r.item_id for r in drafts]
        RecallItemVersion.objects.filter(item_id__in=draft_item_ids, state="live").update(
            state="superseded", superseded_at=now, updated_at=now
        )
        for r in drafts:
            r.item_version.state, r.item_version.live_at = "live", now
            r.item_version.save(update_fields=["state", "live_at", "updated_at"])
            spec = registry.get_kind(r.item.kind)
            fields = {k: v for k, v in r.item_version.fields.items() if k != "v"}
            r.item.live_version = r.item.current_version = r.item_version
            r.item.fingerprint = domain_cards.fingerprint(r.item.kind, fields)
            r.item.search_text = plain_text_of(spec, fields)[:SEARCH_TEXT_MAX]
            r.item.save(update_fields=["live_version", "current_version", "fingerprint", "search_text", "updated_at"])

        by_change: dict[str, list] = {}
        for r, snap in zip(plan.rows, plan.snapshot, strict=True):
            by_change.setdefault(domain.change_vs_prev(plan.previous, snap), []).append(r.item_id)
        for change, item_ids in by_change.items():
            RecallDeckVersionItem.objects.filter(deck_version=version, item_id__in=item_ids).update(
                change_vs_prev=change
            )

        summary = domain.diff_summary(plan.previous, plan.snapshot)
        tiers = domain.tier_counts(plan.snapshot)
        if previous_live is not None:
            previous_live.state = "superseded"
            previous_live.save(update_fields=["state", "updated_at"])
        version.state, version.published_by, version.published_at = "live", editor_id, now
        version.changelog_md = changelog_md or version.changelog_md
        version.item_count, version.tier_counts, version.diff_summary = len(plan.rows), tiers, summary
        version.save()
        deck.live_version = version
        if deck.draft_version_id == version.id:
            deck.draft_version = None
        deck.save(update_fields=["live_version", "draft_version", "updated_at"])
        RecallAuditLog.objects.create(
            actor_id=editor_id,
            action="deck_publish",
            target_kind="deck",
            target_id=str(deck.id),
            detail={"v": 1, "version_no": version.version_no, "items": len(plan.rows), "diff": summary},
        )
        chapter_ids = sorted({str(r.item.chapter_id) for r in plan.rows if r.item.chapter_id})
        payload = {
            "deck_id": str(deck.id),
            "version_no": version.version_no,
            "diff_summary": summary,
            "chapter_ids": chapter_ids,
            "substantive_count": summary["substantive"] + summary["amendment"],
        }
        transaction.on_commit(lambda: events.emit(DECK_PUBLISHED, **payload))
    return version


# ------------------------------------------------------------------------------------------ helpers


def validate_fields(kind: str, fields: dict) -> dict:
    """The cleaned fields of an item version, or `InvalidFields` / `UnknownKind` (the admin turns them into form errors)."""
    spec = registry.get_kind(kind)
    clean = clean_fields(spec, fields)
    check_fields(spec, clean)
    return clean


def resolve_item_refs(refs: Sequence[str]) -> tuple[list[RecallItem], list[str]]:
    """
    Platform items by `external_ref` or by id, in the order given, plus the references nothing matched. Used by the deck version
    editor (a list of references, one per line) so an editor never has to pick one item among thousands in a drop-down.
    """
    found: list[RecallItem] = []
    missing: list[str] = []
    for ref in refs:
        ref = ref.strip()
        if not ref:
            continue
        item = RecallItem.objects.filter(ownership="platform", external_ref=ref).first()
        if item is None:
            try:
                item = RecallItem.objects.filter(ownership="platform", pk=UUID(ref)).first()
            except ValueError:
                item = None
        if item is None:
            missing.append(ref)
        else:
            found.append(item)
    return found, missing
