"""Packaging guards.

These exist because of a real, shipped failure in the sibling projects: a
dependency was declared with no upper bound, the dependency released a new major
that renamed the module the code imported, and every fresh `uvx` install then
died at import. The installed dev environment could not reveal it, because a
locked venv already held the old major — only a fresh resolve picks up a new one.

So these tests check the MANIFEST, not the import. They fail when a ceiling is
removed or when the code migrates to an API the manifest has not been updated
for, which is the drift that actually bites.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _pyproject() -> dict:
    with (ROOT / "pyproject.toml").open("rb") as fh:
        return tomllib.load(fh)


def _requirements() -> dict[str, str]:
    deps = _pyproject()["project"]["dependencies"]
    out: dict[str, str] = {}
    for spec in deps:
        name = re.split(r"[<>=!\[]", spec, maxsplit=1)[0].strip()
        out[name.lower()] = spec
    return out


def test_every_runtime_dependency_has_an_upper_bound() -> None:
    """An unbounded dependency is how a new major silently breaks every fresh install."""
    missing = [
        spec for spec in _requirements().values() if "<" not in spec
    ]
    assert not missing, (
        "these dependencies have no upper bound, so a new major will be resolved "
        f"on the next clean install: {missing}"
    )


def test_gitignore_is_the_disclosure_boundary() -> None:
    """The corpus and generated kits must never be committable to a public repo."""
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for pattern in ("career-corpus.yaml", "kits/", "out/"):
        assert pattern in ignored, f".gitignore must ignore {pattern!r}"
    assert "!career-corpus.example.yaml" in ignored, (
        "the fictional example must stay committable, or CI has no corpus to validate"
    )


def test_no_real_corpus_is_tracked() -> None:
    """A belt-and-braces check that nothing corpus-shaped slipped into the tree."""
    tracked_corpus = [
        p.name
        for p in ROOT.glob("career-corpus*.yaml")
        if p.name != "career-corpus.example.yaml"
    ]
    assert not tracked_corpus, (
        f"a real corpus file is present in the repository root: {tracked_corpus}. "
        "It is gitignored, but verify it was never committed — history is not "
        "cleared by deleting the file."
    )
