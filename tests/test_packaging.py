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
import subprocess
import tomllib
from pathlib import Path

import pytest

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


def test_the_readme_test_count_badge_is_current() -> None:
    """A hand-written number on a badge is a metric with nobody checking it.

    That is precisely the failure this project refuses to allow on a CV, so it
    is not allowed on its own README either. The badge is static because there
    is no free service that counts tests; it is honest because this asserts it.
    """
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    match = re.search(r"tests-(\d+)%20passing", readme)
    assert match, "the README must carry a tests-N%20passing badge"
    claimed = int(match.group(1))

    actual = 0
    for path in (ROOT / "tests").glob("test_*.py"):
        actual += len(re.findall(r"^def test_", path.read_text(encoding="utf-8"), re.MULTILINE))

    assert claimed == actual, (
        f"the README badge claims {claimed} tests, but {actual} exist. "
        "Update the badge in README.md."
    )


def test_no_real_corpus_is_tracked() -> None:
    """Nothing corpus-shaped may be TRACKED by git.

    The first version of this test globbed the filesystem, which was wrong in a
    way that mattered: a real corpus is *supposed* to sit in the working tree —
    that is where the engine reads it from — so the test failed for every user
    the moment they had one, including the author. Presence is correct; being
    tracked is the defect. Ask git, not the disk.
    """
    result = subprocess.run(
        ["git", "ls-files", "career-corpus*.yaml", "corpus", "kits", "out"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:  # not a git checkout, e.g. an unpacked sdist
        pytest.skip("not a git working tree")

    tracked = [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip() and line.strip() != "career-corpus.example.yaml"
    ]
    assert not tracked, (
        f"private career data is TRACKED in a public repository: {tracked}. "
        "Deleting the file does not undo this — the history retains it."
    )
