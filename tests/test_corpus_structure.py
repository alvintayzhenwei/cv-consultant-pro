"""Structural rules: identity, addressability, dates, and cross-references."""

from __future__ import annotations

import pytest

from cv_tailor.corpus import CorpusError, load_corpus_text

MINIMAL = """
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
        claim: Shipped the thing
        mechanism: carefully
        tags: [delivery]
"""


def test_bullet_ids_must_be_unique_across_the_whole_corpus() -> None:
    """Selection, traceability and the audit gate all address bullets by id.

    A duplicate id means a rendered claim traces to two different sources, so the
    traceability record stops being a record of anything.
    """
    with pytest.raises(CorpusError) as err:
        load_corpus_text(
            """
person:
  name: Test Person
roles:
  - id: r1
    org: Acme
    title: Engineer
    start: "2020-01"
    end: "2021-01"
    bullets:
      - id: dupe
        claim: A
        mechanism: x
        tags: [t]
  - id: r2
    org: Beta
    title: Engineer
    start: "2021-02"
    end: present
    bullets:
      - id: dupe
        claim: B
        mechanism: y
        tags: [t]
"""
        )

    assert "dupe" in str(err.value)


def test_a_bullet_without_tags_is_rejected() -> None:
    """Tags are how matching finds evidence; an untagged bullet can never be selected."""
    with pytest.raises(CorpusError) as err:
        load_corpus_text(
            """
person:
  name: Test Person
roles:
  - id: r1
    org: Acme
    title: Engineer
    start: "2020-01"
    end: present
    bullets:
      - id: untagged
        claim: Did something
        mechanism: somehow
        tags: []
"""
        )

    assert "untagged" in str(err.value)


def test_dates_parse_and_compare() -> None:
    corpus = load_corpus_text(MINIMAL)
    role = corpus.roles[0]
    assert role.start.year == 2020
    assert role.start.month == 1
    assert role.end is None, "'present' is represented as an open end, not a date"
    assert role.is_current is True


def test_dates_render_in_the_form_a_cv_requires() -> None:
    """MM/YYYY, because that is the form parsers and recruiters both expect."""
    corpus = load_corpus_text(MINIMAL)
    assert corpus.roles[0].rendered_dates() == "01/2020 - Present"


def test_a_role_with_unknown_dates_is_kept_and_flagged_not_silently_dropped() -> None:
    """A role you cannot date is still a role. Dropping it loses real history.

    This is not hypothetical: the site data this corpus was seeded from recorded
    six years on one account with no dates at all, and the first CV generated
    from it was materially weaker as a result.
    """
    corpus = load_corpus_text(
        """
person:
  name: Test Person
roles:
  - id: undated
    org: Old Job
    title: Developer
    start: TODO
    end: TODO
    bullets:
      - id: b1
        claim: Built things
        mechanism: somehow
        tags: [legacy]
"""
    )

    role = corpus.roles[0]
    assert role.start is None
    assert role.needs_dates is True
    assert "undated" in [t.ref for t in corpus.todos()]


def test_an_end_date_before_the_start_date_is_rejected() -> None:
    with pytest.raises(CorpusError) as err:
        load_corpus_text(
            """
person:
  name: Test Person
roles:
  - id: backwards
    org: Acme
    title: Engineer
    start: "2021-06"
    end: "2020-01"
    bullets:
      - id: b1
        claim: A
        mechanism: x
        tags: [t]
"""
        )

    assert "backwards" in str(err.value)


def test_a_skill_pointing_at_a_bullet_that_does_not_exist_is_rejected() -> None:
    """A skill's evidence_refs are what let the renderer prove the skill is held."""
    with pytest.raises(CorpusError) as err:
        load_corpus_text(
            MINIMAL
            + """
skills:
  - name: Python
    evidence_refs: [does-not-exist]
"""
        )

    assert "does-not-exist" in str(err.value)


def test_positions_are_a_separate_entry_kind_from_bullets() -> None:
    """A stated view is not a delivered accomplishment.

    Flattening the two would let an opinion about how to control LLM cost score
    as evidence of having controlled it.
    """
    corpus = load_corpus_text(
        MINIMAL
        + """
positions:
  - id: p-cost
    topic: Production
    question: How do you control LLM cost at scale?
    answer: Route by task difficulty and measure per call.
    source: interview.ts
"""
    )

    assert len(corpus.positions) == 1
    assert len(corpus.roles[0].bullets) == 1
    assert corpus.positions[0].id not in {b.id for b in corpus.all_bullets()}


def test_language_defaults_to_english_without_annotation() -> None:
    corpus = load_corpus_text(MINIMAL)
    assert corpus.language == "en"
    assert corpus.roles[0].bullets[0].language == "en"
