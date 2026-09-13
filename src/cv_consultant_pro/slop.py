"""Phrases that say nothing, and the shape a bullet has to have.

Two checks, run at different moments on purpose.

The blocklist runs at CORPUS VALIDATION as well as at render. Slop written into
the corpus renders faithfully as slop — the renderer is select-only, so it has no
way to improve a bad sentence, and catching it at render time means telling you
about it when you can no longer fix it cheaply.

The shape check is advisory rather than fatal. Not every true statement is an
accomplishment with a measurable outcome, and failing a build over that would
push people toward inventing one — which is the opposite of the point.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: Phrases that occupy space without making a claim. Each one is here because it
#: can be deleted from a sentence without changing what the sentence asserts.
BLOCKED = (
    "results-driven",
    "results driven",
    "detail-oriented",
    "detail oriented",
    "passionate about",
    "proven track record",
    "track record of success",
    "dynamic professional",
    "seasoned professional",
    "team player",
    "self-starter",
    "go-getter",
    "think outside the box",
    "leveraged synergies",
    "synergies",
    "value-add",
    "best-in-class",
    "world-class",
    "cutting-edge",
    "state-of-the-art",
    "game-changing",
    "wide range of",
    "various stakeholders",
    "spearheaded",
    "orchestrated a paradigm",
    "responsible for",
    "duties included",
    "helped with",
    "assisted with",
    "worked on",
    "involved in",
    "exposure to",
    "hit the ground running",
    "wearing many hats",
    "in today's fast-paced",
    "excellent communication skills",
    "strong work ethic",
)

#: Verbs that describe presence rather than contribution. A bullet opening with
#: one of these is usually a duty, not an accomplishment.
_WEAK_OPENERS = (
    "responsible",
    "helped",
    "assisted",
    "worked",
    "involved",
    "participated",
    "supported",
    "contributed",
    "tasked",
)


@dataclass(frozen=True)
class SlopFinding:
    ref: str
    phrase: str
    where: str

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"{self.ref}: {self.where} contains {self.phrase!r}"


def find_blocked(text: str, *, ref: str, where: str = "text") -> list[SlopFinding]:
    """Blocked phrases in one piece of text.

    Matched on word boundaries so that a legitimate compound — "wide ranges of
    motion" in a physiotherapy CV, say — is not caught by "wide range of".
    """
    lowered = text.lower()
    found: list[SlopFinding] = []
    for phrase in BLOCKED:
        pattern = r"(?<![a-z])" + re.escape(phrase) + r"(?![a-z])"
        if re.search(pattern, lowered):
            found.append(SlopFinding(ref=ref, phrase=phrase, where=where))
    return found


def weak_opening(claim: str) -> str | None:
    """The opening word, when it describes presence rather than contribution.

    Advisory. "Supported the year-end audit" may be exactly true and worth
    saying; the point is to show it to the author while the corpus is still
    being written, not to refuse it.
    """
    first = re.split(r"[^a-zA-Z]+", claim.strip(), maxsplit=1)
    if not first or not first[0]:
        return None
    word = first[0].lower()
    return word if word in _WEAK_OPENERS else None


def has_outcome(claim: str) -> bool:
    """Whether a claim states a result rather than only an activity.

    Deliberately crude: a number, a percentage, a direction of change, or a
    completion word. It informs a warning and never a refusal, because a precise
    rule here would be wrong more often than it was right.
    """
    lowered = claim.lower()
    if re.search(r"\d", lowered):
        return True
    return any(
        word in lowered
        for word in (
            "cut ", "raised", "reduced", "increased", "grew", "halved", "doubled",
            "removed", "eliminated", "shipped", "delivered", "launched", "won",
            "recovered", "improved", "brought", "took ", "led ", "built ", "cleared",
        )
    )


__all__ = ["BLOCKED", "SlopFinding", "find_blocked", "has_outcome", "weak_opening"]
