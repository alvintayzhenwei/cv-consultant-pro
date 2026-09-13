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


def test_a_heading_that_spells_out_its_contraction_still_opens_a_section() -> None:
    """"What we are looking for" found NOTHING while "What we're looking for" found all of it.

    The patterns were `we'?re` and `you'?ll`, which match the contraction and the
    typo'd form without the apostrophe — and not the words spelled out. Postings
    write it both ways, so half of them lost their whole requirements section and
    the tool reported an empty scorecard as though the corpus were at fault.
    """
    for heading in (
        "What we're looking for",
        "What we are looking for",
        "What you'll do",
        "What you will do",
    ):
        jd = parse_jd(f"{heading}\n- Experience monitoring clinical trial sites.\n- GCP training.\n")
        assert len(jd.requirements) == 2, f"{heading!r} parsed {len(jd.requirements)}"


def test_the_noun_sponsor_is_not_mistaken_for_visa_sponsorship() -> None:
    """"sponsor" is everyday vocabulary in whole industries.

    A clinical-research posting says "working with a sponsor or CRO"; publishing,
    sport and events all use it too. Matching the bare word moved a scoreable
    requirement out of the scorecard and into "answer this yourself, no corpus
    entry can evidence it" — so the candidate lost the credit AND was told to
    resolve something that was never about immigration.
    """
    scoreable = parse_jd(
        "Minimum qualifications:\n"
        "- Experience working with a sponsor or CRO on interventional studies.\n"
    ).requirements
    assert scoreable and not scoreable[0].is_hard_filter, scoreable[0]

    for line in (
        "Applicants must not require sponsorship of a visa.",
        "We are unable to offer visa sponsorship for this role.",
        "The company cannot sponsor work permits.",
        "No sponsorship is available.",
    ):
        found = parse_jd(f"Minimum qualifications:\n- {line}\n").requirements
        assert found and found[0].is_hard_filter, f"missed a real filter: {line!r}"


def test_the_common_ways_a_posting_names_its_requirements_all_open_a_section() -> None:
    """An unrecognised heading does not degrade — it DISCARDS.

    Lines under an unknown heading are prose to the parser, so the whole block
    vanishes while `cv_ingest_jd` still reports a requirement count (made up of
    boilerplate matched elsewhere). Three independent testers hit this from
    three professions: "Essential requirements" lost four of six essentials,
    "Essential - you will not be shortlisted without these" lost every one, and
    a posting using "What we are looking for" produced an empty scorecard that
    read as though the CORPUS were at fault.

    These are the phrasings real postings use. Missing one costs a whole
    section, so the list is worth more than it looks.
    """
    essential = [
        "Essential",
        "Essential criteria",
        "Essential requirements",
        "Essential - you will not be shortlisted without these",
        "Required",
        "Requirements",
        "Must have",
        "You will have",
        "You'll have",
        "Key skills",
        "Skills required",
        "What we are looking for",
        "What we're looking for",
        "About you",
    ]
    for heading in essential:
        jd = parse_jd(f"{heading}\n- Five years of post-qualification experience.\n- Part 36 offers.\n")
        assert len(jd.requirements) == 2, f"{heading!r} parsed {len(jd.requirements)}"
        assert jd.requirements[1].tier is Tier.MINIMUM, heading

    for heading in ("Desirable", "Desirable criteria", "Desirable requirements",
                    "Desirable skills", "Nice to have"):
        jd = parse_jd(f"{heading}\n- Costs budgeting experience.\n- Advocacy experience.\n")
        assert len(jd.requirements) == 2, f"{heading!r} parsed {len(jd.requirements)}"
        assert jd.requirements[1].tier is Tier.PREFERRED, heading
