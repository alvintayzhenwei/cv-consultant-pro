"""The anti-fabrication guard.

This is the load-bearing test in the project. The rule it enforces — that a
figure is either verified or is visibly a placeholder — is the whole reason a
generated CV can be trusted in a room. A prompt instructing a renderer not to
invent numbers is advisory; a failing build is not.

Each test names the fabrication it prevents, because a guard whose purpose is
not written down gets relaxed by whoever next finds it inconvenient.
"""

from __future__ import annotations

import pytest

from cv_consultant_pro.corpus import CorpusError, load_corpus_text

BASE = """
person:
  name: Test Person
roles:
  - id: acme-eng
    org: Acme
    title: Engineer
    start: "2020-01"
    end: present
    bullets:
      - id: b1
        claim: "{claim}"
        mechanism: doing the thing
        tags: [testing]
        metric: {metric}
"""


def _corpus(claim: str, metric: str) -> str:
    return BASE.format(claim=claim, metric=metric)


def test_unverified_metric_carrying_a_real_number_is_rejected() -> None:
    """Prevents: claiming a measured 37% improvement that was never measured."""
    with pytest.raises(CorpusError) as err:
        load_corpus_text(_corpus("Cut cost", "{verified: false, value: '37%'}"))

    assert "b1" in str(err.value), "the error must name the offending bullet"
    assert "verified" in str(err.value).lower()


def test_verified_metric_without_a_value_is_rejected() -> None:
    """Prevents: a bullet asserting it is measured while carrying no measurement."""
    with pytest.raises(CorpusError) as err:
        load_corpus_text(_corpus("Cut cost", "{verified: true}"))

    assert "b1" in str(err.value)


def test_placeholder_disguising_a_number_is_rejected() -> None:
    """Prevents: `placeholder: 37%` — a fabricated figure wearing a placeholder's label.

    Checking only the `value` field would miss this, and it is the more likely
    mistake: someone fills in a number where the template asked for a shape.
    """
    with pytest.raises(CorpusError) as err:
        load_corpus_text(_corpus("Cut cost by 37%", "{verified: false, placeholder: '37%'}"))

    assert "b1" in str(err.value)
    assert "placeholder" in str(err.value).lower()


def test_placeholder_must_appear_in_the_text_it_belongs_to() -> None:
    """Prevents: an orphan placeholder that never renders, so nobody fills it in.

    A placeholder exists to leave a visible hole in the output. One that is
    declared but not referenced silently drops the hole, and the bullet ships
    reading as though it were complete.
    """
    with pytest.raises(CorpusError) as err:
        load_corpus_text(
            _corpus("Cut cost substantially", "{verified: false, placeholder: '[X]%'}")
        )

    assert "b1" in str(err.value)


def test_well_formed_verified_and_unverified_metrics_both_pass() -> None:
    verified = load_corpus_text(
        _corpus("Cut release prep from 45 minutes to seconds", "{verified: true, value: '45 min'}")
    )
    assert verified.roles[0].bullets[0].metric.verified is True

    unverified = load_corpus_text(
        _corpus("Cut inference cost per task by [X]%", "{verified: false, placeholder: '[X]%'}")
    )
    assert unverified.roles[0].bullets[0].metric.verified is False
    assert unverified.roles[0].bullets[0].metric.placeholder == "[X]%"


def test_a_bullet_may_carry_no_metric_at_all() -> None:
    """Not every true statement is a measurement; requiring one would invite invention."""
    corpus = load_corpus_text(
        """
person:
  name: Test Person
roles:
  - id: acme-eng
    org: Acme
    title: Engineer
    start: "2020-01"
    end: present
    bullets:
      - id: b1
        claim: Led the migration off the legacy gateway
        mechanism: incremental strangler pattern
        tags: [architecture]
"""
    )
    assert corpus.roles[0].bullets[0].metric is None


# ── a figure the user could not actually state ──────────────────────────────
import json as _json  # noqa: E402

from cv_consultant_pro import mcp_server as _mcp  # noqa: E402


def _call(tool, **kwargs) -> dict:
    return _json.loads(tool(**kwargs))


def test_an_unsure_recollection_is_refused_as_a_measured_figure(tmp_path, monkeypatch) -> None:
    """"roughly 30 I think, maybe 40" was written as `verified: true`.

    Found by an outside tester on the published 0.1.2: it landed one line under
    a claim that said nobody had ever run the numbers.

    This is NOT a ban on hedged figures. "~45 minutes to seconds" and "around 2
    months" are honest — the hedge is the user's own and travels with the claim
    onto the CV, where they can defend it. An "I think" is different in kind: it
    marks the speaker as unsure WHICH number it was, and the tool's own contract
    is that such a number stays a visible placeholder.
    """
    from cv_consultant_pro.session import Session

    from .fixtures import NURSE

    corpus = tmp_path / "career-corpus.yaml"
    corpus.write_text(NURSE.corpus, encoding="utf-8")
    monkeypatch.setattr(_mcp, "_session", Session())
    monkeypatch.chdir(tmp_path)

    _call(_mcp.cv_validate, corpus_path=str(corpus))
    _call(_mcp.cv_ingest_jd, posting=NURSE.posting)
    _call(_mcp.cv_score)
    holes = _call(_mcp.cv_fill_placeholder)["placeholders"]
    if not holes:
        import pytest

        pytest.skip("this posting selects no bullet carrying a placeholder")

    bullet = holes[0]["bullet"]
    before = corpus.read_text(encoding="utf-8")

    for bad, why in (
        ("roughly 30 I think, maybe 40", "unsure which number"),
        ("several", "no number at all"),
        ("I ran the ward for a long time and trained a lot of people over 12 years", "a sentence"),
    ):
        result = _call(_mcp.cv_fill_placeholder, bullet_id=bullet, measured_figure=bad)
        assert "error" in result, f"{why}: {bad!r} was accepted"
        assert "keep_placeholder" in result.get("hint", "")
    assert corpus.read_text(encoding="utf-8") == before, "a refused figure still wrote to disk"

    ok = _call(_mcp.cv_fill_placeholder, bullet_id=bullet, measured_figure="around 42")
    assert "error" not in ok, ok
