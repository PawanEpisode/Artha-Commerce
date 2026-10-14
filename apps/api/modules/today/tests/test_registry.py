"""Provider registration is strict, because a bad provider should fail in CI, not inside a student's plan (ERD 3.2, 3.3)."""

import pytest

from modules.today import registry as reg
from modules.today.registry import KindSpec, ProviderResult, RegistrationError


def noop(request):
    return ProviderResult(candidates=())


def kind(name="revise_chapter", group="revise", slot="revision"):
    return KindSpec(name=name, group=group, slot=slot, icon="RefreshCw", default_est_minutes=15)


@pytest.fixture(autouse=True)
def _clean():
    reg.clear()
    yield
    reg.clear()


def test_a_provider_registers_and_is_listed_in_name_order():
    reg.register_task_provider("recall.due", noop, kinds=[kind("recall_cards", "revise", "recall")], label="Recall")
    reg.register_task_provider("coverage.revision", noop, kinds=[kind()], label="Revisions")
    assert [p.name for p in reg.providers()] == ["coverage.revision", "recall.due"]
    spec, k = reg.kind_spec("recall_cards")
    assert spec.name == "recall.due" and k.slot == "recall"
    assert reg.kind_spec("nope") is None


def test_registering_twice_replaces_it_because_ready_can_run_twice():
    reg.register_task_provider("coverage.revision", noop, kinds=[kind()], label="One")
    reg.register_task_provider("coverage.revision", noop, kinds=[kind()], label="Two")
    assert len(reg.providers()) == 1 and reg.get_provider("coverage.revision").label == "Two"


@pytest.mark.parametrize("name", ["", "revision", "Coverage.Revision", "coverage.", ".revision", "cover age.x", "1x.y"])
def test_provider_names_are_module_dot_what(name):
    with pytest.raises(RegistrationError):
        reg.register_task_provider(name, noop, kinds=[kind()], label="x")


def test_kinds_are_global_and_validated():
    reg.register_task_provider("coverage.revision", noop, kinds=[kind()], label="Revisions")
    with pytest.raises(RegistrationError, match="already belong"):
        reg.register_task_provider("other.thing", noop, kinds=[kind()], label="Clash")
    with pytest.raises(RegistrationError, match="no kinds"):
        reg.register_task_provider("other.empty", noop, kinds=[], label="x")
    with pytest.raises(RegistrationError, match="unknown group"):
        reg.register_task_provider("other.g", noop, kinds=[kind("k1", group="mystery")], label="x")
    with pytest.raises(RegistrationError, match="unknown slot"):
        reg.register_task_provider("other.s", noop, kinds=[kind("k2", slot="mystery")], label="x")
    with pytest.raises(RegistrationError, match="twice"):
        reg.register_task_provider("other.d", noop, kinds=[kind("k3"), kind("k3")], label="x")
    with pytest.raises(RegistrationError, match="lower_snake"):
        reg.register_task_provider("other.n", noop, kinds=[kind("Bad Name")], label="x")


def test_limits_on_timeout_and_candidates():
    with pytest.raises(RegistrationError, match="timeout"):
        reg.register_task_provider("a.b", noop, kinds=[kind()], label="x", timeout_ms=50)
    with pytest.raises(RegistrationError, match="timeout"):
        reg.register_task_provider("a.b", noop, kinds=[kind()], label="x", timeout_ms=5000)
    with pytest.raises(RegistrationError, match="max_candidates"):
        reg.register_task_provider("a.b", noop, kinds=[kind()], label="x", max_candidates=0)
    with pytest.raises(RegistrationError, match="label"):
        reg.register_task_provider("a.b", noop, kinds=[kind()], label=" ")


def test_defaults_are_the_contract_defaults():
    reg.register_task_provider("a.b", noop, kinds=[kind()], label="x")
    spec = reg.get_provider("a.b")
    assert (spec.timeout_ms, spec.max_candidates, spec.flag, spec.enabled_for) == (400, 20, None, None)


def test_completion_event_names_are_the_union_of_the_rules():
    rule = lambda name: reg.CompletionRule(event_name=name, match=lambda e, t: None)  # noqa: E731
    reg.register_task_provider(
        "coverage.revision", noop, kinds=[kind()], label="x", completion=[rule("coverage_event_recorded")]
    )
    reg.register_task_provider(
        "recall.due",
        noop,
        kinds=[kind("recall_cards", "revise", "recall")],
        label="y",
        completion=[rule("recall_session_completed"), rule("coverage_event_recorded")],
    )
    assert reg.completion_event_names() == ["coverage_event_recorded", "recall_session_completed"]


def test_manual_actions_are_found_by_key_and_not_duplicated():
    action = reg.ManualAction(
        key="coverage.log_revision", label="Also log this revision", default_on=True, run=lambda u, t: None
    )
    reg.register_task_provider("coverage.revision", noop, kinds=[kind()], label="x", manual_actions=[action])
    spec, found = reg.manual_action("coverage.log_revision")
    assert spec.name == "coverage.revision" and found.default_on is True
    assert reg.manual_action("missing.key") is None
    with pytest.raises(RegistrationError, match="manual action twice"):
        reg.register_task_provider("x.y", noop, kinds=[kind("k9")], label="x", manual_actions=[action, action])


def test_reasons_extend_but_never_silently_change():
    assert reg.reason_label("revision_overdue") == "A revision is overdue"
    assert reg.reason_label("unknown_code") == "Added by you"  # falls back to the custom label
    reg.register_reason("mock_due", label="A mock test is due")
    reg.register_reason("mock_due", label="A mock test is due")  # same label: fine
    assert reg.reasons()["mock_due"] == "A mock test is due"
    with pytest.raises(RegistrationError):
        reg.register_reason("mock_due", label="Something else")
    with pytest.raises(RegistrationError):
        reg.register_reason("Bad Code", label="x")


def test_the_registry_is_a_leaf_that_imports_no_django_and_no_models():
    import ast

    tree = ast.parse(open(reg.__file__).read())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0] if node.level == 0 else "." + node.module)
    assert "django" not in imported
    assert not [m for m in imported if "models" in m], imported
