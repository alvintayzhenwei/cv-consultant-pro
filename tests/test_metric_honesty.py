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

from cv_tailor.corpus import CorpusError, load_corpus_text

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
