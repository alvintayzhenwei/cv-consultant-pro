"""Read a job posting into structured requirements.

Deliberately heuristic and deliberately conservative. It reads the posting's own
headings rather than trying to understand it, and it keeps every requirement's
exact wording, because that wording is what a keyword search looks for and what
a truthful CV may echo.

Prose is not scored. A narrative "About the job" section describes a team;
treating its sentences as requirements would invent criteria the employer never
set, and then report gaps against them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum

_BULLET = re.compile(r"^\s*(?:[-•*]|\d+[.)])\s+(.*\S)\s*$")

#: The longest line still treated as a requirement when a posting uses no bullet
#: glyphs. Measured rather than guessed: across Apple's two Singapore postings
#: the longest genuine qualification line was 142 characters, so this clears
#: every real one while still refusing a paragraph of prose.
_MAX_REQUIREMENT = 240

#: Sections whose contents are a LIST by convention, so an unbulleted line in
#: one is still a requirement. Responsibilities are deliberately absent:
#: `Description` opens one, and a description is prose.
_LIST_SECTIONS = frozenset({"minimum", "preferred"})
_YEARS = re.compile(r"\b(\d{1,2})\s*\+?\s*(?:or more\s*)?years?\b", re.IGNORECASE)

# Section headings, matched loosely because postings punctuate them freely.
_HEADINGS: list[tuple[str, Tier]] = []

# Lines that disqualify rather than merely score. Failing one is not a low score,
# it is a closed door — so they are surfaced apart from the scored rows.
_HARD_FILTER_PATTERNS = (
    r"right to work",
    r"work authorisation|work authorization",
    # "sponsor" is everyday vocabulary in whole industries — a trial sponsor, a
    # publishing sponsor, an event sponsor. Matching the bare word moved a
    # scoreable requirement ("working with a sponsor or CRO") out of the
    # scorecard and into "answer this yourself, no corpus entry can evidence
    # it", so the candidate lost the credit AND was told to resolve something
    # that was never about immigration. It counts only alongside immigration
    # vocabulary, or where the posting is plainly refusing it.
    r"\bsponsor(ship|ing)?\b[^.]{0,60}\b(visa|immigration|work permit|right to work|employment pass)\b",
    r"\b(visa|immigration|work permit|right to work|employment pass)\b[^.]{0,60}\bsponsor(ship|ing)?\b",
    r"\b(no|not|cannot|can't|unable to|without|do not|does not)\b[^.]{0,30}\bsponsor(ship|ing)?\b",
    r"visa\b",
    r"citizen(ship)?\b",
    r"security clearance",
    r"fluen(t|cy) in",
    r"native (speaker|proficiency)",
    r"must be (located|based)",
    r"relocat",
    # Most regulated professions gate on a credential rather than on years, and
    # the original list had none of them: nursing registration, chartered
    # status, qualified teacher status, a practising certificate. Scoring one of
    # those as an ordinary requirement lets a disqualifying miss hide behind a
    # good overall match.
    #
    # Each is GATED on a qualifier rather than matching the bare noun, because
    # the bare noun over-fires. "Post-registration experience in an acute
    # setting" is a scorable requirement about experience; "Current NMC
    # registration" is a door. Only the second should leave the scorecard.
    r"\b(current|valid|active|full|professional)\b[^.]{0,40}\bregistration\b",
    r"\bregistered\s+(nurse|practitioner|with the)\b",
    r"\bchartered\b",
    r"\bqualified\s+(teacher status|accountant|nurse|solicitor|surveyor|social worker)\b",
    r"\bqts\b",
    r"\b(hold|holds|holding|must have|must hold)\b[^.]{0,40}"
    r"\b(licen[cs]e|certificate|registration|accreditation)\b",
    r"\bpractising certificate\b",
    r"\bdbs (check|clearance)\b|\bworking with children check\b|\bbackground check\b",
)

_DEGREE_PATTERNS = (
    r"bachelor'?s?\b",
    r"master'?s?\b",
    r"\bph\.?d\b",
    r"\bdegree\b",
)


class Tier(StrEnum):
    MINIMUM = "minimum"
    PREFERRED = "preferred"
    RESPONSIBILITY = "responsibility"


# Order matters: first match wins, so anything qualified by "preferred" or
# "desirable" is listed before the bare form it contains.
#
# The healthcare, education and public-sector conventions below are not padding.
# A nursing post advertises "Essential criteria", a school publishes a "Person
# specification", a public body lists "Selection criteria" — and a parser that
# only knows "Minimum qualifications" reads all three as prose and finds nothing
# to score. Four of five test professions failed on exactly this.
for _pattern, _tier in (
    # Preferred first, so "preferred qualifications" never falls to a minimum rule.
    (r"preferred qualification", Tier.PREFERRED),
    (r"preferred requirement", Tier.PREFERRED),
    # `^desirable` rather than `^desirable$`, so "Desirable requirements" and
    # "Desirable skills" cannot fall through to a MINIMUM rule below.
    (r"^desirable", Tier.PREFERRED),
    (r"^preferred$", Tier.PREFERRED),
    (r"nice to have", Tier.PREFERRED),
    (r"bonus points", Tier.PREFERRED),
    # Minimum and essential.
    #
    # An unrecognised heading does not degrade, it DISCARDS: the lines under it
    # are prose to this parser, so the block vanishes while cv_ingest_jd still
    # reports a count made of boilerplate matched elsewhere. Three independent
    # testers hit that from three professions — "Essential requirements" lost
    # four of six essentials, and "Essential - you will not be shortlisted
    # without these" lost all of them.
    #
    # So `^essential` anchored at the start rather than `^essential$`, and the
    # contractions are spelled out both ways: `we'?re` matches "we're" and the
    # apostrophe-less typo, and NOT "we are", which is how half of postings
    # write it. That one character cost a posting its entire requirements
    # section and reported an empty scorecard as though the corpus were at fault.
    (r"minimum qualification", Tier.MINIMUM),
    (r"basic qualification", Tier.MINIMUM),
    (r"^qualifications", Tier.MINIMUM),
    (r"minimum requirement", Tier.MINIMUM),
    (r"^require(ments?|d)\b", Tier.MINIMUM),
    (r"^essential", Tier.MINIMUM),
    (r"must have", Tier.MINIMUM),
    (r"you(?:'ll| will| ?ll)? have\b", Tier.MINIMUM),
    (r"key skills", Tier.MINIMUM),
    (r"skills required", Tier.MINIMUM),
    (r"person specification", Tier.MINIMUM),
    (r"selection criteria", Tier.MINIMUM),
    (r"skills and experience", Tier.MINIMUM),
    (r"about you", Tier.MINIMUM),
    (r"what we(?:'re| are| ?re) looking for", Tier.MINIMUM),
    (r"what we need", Tier.MINIMUM),
    (r"who you are", Tier.MINIMUM),
    (r"what you(?:'ll| will| ?ll) need", Tier.MINIMUM),
    # Responsibilities.
    (r"responsibilit", Tier.RESPONSIBILITY),
    (r"key duties", Tier.RESPONSIBILITY),
    (r"main duties", Tier.RESPONSIBILITY),
    (r"^duties", Tier.RESPONSIBILITY),
    (r"what you(?:'ll| will| ?ll) do", Tier.RESPONSIBILITY),
    (r"^the role$", Tier.RESPONSIBILITY),
    (r"^description", Tier.RESPONSIBILITY),
):
    _HEADINGS.append((_pattern, _tier))

# Headings that end a scored section without starting a new one.
_STOP_HEADINGS = (
    r"about the job",
    r"about (us|the team|google|apple)",
    r"equal opportunit",
    r"benefits",
    r"how we hire",
    r"to all recruitment agencies",
    r"information collected",
)


@dataclass
class Requirement:
    text: str
    tier: Tier
    is_hard_filter: bool = False
    is_degree: bool = False
    years_required: int | None = None


@dataclass
class JobDescription:
    requirements: list[Requirement] = field(default_factory=list)
    title: str | None = None
    source: str | None = None
    raw: str = ""

    def by_tier(self, tier: Tier) -> list[Requirement]:
        return [r for r in self.requirements if r.tier is tier]


def _heading_tier(line: str) -> Tier | None:
    lowered = line.strip().lower().rstrip(":")
    if len(lowered) > 60:
        return None
    for pattern, tier in _HEADINGS:
        if re.search(pattern, lowered):
            return tier
    return None


def _is_stop_heading(line: str) -> bool:
    lowered = line.strip().lower()
    if len(lowered) > 70:
        return False
    return any(re.search(p, lowered) for p in _STOP_HEADINGS)


def _classify(text: str, tier: Tier) -> Requirement:
    lowered = text.lower()

    years = None
    match = _YEARS.search(text)
    if match:
        years = int(match.group(1))

    hard = any(re.search(p, lowered) for p in _HARD_FILTER_PATTERNS)
    # A minimum years threshold is an eligibility bar, not a scored preference.
    if years is not None and tier is Tier.MINIMUM:
        hard = True

    return Requirement(
        text=text,
        tier=tier,
        is_hard_filter=hard,
        is_degree=any(re.search(p, lowered) for p in _DEGREE_PATTERNS),
        years_required=years,
    )


def parse_jd(text: str, *, title: str | None = None, source: str | None = None) -> JobDescription:
    """Parse a posting. Pasted text always works and needs no network."""
    jd = JobDescription(title=title, source=source, raw=text)

    current: Tier | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        tier = _heading_tier(stripped)
        if tier is not None:
            current = tier
            continue

        if _is_stop_heading(stripped):
            current = None
            # A standalone hard-filter statement can appear outside any section —
            # the right-to-work line usually sits above the headings entirely.
            continue

        if current is not None:
            bullet = _BULLET.match(line)
            if bullet:
                jd.requirements.append(_classify(bullet.group(1), current))
                continue

            # A line inside an open section counts even with no bullet glyph.
            # Requiring one was a real defect: Apple's own job API returns
            # qualifications as plain newline-separated lines, so the parser
            # found NOTHING in a genuine posting and then advised the user to
            # check that the headings had survived the copy — wrong advice, and
            # the headings were the one part that was fine.
            #
            # TWO bounds, and both are load-bearing.
            #
            # The SECTION bound is the important one. Only a qualifications list
            # takes unbulleted lines, because a qualifications section is a list
            # by convention while `Description` is prose by convention — and
            # `Description` opens a RESPONSIBILITY section here, so without this
            # the first cut of the fix scored Apple's marketing copy as
            # requirements. That is precisely what this module's own docstring
            # forbids: inventing criteria the employer never set, then reporting
            # gaps against them. A responsibilities list that really is a list
            # still arrives through the bullet branch above.
            #
            # The LENGTH bound catches the rest: some postings open a
            # qualifications section with a sentence of prose, and a requirement
            # is a short clause rather than a paragraph.
            if current in _LIST_SECTIONS and len(stripped) <= _MAX_REQUIREMENT:
                jd.requirements.append(_classify(stripped, current))
            continue

        # Outside a scored section, keep only lines that are plainly eligibility
        # statements. Everything else is prose and is not a requirement.
        if current is None:
            lowered = stripped.lower()
            if any(re.search(p, lowered) for p in _HARD_FILTER_PATTERNS) and len(stripped) < 400:
                jd.requirements.append(
                    Requirement(text=stripped, tier=Tier.MINIMUM, is_hard_filter=True)
                )

    return jd


__all__ = ["JobDescription", "Requirement", "Tier", "parse_jd"]
