"""`recall.legacy`: Recall's `core.today_port` tasks become Today candidates, with no change to Recall."""

import uuid
from dataclasses import dataclass, field

import pytest

from core import today_port
from modules.today import legacy_bridge, registry
from modules.today.domain import deeplinks
from modules.today.models import Task
from modules.today.registry import EnrollmentCtx, PaperCtx, PlanContext, TaskRequest

from .conftest import USER
from .helpers import TODAY

pytestmark = pytest.mark.django_db

SUBJECT = uuid.uuid4()


@dataclass(frozen=True)
class FakeTask:
    kind: str
    title: str
    count: int
    est_minutes: int = 0
    subject_key: str | None = None
    target: str = ""


@dataclass(frozen=True)
class FakeResult:
    key: str
    tasks: list = field(default_factory=list)


@pytest.fixture(autouse=True)
def _port():
    today_port.clear()
    yield
    today_port.clear()


def serve(*tasks, key="recall"):
    today_port.register_task_provider(key, lambda user_id, *, now: FakeResult(key, list(tasks)))


def request(papers=(("taxation", SUBJECT),), limit=5):
    ctx = PlanContext(
        user_id=uuid.UUID(USER),
        local_date=TODAY,
        tz="Asia/Kolkata",
        enrollment=EnrollmentCtx(uuid.uuid4(), uuid.uuid4(), "ca", "intermediate", None, None, None),
        days_to_exam=40,
        phase="consolidate",
        papers=tuple(PaperCtx(sid, key, key.title(), None, "theory", 0, None) for key, sid in papers),
        done_keys=frozenset(),
        suppressed_keys=frozenset(),
        budget_minutes=60,
        comeback=False,
        seed=1,
        is_preview=False,
    )
    return TaskRequest(ctx=ctx, limit=limit, deadline_ms=800)


def test_the_bridge_is_registered_with_the_kinds_recall_will_keep():
    spec = registry.get_provider("recall.legacy")
    assert {k.name for k in spec.kinds} == {
        "recall_cards",
        "forgotten_cards",
        "recheck",
        "cards_changed",
        "quick_revision",
    }
    assert registry.reason_label("deck_updated") == "Your decks changed"


def test_every_recall_task_becomes_a_valid_candidate():
    serve(
        FakeTask("recall_cards", "Recall: 12 cards due", 12, 6, target="review?source=today"),
        FakeTask("forgotten_cards", "Forgotten: top 5", 5, 3, target="forgotten"),
        FakeTask("recheck", "Re-check after amendment", 4, 2, target="cards?state=recheck"),
        FakeTask("cards_changed", "3 cards changed in your decks", 3, 2, target="decks"),
        FakeTask("quick_revision", "Quick revision: 20 cards today", 20, 10, target="quick"),
    )
    got = {c.kind: c for c in legacy_bridge.provide(request(limit=10)).candidates}
    assert set(got) == {k.name for k in legacy_bridge.KINDS}
    for c in got.values():
        assert deeplinks.valid_link(c.link.path, c.link.search), c.kind
        assert 1 <= c.est_minutes <= 90 and c.subject_id is None
        assert all(
            0 <= v <= 100 for v in (c.signals.urgency, c.signals.importance, c.signals.weakness, c.signals.freshness)
        )
    assert got["recall_cards"].link.path == "/app/recall/review" and dict(got["recall_cards"].link.search) == {
        "source": "today"
    }
    assert got["recheck"].link.path == "/app/recall/cards" and dict(got["recheck"].link.search) == {"state": "recheck"}
    assert got["recall_cards"].dedupe_key == "recall:due" and got["recall_cards"].target_value == 12
    assert got["recall_cards"].reason == "12 cards are due for recall" and got["cards_changed"].target_value is None


def test_a_task_with_a_paper_goes_to_that_paper_and_an_unknown_paper_is_skipped():
    serve(
        FakeTask("recall_cards", "Recall", 3, 2, subject_key="taxation", target="review"),
        FakeTask("forgotten_cards", "Forgotten", 2, 1, subject_key="old-paper", target="forgotten"),
    )
    [only] = legacy_bridge.provide(request()).candidates
    assert only.kind == "recall_cards" and only.subject_id == SUBJECT


def test_nothing_unusable_gets_through():
    serve(
        FakeTask("recall_cards", "No cards", 0),
        FakeTask("unknown_kind", "Mystery", 5),
        FakeTask("recall_cards", "  Spaced   out   title  ", 2, 0, target=""),
    )
    [c] = legacy_bridge.provide(request()).candidates
    assert c.title == "Spaced out title" and c.est_minutes == 1 and c.link.path == "/app/recall"


def test_another_ports_results_are_not_ours():
    serve(FakeTask("recall_cards", "Not recall", 4, 2), key="other")
    assert legacy_bridge.provide(request()).candidates == []


def test_a_failing_port_provider_never_breaks_the_bridge():
    def boom(user_id, *, now):
        raise RuntimeError("recall is down")

    today_port.register_task_provider("recall", boom)
    assert legacy_bridge.provide(request()).candidates == []


def test_the_limit_is_respected():
    serve(*[FakeTask("recall_cards", f"t{n}", 1, 1) for n in range(8)])
    assert len(legacy_bridge.provide(request(limit=3)).candidates) == 3


def test_recall_appears_in_a_real_plan_in_the_general_pool(api, enrolled):
    serve(FakeTask("recall_cards", "Recall: 12 cards due", 12, 6, target="review?source=today"))
    body = api.post("/today/open/").json_body
    recall = [t for t in body["tasks"] if t["kind"] == "recall_cards"]
    assert len(recall) == 1 and recall[0]["subject_id"] is None and recall[0]["link"]["path"] == "/app/recall/review"
    assert Task.objects.get(user_id=USER, kind="recall_cards").provider == "recall.legacy"
    assert any(tile["subject_id"] is None and recall[0]["id"] in tile["tasks"] for tile in body["tiles"])
