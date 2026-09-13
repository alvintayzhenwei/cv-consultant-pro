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
import sys
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

    The count comes from pytest's own collection, not from counting `def test_`
    lines. The first version counted definitions, which disagreed with the
    number pytest reports the moment a parametrised test existed — a guard that
    is itself wrong about the figure it guards is worse than no guard.
    """
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    match = re.search(r"tests-(\d+)%20passing", readme)
    assert match, "the README must carry a tests-N%20passing badge"
    claimed = int(match.group(1))

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "--no-header", "-p", "no:cacheprovider"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    # Two output shapes in the wild: a single "N tests collected" summary, and
    # (this pytest) one "path: N" line per file. Handle both rather than skip —
    # a guard that silently skips is a guard that is not running.
    total = re.search(r"(\d+)\s+tests? collected", result.stdout)
    if total:
        actual = int(total.group(1))
    else:
        per_file = re.findall(r"^\S+\.py:\s*(\d+)$", result.stdout, re.MULTILINE)
        assert per_file, (
            "could not read a collection count from pytest, so this guard is not "
            f"running. Output tail:\n{result.stdout[-400:]}"
        )
        actual = sum(int(n) for n in per_file)

    assert claimed == actual, (
        f"the README badge claims {claimed} tests, but pytest collects {actual}. "
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


# ── the plugin surface ──────────────────────────────────────────────────────
def test_the_mcp_ceiling_is_tied_to_the_api_the_server_actually_imports() -> None:
    """The exact failure that shipped in two sibling packages, guarded here.

    `mcp.server.fastmcp.FastMCP` was renamed and deleted in mcp 2.0. Both of
    those packages declared `mcp>=1.12` with no ceiling, so from the day 2.x
    landed every fresh `uvx` install died at import and the published install
    instructions could not work for anybody.

    This checks the MANIFEST against the IMPORT, so migrating one and forgetting
    the other fails here rather than in a stranger's terminal. The suite could
    not catch the original break by importing, because a locked dev venv already
    held the old major.
    """
    server = (ROOT / "src" / "cv_consultant_pro" / "mcp_server.py").read_text(encoding="utf-8")
    spec = _requirements().get("mcp")
    assert spec, "the MCP server needs `mcp` declared as a dependency"

    if "from mcp.server.fastmcp import" in server:
        assert "<2" in spec, (
            "the server imports mcp.server.fastmcp, which mcp 2.0 deleted. The "
            f"declared range {spec!r} would resolve it on a fresh install."
        )
    else:
        assert ">=2" in spec, (
            "the server no longer imports the 1.x API, so the FLOOR should move to "
            ">=2 rather than the range being widened."
        )


def test_both_plugin_manifests_launch_the_same_server() -> None:
    """One payload, two wrappers. A drift here means one host gets a stale tool set."""
    import json

    claude = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    codex = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))

    launch = claude["mcpServers"]["cv-consultant-pro"]
    assert codex["mcp_servers"]["cv-consultant-pro"] == launch
    assert claude["version"] == codex["version"] == _pyproject()["project"]["version"]


def test_what_the_manifests_INSTALL_is_what_this_project_PUBLISHES() -> None:
    """The guard for a defect that reached the README and nearly reached PyPI.

    `uvx NAME` resolves NAME as a PACKAGE, not as a command. Under the project's
    first name the manifests said `uvx cv-tailor-mcp` while the distribution was
    named `cv-tailor` — and `cv-tailor-mcp` turned out to be an EXISTING,
    unrelated project on PyPI that also tailors CVs. So anyone following the
    install line would have downloaded and run a stranger's code, plausibly
    without noticing. Caught before anything was published.

    Hence this checks the two names against each other rather than checking
    either alone. The command must be a real console script here, AND whatever
    package `uvx` is told to resolve must be the one this pyproject publishes.
    """
    import json

    claude = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    launch = claude["mcpServers"]["cv-consultant-pro"]
    assert launch["command"] == "uvx"

    args = launch["args"]
    command = args[-1]
    assert command in _pyproject()["project"]["scripts"], (
        f"the manifests launch {command!r}, which is not a console script in pyproject.toml"
    )

    distribution = _pyproject()["project"]["name"]
    if command == distribution:
        assert args == [command], "a bare uvx is only correct when command == package"
    else:
        assert args[:2] == ["--from", distribution], (
            f"the command {command!r} differs from the distribution {distribution!r}, so "
            f"uvx needs `--from {distribution}`. Without it uvx resolves {command!r} as a "
            "PACKAGE NAME on PyPI — which may belong to somebody else entirely."
        )


def test_the_readme_installs_the_same_thing_the_manifests_do() -> None:
    """A copied-and-pasted README line is how most people will install this."""
    import json

    args = json.loads(
        (ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )["mcpServers"]["cv-consultant-pro"]["args"]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert f"uvx {' '.join(args)}" in readme, (
        "the README's install line disagrees with the plugin manifests"
    )


def test_the_skill_is_where_a_plugin_host_looks_for_it() -> None:
    skill = ROOT / "skills" / "cv-consultant-pro" / "SKILL.md"
    assert skill.is_file()
    text = skill.read_text(encoding="utf-8")
    assert text.startswith("---"), "a skill needs YAML frontmatter to be discovered"
    assert "description:" in text.split("---")[1]


def test_the_skill_repeats_the_rules_the_server_enforces() -> None:
    """A host may load the skill and never read this repo. The rules travel with it."""
    text = (ROOT / "skills" / "cv-consultant-pro" / "SKILL.md").read_text(encoding="utf-8").lower()
    assert "own phrasing" in text or "own words" in text
    assert "estimated_placeholder" in text
    assert "exposure to" in text, "the skill must name the way a gap gets softened"


#: PyPI projects belonging to somebody else. No command or package name here may
#: be one of these. Sharing a stranger's package name sends anyone who omits
#: `--from` to THEIR code, and takes their name in our own documentation.
NOT_OURS = {
    # An unrelated MCP server by another author that also tailors a CV to a job
    # posting. This project was called that in its first cut, in every install
    # line, which is the whole reason the list exists. Note a blanket
    # search-and-replace during the rename briefly pointed this set at OUR OWN
    # name — the guard below caught it, which is the other reason it exists.
    "cv-tailor-mcp",
}


def test_nothing_here_is_named_after_someone_elses_project() -> None:
    project = _pyproject()["project"]
    claimed = set(project["scripts"]) | {project["name"]}
    collision = claimed & NOT_OURS
    assert not collision, (
        f"{sorted(collision)} names an existing PyPI project by another author. "
        "Rename ours: a command sharing a stranger's package name sends anyone who "
        "omits `--from` to their code, and borrows their name in our own docs."
    )


def test_their_name_appears_nowhere_a_user_would_copy_from() -> None:
    """Install lines get copied. Their project's name must not be in ours at all."""
    surfaces = (
        ROOT / "README.md",
        ROOT / ".claude-plugin" / "plugin.json",
        ROOT / ".codex-plugin" / "plugin.json",
        ROOT / "skills" / "cv-consultant-pro" / "SKILL.md",
        ROOT / "src" / "cv_consultant_pro" / "mcp_server.py",
    )
    for name in NOT_OURS:
        for surface in surfaces:
            assert name not in surface.read_text(encoding="utf-8"), (
                f"{surface.name} mentions {name!r}, which is another author's project"
            )


def test_the_readme_has_no_relative_links() -> None:
    """The README IS the PyPI project page, and PyPI has no repo to resolve against.

    GitHub resolves `docs/sample-rail.png` against the repository; PyPI renders
    the same markdown standalone, so a relative path there is a broken image or
    a dead link. It shipped that way in 0.1.0 — the screenshot the README uses
    to show what the tool produces was a broken-image icon on the project page,
    which is the first thing a stranger sees.
    """
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    # Markdown links and images, minus anchors and mailto.
    targets = re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", readme)
    relative = [
        t for t in targets
        if not t.startswith(("http://", "https://", "#", "mailto:"))
    ]
    assert not relative, (
        f"these README targets are relative and will break on PyPI: {relative}. "
        "Use an absolute https:// URL — raw.githubusercontent.com for an image, "
        "github.com/<owner>/<repo>/blob/main/... for a file."
    )
