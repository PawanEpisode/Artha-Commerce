"""
Platform deck seed loader (`manage.py load_recall_seed`, FR-F15-44). A seed file is the editors' hand-over: decks, each with its
items, in our own wording. Loading is IDEMPOTENT: items are matched on `external_ref`, decks on `slug`, so a second run changes
nothing, and an edited item becomes a new DRAFT version (never a change to a live one). Decks load as drafts; `publish=True`
publishes them through the same atomic service the admin uses (the rights gate applies). A file marked `"sample": true` is for
tests and demos: it is never published unless the caller says so.

File shape (see `seed/_TEMPLATE.json`):
    {"schema": 1, "sample": false, "decks": [{"slug", "title", "description", "changelog",
        "scope": {"course", "level", "subject_key", "chapter_key"?}, "items": [{"ref", "kind", "importance", "fields",
        "tags"?, "reference_keys"?, "rights_status", "source_label"?, "source_url"?, "chapter_key"?, "change_kind"?}]}]}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from django.db import transaction

from core.errors import CodedError

from ..adapters import syllabus as syllabus_adapter
from ..models import ITEM_IMPORTANCES, ITEM_RIGHTS, RecallDeck, RecallDeckVersionItem, RecallItem
from . import decks as deck_service

SCHEMA = 1
CHANGE_KINDS = ("typo", "clarify", "substantive", "amendment")
ITEM_KEYS = {
    "ref", "kind", "importance", "fields", "tags", "reference_keys", "rights_status", "source_label", "source_url",
    "chapter_key", "change_kind",
}  # fmt: skip
DECK_KEYS = {"slug", "title", "description", "changelog", "scope", "items"}


@dataclass
class DeckResult:
    slug: str
    items_created: int = 0
    items_updated: int = 0  # a new draft version or changed metadata
    items_unchanged: int = 0
    draft_version_no: int | None = None
    published_version_no: int | None = None
    skipped: str = ""  # why a deck was not loaded or not published
    errors: list[str] = field(default_factory=list)


@dataclass
class SeedReport:
    sample: bool = False
    decks: list[DeckResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(d.errors for d in self.decks)


def problems_in(data) -> list[str]:
    """Structural problems of a seed file (everything the loader needs before it touches the database)."""
    out: list[str] = []
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        return [f"The file must be an object with schema {SCHEMA}."]
    decks = data.get("decks")
    if not isinstance(decks, list) or not decks:
        return ["`decks` must be a non-empty list."]
    refs: set[str] = set()
    slugs: set[str] = set()
    for d_index, deck in enumerate(decks):
        where = f"decks[{d_index}]"
        if not isinstance(deck, dict):
            out.append(f"{where} must be an object.")
            continue
        for key in sorted(set(deck) - DECK_KEYS):
            out.append(f"{where}: unknown key {key!r}.")
        slug = deck.get("slug")
        if not isinstance(slug, str) or not slug or slug in slugs:
            out.append(f"{where}: `slug` must be a unique non-empty string.")
        slugs.add(str(slug))
        if not isinstance(deck.get("title"), str) or not 1 <= len(deck["title"]) <= 80:
            out.append(f"{where}: `title` must be 1 to 80 characters.")
        scope = deck.get("scope")
        if not isinstance(scope, dict) or not all(
            isinstance(scope.get(k), str) for k in ("course", "level", "subject_key")
        ):
            out.append(f"{where}: `scope` needs course, level and subject_key.")
        items = deck.get("items")
        if not isinstance(items, list) or not items:
            out.append(f"{where}: `items` must be a non-empty list.")
            continue
        for i_index, item in enumerate(items):
            iwhere = f"{where}.items[{i_index}]"
            if not isinstance(item, dict):
                out.append(f"{iwhere} must be an object.")
                continue
            for key in sorted(set(item) - ITEM_KEYS):
                out.append(f"{iwhere}: unknown key {key!r}.")
            ref = item.get("ref")
            if not isinstance(ref, str) or not ref.strip() or ref in refs:
                out.append(f"{iwhere}: `ref` must be a unique non-empty string.")
            refs.add(str(ref))
            if not isinstance(item.get("kind"), str) or not isinstance(item.get("fields"), dict):
                out.append(f"{iwhere}: `kind` and `fields` are required.")
            if item.get("importance", "bullet") not in ITEM_IMPORTANCES:
                out.append(f"{iwhere}: bad importance.")
            if item.get("rights_status", "unknown") not in ITEM_RIGHTS:
                out.append(f"{iwhere}: bad rights_status.")
            if item.get("change_kind", "clarify") not in CHANGE_KINDS:
                out.append(f"{iwhere}: bad change_kind.")
    return out


def _chapter_for(scope: dict, chapter_key: str | None) -> UUID | None:
    if not chapter_key:
        return None
    return syllabus_adapter.chapter_id_by_keys(scope["course"], scope["level"], scope["subject_key"], chapter_key)


def _upsert_item(editor_id, spec: dict, scope: dict, deck_chapter_key: str | None, result: DeckResult) -> RecallItem:
    chapter_key = spec.get("chapter_key") or deck_chapter_key
    chapter_id = _chapter_for(scope, chapter_key)
    if chapter_key and chapter_id is None:
        raise ValueError(
            f"Chapter {chapter_key!r} was not found in {scope['course']}/{scope['level']}/{scope['subject_key']}."
        )
    meta = {
        "importance": spec.get("importance", "bullet"),
        "tags": deck_service.clean_tags(spec.get("tags", [])),
        "reference_keys": deck_service.clean_reference_keys(spec.get("reference_keys", [])),
        "rights_status": spec.get("rights_status", "unknown"),
        "source_label": (spec.get("source_label") or "")[:200],
        "source_url": spec.get("source_url") or None,
    }
    item = RecallItem.objects.filter(external_ref=spec["ref"]).first()
    if item is None:
        item = deck_service.create_platform_item(
            editor_id, kind=spec["kind"], fields=spec["fields"], chapter_id=chapter_id, external_ref=spec["ref"], **meta
        )
        result.items_created += 1
        return item
    if item.ownership != "platform" or item.kind != spec["kind"]:
        raise ValueError(f"{spec['ref']}: an existing item of another ownership or kind has this reference.")
    changed = False
    for key, value in meta.items():
        if getattr(item, key) != value:
            setattr(item, key, value)
            changed = True
    if chapter_id != item.chapter_id:
        link = syllabus_adapter.link_columns(chapter_id)
        for key, value in link.items():
            setattr(item, key, value)
        changed = True
    if changed:
        item.save()
    before = item.current_version_id
    version = deck_service.new_item_version(
        editor_id, item, spec["fields"], change_kind=spec.get("change_kind", "clarify"), note="Seed load"
    )
    changed = changed or version.pk != before
    item.refresh_from_db()
    if changed:
        result.items_updated += 1
    else:
        result.items_unchanged += 1
    return item


def _same_as_live(deck: RecallDeck, items: list[RecallItem]) -> bool:
    if not deck.live_version_id:
        return False
    live = list(
        RecallDeckVersionItem.objects.filter(deck_version_id=deck.live_version_id)
        .order_by("position", "item_id")
        .values_list("item_id", "item_version_id")
    )
    want = [(i.pk, i.current_version_id) for i in items]
    return live == want


def load_seed(
    data: dict, *, publish: bool = False, publisher_id=None, include_sample: bool = False, editor_id=None
) -> SeedReport:
    """Load every deck of a parsed seed file; one deck's failure never stops the others (each deck is one transaction)."""
    bad = problems_in(data)
    if bad:
        report = SeedReport(sample=bool(isinstance(data, dict) and data.get("sample")))
        report.decks.append(DeckResult("(file)", errors=bad))
        return report
    sample = bool(data.get("sample"))
    report = SeedReport(sample=sample)
    for deck_spec in data["decks"]:
        result = DeckResult(deck_spec["slug"])
        report.decks.append(result)
        try:
            with transaction.atomic():
                _load_deck(deck_spec, result, editor_id)
        except ValueError as exc:
            result.errors.append(str(exc))
            continue
        except CodedError as exc:
            issues = (getattr(exc, "extra", None) or {}).get("errors", [])
            result.errors.append("; ".join(f"{e.get('field')}: {e.get('message')}" for e in issues) or str(exc.detail))
            continue
        if publish and result.draft_version_no is not None:
            if sample and not include_sample:
                result.skipped = "sample file: not published (pass include_sample to override)"
                continue
            _publish(deck_spec, result, publisher_id)
    return report


def _load_deck(spec: dict, result: DeckResult, editor_id) -> None:
    scope = spec["scope"]
    chapter_key = scope.get("chapter_key")
    chapter_id = _chapter_for(scope, chapter_key)
    if chapter_key and chapter_id is None:
        raise ValueError(
            f"Chapter {chapter_key!r} was not found in {scope['course']}/{scope['level']}/{scope['subject_key']}."
        )
    items = [_upsert_item(editor_id, s, scope, chapter_key, result) for s in spec["items"]]
    deck = RecallDeck.objects.filter(slug=spec["slug"]).first()
    link = syllabus_adapter.link_columns(chapter_id) if chapter_id else None
    if deck is None:
        deck = RecallDeck.objects.create(kind="platform", slug=spec["slug"], title=spec["title"])
    elif deck.kind != "platform":
        raise ValueError(f"{spec['slug']}: this slug belongs to a student's deck.")
    deck.title, deck.description = spec["title"], spec.get("description", "")[:500]
    if link:
        deck.course_id, deck.level_id, deck.subject_id, deck.chapter_id = (
            link["course_id"], link["level_id"], link["subject_id"], link["chapter_id"],
        )  # fmt: skip
    deck.save()
    if _same_as_live(deck, items):
        return
    draft = deck_service.start_draft_version(editor_id, deck, from_live=False)
    deck_service.set_draft_rows(draft, [(item, None) for item in items])
    if spec.get("changelog"):
        draft.changelog_md = spec["changelog"]
        draft.save(update_fields=["changelog_md", "updated_at"])
    result.draft_version_no = draft.version_no


def _publish(spec: dict, result: DeckResult, publisher_id) -> None:
    deck = RecallDeck.objects.get(slug=spec["slug"])
    try:
        version = deck_service.publish_deck_version(
            publisher_id, deck.pk, deck.draft_version_id, changelog_md=spec.get("changelog", "")
        )
        result.published_version_no = version.version_no
    except CodedError as exc:
        ids = (getattr(exc, "extra", None) or {}).get("item_ids")
        refs = sorted(RecallItem.objects.filter(pk__in=ids or []).values_list("external_ref", flat=True))
        result.errors.append(
            f"not published: {exc.detail}" + (f" Items: {', '.join(r or '?' for r in refs)}." if refs else "")
        )
