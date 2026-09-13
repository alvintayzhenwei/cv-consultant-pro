"""Every source and test file must be tracked by git.

Written after four files — the whole corpus schema, loader and validator —
shipped to a public repository as nothing at all.

`.gitignore` carried `corpus/` to keep a private career corpus out. Git patterns
without a leading slash match at ANY depth, so it also matched
`src/cv_consultant_pro/corpus/`. Locally everything passed, because the files were on
disk. CI cloned a repository that did not contain them and failed importing
`cv_consultant_pro.corpus`.

The existing guards could not catch it: they all ask "is anything private
tracked?" and this is the mirror question, "is anything public NOT tracked?"
A privacy rule that is too broad fails silently and in exactly this direction.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _tracked() -> set[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip("not a git working tree")
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def test_no_source_or_test_file_is_untracked() -> None:
    tracked = _tracked()

    untracked: list[str] = []
    for base in ("src", "tests"):
        for path in (ROOT / base).rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            rel = path.relative_to(ROOT).as_posix()
            if rel not in tracked:
                untracked.append(rel)

    assert not untracked, (
        "these files exist on disk but are NOT in the repository, so a fresh "
        f"clone cannot import them: {sorted(untracked)}. Check .gitignore — a "
        "pattern without a leading slash matches at any depth."
    )


def test_the_shipped_package_exposes_its_subpackages() -> None:
    """The failure this test file exists for, stated as behaviour.

    `import cv_consultant_pro` succeeded in CI while `cv_consultant_pro.corpus` did not, because
    the parent package was present and the subpackage was not. Importing the top
    level proves nothing.
    """
    import cv_consultant_pro.corpus
    import cv_consultant_pro.docx
    import cv_consultant_pro.jd
    import cv_consultant_pro.match
    import cv_consultant_pro.render
    import cv_consultant_pro.templates  # noqa: F401


def test_private_paths_are_still_ignored_at_the_repository_root() -> None:
    """Anchoring the patterns must not have opened the disclosure boundary.

    The fix narrowed `corpus/` to `/corpus/`. This asserts the narrowing did not
    go too far: a corpus at the root is still refused.
    """
    for candidate in ("career-corpus.yaml", "corpus/anything.yaml", "kits/x/cv.md"):
        result = subprocess.run(
            ["git", "check-ignore", "-q", candidate],
            cwd=ROOT,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, f"{candidate} is NOT ignored and must be"
