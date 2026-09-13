"""Scoring corpus evidence against a posting's requirements."""

from __future__ import annotations

from cv_consultant_pro.corpus import load_corpus_text
from cv_consultant_pro.jd import parse_jd
from cv_consultant_pro.match import Verdict, score

CORPUS = """
person:
  name: Test Person
roles:
  - id: r1
    org: Acme
    title: Engineer
    start: "2019-06"
    end: present
    tags: [software, development, engineering]
    bullets:
      - id: b-python-tooling
        claim: Built internal tooling in Python
        mechanism: scripts and services
        tags: [python, tooling, automation]
      - id: b-discovery
        claim: Ran technical discovery sessions with every onboarding team
        mechanism: briefings and kickoffs
        tags: [discovery, stakeholder-management, onboarding]
skills:
  - name: Python
    tags: [languages]
    evidence_refs: [b-python-tooling]
  - name: Technical discovery
    aliases: [technical discovery sessions, discovery sessions]
    tags: [delivery]
    evidence_refs: [b-discovery]
"""

POSTING = """
Minimum qualifications:
- Experience with software development using Python or similar coding languages.
- Experience leading technical discovery sessions.
- Experience with quantum error correction on superconducting hardware.
"""


def _scored():
    corpus = load_corpus_text(CORPUS)
    jd = parse_jd(POSTING)
    return {row.requirement.text: row for row in score(jd, corpus).rows}


def test_every_requirement_is_scored_exactly_once() -> None:
    corpus = load_corpus_text(CORPUS)
    jd = parse_jd(POSTING)
    result = score(jd, corpus)
    assert len(result.rows) == len(jd.requirements)


def test_a_requirement_backed_by_an_evidenced_skill_scores_strong_and_cites_it() -> None:
    rows = _scored()
    row = next(r for k, r in rows.items() if "discovery" in k)
    assert row.verdict is Verdict.STRONG
    assert "b-discovery" in row.evidence_ids


def test_an_unsupported_requirement_is_an_honest_gap_citing_nothing() -> None:
    rows = _scored()
    row = next(r for k, r in rows.items() if "quantum" in k)
    assert row.verdict is Verdict.GAP
    assert row.evidence_ids == []


def test_an_alias_is_what_permits_the_postings_own_wording() -> None:
    """The corpus declares 'technical discovery sessions' as an alias.

    Without the alias the phrase is not adopted — that is the whole boundary
    between tailoring and inventing.
    """
    rows = _scored()
    row = next(r for k, r in rows.items() if "discovery" in k)
    assert any("Technical discovery" == s for s in row.skill_names)


def test_a_years_threshold_is_computed_from_real_dates_not_asserted() -> None:
    """A minimum years bar is an eligibility filter, so it lands in hard_filters.

    The engine reports the span the corpus evidences alongside the threshold,
    rather than declaring a pass. Overlapping roles make any automatic sum
    arguable, and the reader is better placed to make that call than a rule is.
    """
    corpus = load_corpus_text(CORPUS)
    jd = parse_jd("Minimum qualifications:\n- 5 years of experience in software development.\n")
    result = score(jd, corpus)
    row = result.hard_filters[0]
    assert row.requirement.years_required == 5
    assert row.evidenced_years is not None, "the span must be computed from role dates"


def test_hard_filters_are_reported_separately_from_scored_rows() -> None:
    jd = parse_jd(
        "Minimum qualifications:\n"
        "- Applicants must have a current right to work in Singapore without visa sponsorship.\n"
        "- Experience with software development using Python.\n"
    )
    result = score(jd, load_corpus_text(CORPUS))
    assert result.hard_filters, "the right-to-work line must surface as a hard filter"
    assert all(r.requirement.is_hard_filter for r in result.hard_filters)
