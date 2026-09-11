"""Reading a job posting into requirements."""

from __future__ import annotations

from cv_tailor.jd import Tier, parse_jd

POSTING = """
AI Technical Enablement Lead, Forward Deployed Engineering
Google place Singapore

Google will be prioritizing applicants who have a current right to work in Singapore,
and do not require Google's sponsorship of a visa.

Minimum qualifications:
- Bachelor's degree in Engineering, Computer Science, a related field, or equivalent practical experience.
- 5 years of experience with software development using Python or similar coding languages.
- Experience leading technical discovery sessions.

Preferred qualifications:
- Master's degree or PhD in AI, Computer Science, or a related technical field.
- Experience implementing multi-agent systems using frameworks (e.g., LangGraph, CrewAI, ADK).

About the job
Some prose about the team that is not a requirement.

Responsibilities
- Develop deep technical enablement programs.
- Map persona-based views of technical GTM field enablement needs.
"""


def test_requirements_are_split_by_the_posting_own_headings() -> None:
    jd = parse_jd(POSTING)

    tiers = {r.tier for r in jd.requirements}
    assert Tier.MINIMUM in tiers
    assert Tier.PREFERRED in tiers
    assert Tier.RESPONSIBILITY in tiers


def test_prose_is_not_mistaken_for_a_requirement() -> None:
    """'About the job' is narrative. Scoring it would invent requirements."""
    jd = parse_jd(POSTING)
    assert not any("prose about the team" in r.text for r in jd.requirements)


def test_exact_wording_is_preserved() -> None:
    """The posting's own words are what a keyword search looks for."""
    jd = parse_jd(POSTING)
    assert any("technical discovery sessions" in r.text for r in jd.requirements)


def test_a_years_threshold_is_captured_as_a_number() -> None:
    jd = parse_jd(POSTING)
    years = [r for r in jd.requirements if r.years_required]
    assert years, "the 5-year line must be recognised"
    assert years[0].years_required == 5
    assert years[0].is_hard_filter


def test_a_visa_or_right_to_work_line_is_flagged_as_a_hard_filter() -> None:
    """Failing this disqualifies regardless of every other match.

    Averaging it into a score would let a disqualifying miss hide behind a high
    percentage, which is the most expensive kind of false comfort.
    """
    jd = parse_jd(POSTING)
    filters = [r for r in jd.requirements if r.is_hard_filter]
    assert any("right to work" in r.text.lower() for r in filters)


def test_a_degree_line_is_recognised() -> None:
    jd = parse_jd(POSTING)
    assert any(r.is_degree for r in jd.requirements)


def test_the_title_and_location_are_captured() -> None:
    jd = parse_jd(POSTING, title="AI Technical Enablement Lead", source="google")
    assert jd.title == "AI Technical Enablement Lead"
    assert jd.source == "google"
