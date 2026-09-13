"""Selection, rendering and the audit gate."""

from __future__ import annotations

import pytest

from cv_consultant_pro.corpus import load_corpus_text
from cv_consultant_pro.jd import parse_jd
from cv_consultant_pro.match import score
from cv_consultant_pro.render import AuditError, render, select

from .fixtures import NURSE

CORPUS = """
person:
  name: Test Person
  location: Singapore
  email: t@example.com
roles:
  - id: recent
    org: Acme
    title: Engineer
    start: "2022-01"
    end: present
    bullets:
      - id: b-relevant
        claim: Ran technical discovery sessions with onboarding teams
        mechanism: briefings and kickoffs
        tags: [discovery, onboarding]
      - id: b-placeholder
        claim: Cut inference cost per task by [X]%
        mechanism: routing by task tier
        tags: [discovery, cost]
        metric:
          verified: false
          placeholder: "[X]%"
  - id: ancient
    org: Old Co
    title: Webmaster
    start: "2005-01"
    end: "2007-01"
    bullets:
      - id: b-irrelevant
        claim: Maintained a brochure site
        mechanism: hand-edited HTML
        tags: [html]
skills:
  - name: Technical discovery
    aliases: [technical discovery sessions]
    evidence_refs: [b-relevant]
  - name: Inference cost optimisation
    aliases: [inference cost, cost per request]
    evidence_refs: [b-placeholder]
"""

POSTING = (
    "Minimum qualifications:\n"
    "- Experience leading technical discovery sessions.\n"
    "- Familiarity with inference cost and cost per request.\n"
)


def _kit():
    corpus = load_corpus_text(CORPUS)
    jd = parse_jd(POSTING, title="Test Role")
    card = score(jd, corpus)
    return corpus, render(corpus, jd, card, select(corpus, card))


def test_an_irrelevant_role_is_dropped_whole_not_truncated() -> None:
    _, kit = _kit()
    assert "ancient" in kit.selection.dropped_roles
    assert "brochure site" not in kit.markdown


def test_a_placeholder_survives_rendering_verbatim() -> None:
    """The hole must reach the page, or an unmeasured figure ships looking real."""
    _, kit = _kit()
    assert "[X]%" in kit.markdown
    assert ("b-placeholder", "[X]%") in kit.placeholders


def test_every_rendered_bullet_is_traceable_to_a_corpus_id() -> None:
    corpus, kit = _kit()
    known = {b.id for b in corpus.all_bullets()}
    assert kit.traceability
    for bullet_id, _claim in kit.traceability:
        assert bullet_id in known


def test_the_skills_block_leads_with_what_the_posting_asked_for() -> None:
    _, kit = _kit()
    assert kit.selection.skills[0] == "Technical discovery"


def test_dates_render_in_the_required_form() -> None:
    _, kit = _kit()
    assert "01/2022 - Present" in kit.markdown


def test_the_audit_refuses_output_whose_bullets_are_not_in_the_corpus() -> None:
    """The gate that makes 'never invents a claim' checkable rather than asserted."""
    corpus = load_corpus_text(CORPUS)
    jd = parse_jd(POSTING, title="Test Role")
    card = score(jd, corpus)
    selection = select(corpus, card)

    # Simulate a renderer that smuggled in an entry the corpus does not hold.
    role, bullets = selection.roles[0]
    ghost = type(bullets[0])(
        id="not-in-corpus", claim="Invented", mechanism="x", tags=["x"]
    )
    selection.roles[0] = (role, [*bullets, ghost])

    with pytest.raises(AuditError) as err:
        render(corpus, jd, card, selection)
    assert "not-in-corpus" in str(err.value)


def test_the_line_under_the_name_can_be_something_other_than_the_posting() -> None:
    """A CV going into a talent pool must not announce a role nobody applied for.

    The heading was hardwired to the posting title, which is right for one
    application and wrong everywhere else: uploaded to a centralised candidate
    pool it claims an application that was never made, and a recruiter searching
    that pool reads a job title belonging to another company.
    """
    from cv_consultant_pro.render import build_document

    corpus = load_corpus_text(NURSE.corpus)
    jd = parse_jd(NURSE.posting, title="Ward Sister, St Elsewhere")
    card = score(jd, corpus)
    selection = select(corpus, card)

    default, _t, _p = build_document(corpus, jd, card, selection)
    assert default.target_title == "Ward Sister, St Elsewhere"

    current, _t, _p = build_document(corpus, jd, card, selection, target="current")
    assert current.target_title and current.target_title != "Ward Sister, St Elsewhere"

    none, _t, _p = build_document(corpus, jd, card, selection, target="none")
    assert none.target_title is None

    headline, _t, _p = build_document(
        corpus, jd, card, selection, target="Senior Nurse · Acute Care"
    )
    assert headline.target_title == "Senior Nurse · Acute Care"
