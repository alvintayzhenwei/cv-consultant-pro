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
from enum import Enum

_BULLET = re.compile(r"^\s*(?:[-•*]|\d+[.)])\s+(.*\S)\s*$")
_YEARS = re.compile(r"\b(\d{1,2})\s*\+?\s*(?:or more\s*)?years?\b", re.IGNORECASE)

# Section headings, matched loosely because postings punctuate them freely.
_HEADINGS: list[tuple[str, Tier]] = []

# Lines that disqualify rather than merely score. Failing one is not a low score,
# it is a closed door — so they are surfaced apart from the scored rows.
_HARD_FILTER_PATTERNS = (
    r"right to work",
    r"work authorisation|work authorization",
    r"sponsor(ship)?\b",
    r"visa\b",
    r"citizen(ship)?\b",
    r"security clearance",
    r"fluen(t|cy) in",
    r"native (speaker|proficiency)",
    r"must be (located|based)",
    r"relocat",
)

_DEGREE_PATTERNS = (
    r"bachelor'?s?\b",
    r"master'?s?\b",
    r"\bph\.?d\b",
    r"\bdegree\b",
)


class Tier(str, Enum):
    MINIMUM = "minimum"
    PREFERRED = "preferred"
    RESPONSIBILITY = "responsibility"


for _pattern, _tier in (
    (r"minimum qualification", Tier.MINIMUM),
    (r"basic qualification", Tier.MINIMUM),
    (r"^qualifications", Tier.MINIMUM),
    (r"minimum requirement", Tier.MINIMUM),
    (r"what you'?ll need", Tier.MINIMUM),
    (r"preferred qualification", Tier.PREFERRED),
    (r"preferred requirement", Tier.PREFERRED),
    (r"nice to have", Tier.PREFERRED),
    (r"bonus points", Tier.PREFERRED),
    (r"responsibilit", Tier.RESPONSIBILITY),
    (r"what you'?ll do", Tier.RESPONSIBILITY),
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

        bullet = _BULLET.match(line)
        if bullet and current is not None:
            jd.requirements.append(_classify(bullet.group(1), current))
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
