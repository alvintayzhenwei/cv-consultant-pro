"""Reading a job posting into requirements."""

from __future__ import annotations

from cv_consultant_pro.jd import Tier, parse_jd

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


# ── postings that use no bullet glyph at all ────────────────────────────────
# Found by running the engine against Apple's own job API, which returns
# qualifications as plain newline-separated lines. Every fixture written before
# this one used "- " bullets, so the whole suite was green while the parser
# silently found nothing in a real posting — and then told the user to check
# that the headings had survived the copy, which was wrong advice: the headings
# were fine, the bullets had never existed.
UNBULLETED = """Engineering Product Manager

Description
As an Engineering Product Manager on our team, you will be the driving force
behind the planning and delivery of internal tools.

Minimum Qualifications
Bachelor's degree in Computer Science, Information Systems, or related field
Minimum 5 years of experience in technical program or project management
Hands-on experience in frontend software engineering, including React and JavaScript

Preferred Qualifications
Experience with AI-assisted development tools (e.g., Claude Code, Codex)
Familiarity with Agile or iterative development practices
"""


def test_a_posting_with_no_bullet_glyphs_still_yields_requirements() -> None:
    jd = parse_jd(UNBULLETED)
    assert jd.requirements, (
        "a posting whose qualifications are plain lines under a heading — which is "
        "what Apple's own job API returns — produced nothing at all"
    )
    texts = [r.text for r in jd.requirements]
    assert any("React" in t for t in texts)
    assert any("Agile" in t for t in texts)


def test_tiers_survive_when_the_bullets_are_missing() -> None:
    jd = parse_jd(UNBULLETED)
    minimum = [r.text for r in jd.by_tier(Tier.MINIMUM)]
    preferred = [r.text for r in jd.by_tier(Tier.PREFERRED)]
    assert any("5 years" in t for t in minimum)
    assert any("Agile" in t for t in preferred)
    assert not any("Agile" in t for t in minimum), "a preferred line leaked into minimum"


def test_prose_outside_a_qualifications_section_is_not_a_requirement() -> None:
    """The cost of accepting unbulleted lines, and the bound that contains it.

    `Description` DOES open a section here — a responsibilities one — so the
    first cut of the unbulleted-line rule scored Apple's marketing prose as
    requirements. Only a qualifications list takes unbulleted lines now, because
    a qualifications section is a list by convention and a description is not.
    """
    jd = parse_jd(UNBULLETED)
    assert not any("driving force" in r.text for r in jd.requirements)


def test_a_paragraph_inside_a_section_is_not_mistaken_for_a_requirement() -> None:
    """Some postings open a qualifications section with a sentence of prose.

    A requirement is a short clause; the longest real one measured across both
    Apple postings was 142 characters. A paragraph is not one, and scoring it
    would put a wall of marketing text on the scorecard.
    """
    paragraph = (
        "We are looking for someone who thrives in ambiguity and brings a genuine "
        "passion for building tools that people actually want to use, working "
        "closely with partners across several time zones to land outcomes that "
        "matter to the business and to the teams we support every single day, "
        "which means communicating clearly and often with everyone involved."
    )
    jd = parse_jd(f"Minimum Qualifications\n{paragraph}\nReact and JavaScript experience\n")
    texts = [r.text for r in jd.requirements]
    assert any("React" in t for t in texts)
    assert not any("thrives in ambiguity" in t for t in texts)
