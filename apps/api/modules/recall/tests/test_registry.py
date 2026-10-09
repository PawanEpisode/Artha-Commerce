import pytest

from modules.recall import registry
from modules.recall.domain import cards as domain
from modules.recall.errors import UnknownKind

pytestmark = pytest.mark.django_db


def test_all_seven_builtin_kinds_are_registered_and_wrap_the_domain():
    assert tuple(k.name for k in registry.all_kinds()) == domain.KINDS
    for spec in registry.all_kinds():
        assert spec.fields == domain.SPECS[spec.name]
        assert spec.validate(spec.example_fields) == [], spec.name
        front, back = spec.render(spec.example_fields, spec.ordinals(spec.example_fields)[0])
        assert front and back and spec.icon_key


def test_an_unknown_kind_is_a_coded_422():
    with pytest.raises(UnknownKind) as caught:
        registry.get_kind("riddle")
    assert caught.value.status_code == 422 and caught.value.default_code == "unknown_kind"


def test_a_kind_can_be_registered_once_and_replaced_on_purpose():
    spec = registry.get_kind("pointer")
    custom = registry.KindSpec(**{**spec.__dict__, "name": "riddle", "icon_key": "x"})
    registry.register_card_kind(custom)
    try:
        assert registry.get_kind("riddle") is custom
        with pytest.raises(ValueError):
            registry.register_card_kind(custom)
        registry.register_card_kind(custom, replace=True)
    finally:
        registry._KINDS.pop("riddle")


def test_markdown_fields_exclude_the_short_ones():
    assert registry.get_kind("formula").markdown_fields == ("expression_md", "variables_md", "when_md")
    assert registry.get_kind("cloze").markdown_fields == ("text_md",)


def test_suggest_scores_only_the_winning_kind():
    text = "Section 17(5) blocks credit"
    assert registry.get_kind("section").suggest(text) > 0
    assert registry.get_kind("formula").suggest(text) == 0
