"""
The card kind registry (ERD 3.3). A kind is a `KindSpec`; the seven built-in kinds wrap `domain.cards` (the rules live
there, once) and a later release adds a kind with `register_card_kind` without touching the services.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from .domain import cards as domain
from .errors import UnknownKind

Fields = Mapping[str, object]


@dataclass(frozen=True)
class KindSpec:
    name: str
    fields: tuple[domain.FieldSpec, ...]
    validate: Callable[[Fields], list[domain.Issue]]
    render: Callable[[Fields, int], tuple[str, str]]
    ordinals: Callable[[Fields], list[int]]
    suggest: Callable[[str], float]
    icon_key: str
    example_fields: Mapping[str, str] = field(default_factory=dict)

    @property
    def markdown_fields(self) -> tuple[str, ...]:
        """The fields that hold Markdown (linted under the `card` profile); the others are plain one-line text."""
        return tuple(f.name for f in self.fields if not f.short)


_KINDS: dict[str, KindSpec] = {}


def register_card_kind(spec: KindSpec, *, replace: bool = False) -> None:
    if spec.name in _KINDS and not replace:
        raise ValueError(f"card kind {spec.name!r} is already registered")
    _KINDS[spec.name] = spec


def get_kind(name: str) -> KindSpec:
    try:
        return _KINDS[name]
    except KeyError:
        raise UnknownKind from None


def all_kinds() -> tuple[KindSpec, ...]:
    return tuple(_KINDS.values())


_ICONS = {
    "pointer": "pointer",
    "formula": "sigma",
    "section": "scale",
    "definition": "book-open",
    "mnemonic": "lightbulb",
    "case_law": "gavel",
    "cloze": "brackets",
}
_EXAMPLES: dict[str, dict[str, str]] = {
    "pointer": {
        "prompt_md": "When is ITC blocked under section 17(5)?",
        "answer_md": "Motor vehicles, food, club fees...",
    },
    "formula": {"name": "Break-even point", "expression_md": "$\\text{Fixed cost} / \\text{Contribution per unit}$"},
    "section": {"reference": "Section 17(5)", "prompt_md": "What is blocked?", "gist_md": "Blocked credits"},
    "definition": {"term": "Goodwill", "definition_md": "An intangible asset from a business combination."},
    "mnemonic": {"mnemonic": "PEMDAS", "expands_md": "Parentheses, Exponents, ..."},
    "case_law": {"case_name": "Salomon v. Salomon", "held_md": "A company is a separate legal person."},
    "cloze": {"text_md": "The {{c1::Companies Act, 2013}} replaced the {{c2::1956}} Act."},
}


def _builtin(name: str) -> KindSpec:
    def suggest(text: str) -> float:
        best, score = domain.suggest_kind(text)
        return score if best == name else 0.0

    return KindSpec(
        name=name,
        fields=domain.SPECS[name],
        validate=lambda fields, _n=name: domain.validate(_n, fields),
        render=lambda fields, ordinal, _n=name: domain.render(_n, fields, ordinal),
        ordinals=lambda fields, _n=name: domain.ordinals(_n, fields),
        suggest=suggest,
        icon_key=_ICONS[name],
        example_fields=_EXAMPLES[name],
    )


def register_builtin_kinds() -> None:
    for name in domain.KINDS:
        if name not in _KINDS:
            register_card_kind(_builtin(name))


register_builtin_kinds()
