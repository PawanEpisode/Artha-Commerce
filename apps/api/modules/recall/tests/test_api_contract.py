"""
`docs/F-15-API-CONTRACT.md` and the URL conf must agree: every path the contract documents resolves to a recall view, and every
recall route is documented. Paths in the contract are written in backticks, `METHOD recall/...` with `{id}` for a uuid.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from django.urls import Resolver404, get_resolver, resolve

DOC = Path(__file__).resolve().parents[5] / "docs" / "F-15-API-CONTRACT.md"
TOKEN = re.compile(r"`([^`]+)`")


def documented() -> set[str]:
    """
    Every documented path. A table row's first cell lists them in backticks: `METHOD recall/...` and, for siblings,
    just `other/` (relative to the folder of the first path). Every `{...}` is a uuid when the path is resolved.
    """
    found: set[str] = set()
    for line in DOC.read_text().splitlines():
        if not line.startswith("| `"):
            continue
        cell = line.replace("\\|", "\x00").split("|")[1]
        folder = ""
        for token in TOKEN.findall(cell):
            word = token.replace("\x00", "|").split(" ")[-1]
            if word.startswith("recall/"):
                found.add(word)
                folder = word.rstrip("/").rsplit("/", 1)[0] + "/"
            elif folder and re.fullmatch(r"[a-z\-]+/", word):
                found.add(folder + word)
    return found


def concrete(path: str) -> str:
    return "/api/v1/" + re.sub(r"\{[a-z_]+\}", lambda _: str(uuid.uuid4()), path)


def recall_routes() -> set[str]:
    out: set[str] = set()

    def walk(patterns, prefix=""):
        for p in patterns:
            here = prefix + str(p.pattern)
            if hasattr(p, "url_patterns"):
                walk(p.url_patterns, here)
            elif here.startswith("api/v1/recall/"):
                out.add(here[len("api/v1/") :])

    walk(get_resolver().url_patterns)
    assert out, "no recall route found under api/v1/"
    return out


def test_every_documented_path_resolves_to_a_recall_view():
    paths = documented()
    assert len(paths) >= 35, "the contract tables were not parsed"
    missing = []
    for path in sorted(paths):
        try:
            match = resolve(concrete(path))
        except Resolver404:
            missing.append(path)
            continue
        if "recall" not in match.func.__module__:
            missing.append(path)
    assert missing == [], f"documented in F-15-API-CONTRACT.md but not in the URL conf: {missing}"


def test_every_recall_route_is_documented():
    normalise = lambda p: re.sub(r"<uuid:[a-z_]+>|\{[a-z_]+\}", "{}", p)  # noqa: E731
    documented_shapes = {normalise(p) for p in documented()}
    undocumented = sorted(r for r in recall_routes() if normalise(r) not in documented_shapes)
    assert undocumented == [], f"in the URL conf but not in F-15-API-CONTRACT.md: {undocumented}"
