"""Where the corpus is read from.

The path is configurable because the corpus does not live with the engine: it is
private, and the engine is public. Hard-coding a location would force the two
into the same directory, which is the arrangement this project exists to avoid.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cv_consultant_pro.corpus import ENV_VAR, CorpusError, load_corpus, resolve_corpus_path


def test_an_explicit_path_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_VAR, str(tmp_path / "from-env.yaml"))
    assert resolve_corpus_path(tmp_path / "explicit.yaml") == tmp_path / "explicit.yaml"


def test_the_environment_variable_is_used_when_no_path_is_given(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "from-env.yaml"
    monkeypatch.setenv(ENV_VAR, str(target))
    assert resolve_corpus_path() == target


def test_an_empty_environment_variable_counts_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Containers and CI inject "" for an absent variable.

    Treating that as a path points the engine at a file named "" and produces a
    confusing failure far from the cause.
    """
    monkeypatch.setenv(ENV_VAR, "   ")
    assert resolve_corpus_path().name == "career-corpus.yaml"


def test_a_missing_corpus_says_what_to_do_about_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ENV_VAR, str(tmp_path / "nope.yaml"))
    with pytest.raises(CorpusError) as err:
        load_corpus()

    message = str(err.value)
    assert "career-corpus.example.yaml" in message, "the error must name the way forward"
