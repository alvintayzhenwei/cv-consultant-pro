"""The pipeline, run against five professions it was not written for.

Every other test in this suite uses one career and one style of job ad. That is
the narrowest possible proof for a package strangers will install, and it hides
exactly the assumptions that matter: heading conventions, what counts as a hard
filter, and whether the vocabulary bridge works outside a technology CV.
"""

from __future__ import annotations

import pytest

from cv_tailor.corpus import load_corpus_text
from cv_tailor.jd import Tier, parse_jd
from cv_tailor.match import Verdict, score
from cv_tailor.render import render, select
from cv_tailor.templates import TEMPLATES, render_html

from .fixtures import ALL_DOMAINS, Domain

IDS = [d.key for d in ALL_DOMAINS]


def _run(domain: Domain):
    corpus = load_corpus_text(domain.corpus)
    jd = parse_jd(domain.posting, title="Test Role")
    card = score(jd, corpus)
    kit = render(corpus, jd, card, select(corpus, card))
    return corpus, jd, card, kit


@pytest.mark.parametrize("domain", ALL_DOMAINS, ids=IDS)
def test_every_domain_parses_a_posting_into_requirements(domain: Domain) -> None:
    """Healthcare and education postings use headings a tech ad never does.

    "Essential criteria", "Person specification", "Main duties" — a parser that
    only knows "Minimum qualifications" reads those postings as prose and finds
    nothing to score.
    """
    jd = parse_jd(domain.posting)
    assert jd.requirements, f"{domain.key}: no requirements found in the posting"
    assert jd.by_tier(Tier.MINIMUM), f"{domain.key}: nothing recognised as a minimum"


@pytest.mark.parametrize("domain", ALL_DOMAINS, ids=IDS)
def test_every_domain_flags_its_licence_or_registration_as_a_hard_filter(domain: Domain) -> None:
    """Most regulated professions gate on a credential, not on years.

    Nursing registration, chartered status, qualified teacher status, a right to
    work, a professional accountancy qualification. Scoring one of those as an
    ordinary requirement would let a disqualifying miss hide behind a good match.
    """
    _corpus, _jd, card, _kit = _run(domain)
    filters = " ".join(r.requirement.text.lower() for r in card.hard_filters)
    assert domain.hard_filter_phrase in filters, (
        f"{domain.key}: {domain.hard_filter_phrase!r} was not treated as a hard filter. "
        f"Hard filters found: {[r.requirement.text for r in card.hard_filters]}"
    )


@pytest.mark.parametrize("domain", ALL_DOMAINS, ids=IDS)
def test_the_alias_bridge_works_outside_a_technology_vocabulary(domain: Domain) -> None:
    """A posting says "tissue viability"; the corpus calls it "Wound care".

    That substitution is the whole mechanism by which a CV can use an employer's
    own words truthfully, and nothing about it should be specific to software.
    """
    _corpus, _jd, card, _kit = _run(domain)
    named = {name for row in card.rows + card.hard_filters for name in row.skill_names}
    assert domain.expected_skill in named, (
        f"{domain.key}: expected {domain.expected_skill!r} to match under one of its "
        f"aliases. Matched instead: {sorted(named)}"
    )


@pytest.mark.parametrize("domain", ALL_DOMAINS, ids=IDS)
def test_every_domain_produces_a_cv_that_passes_the_audit(domain: Domain) -> None:
    _corpus, _jd, _card, kit = _run(domain)
    assert kit.document.roles, f"{domain.key}: no roles selected"
    assert kit.traceability, f"{domain.key}: nothing traced"
    assert kit.document.summary, f"{domain.key}: no summary selected"


@pytest.mark.parametrize("domain", ALL_DOMAINS, ids=IDS)
def test_placeholders_survive_in_every_domain(domain: Domain) -> None:
    """Each fixture carries one unverified figure. It must reach the page as a hole."""
    _corpus, _jd, _card, kit = _run(domain)
    assert kit.placeholders, f"{domain.key}: the unverified metric was not reported"
    for _bullet_id, holder in kit.placeholders:
        assert holder in kit.markdown, f"{domain.key}: placeholder {holder} did not render"


@pytest.mark.parametrize("domain", ALL_DOMAINS, ids=IDS)
def test_every_domain_renders_in_every_layout(domain: Domain) -> None:
    _corpus, _jd, _card, kit = _run(domain)
    for template in TEMPLATES.values():
        html = render_html(kit.document, template)
        assert kit.document.name in html
        assert "EXPERIENCE" in html.upper()


@pytest.mark.parametrize("domain", ALL_DOMAINS, ids=IDS)
def test_a_domain_scores_something_and_not_everything(domain: Domain) -> None:
    """A matcher that scores everything strong is as useless as one that scores nothing.

    Each fixture deliberately holds evidence for some requirements and not
    others, so a real spread is the signal that scoring is doing work rather
    than rubber-stamping.
    """
    _corpus, _jd, card, _kit = _run(domain)
    verdicts = {row.verdict for row in card.rows}
    assert Verdict.STRONG in verdicts, f"{domain.key}: nothing scored strong"
    assert len(verdicts) > 1, (
        f"{domain.key}: every requirement scored the same verdict ({verdicts}), which means "
        "the matcher is not discriminating"
    )
