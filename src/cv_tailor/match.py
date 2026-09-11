"""Score corpus evidence against a posting's requirements.

Deterministic on purpose. No model call decides whether you have done something —
a declared skill alias or a tagged bullet does. That makes every verdict
explainable ("this scored strong because these two bullets carry these tags"),
reproducible, and free.

The cost is bluntness: this will miss a match a careful human reader would see,
and it cannot judge depth. It is a first pass that tells you where to look, not
a replacement for reading the posting.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from .corpus import Bullet, Corpus, YearMonth
from .jd import JobDescription, Requirement

_WORD = re.compile(r"[a-z0-9+#./-]+")

# Words that carry no signal in a job posting. Without this, "experience" and
# "with" match everything and every requirement scores strong.
_STOPWORDS = frozenset(
    ["a", "an", "and", "or", "the", "of", "in", "on", "to", "for", "with", "using", "via", "by", "at", "as", "is", "are", "be", "been", "being", "your", "you", "our", "we", "us", "they", "it", "its", "this", "that", "these", "those", "from", "into", "over", "under", "experience", "experiences", "experienced", "work", "working", "works", "ability", "able", "across", "strong", "proven", "demonstrated", "excellent", "good", "deep", "solid", "hands-on", "hands", "on", "including", "include", "includes", "such", "e.g", "eg", "i.e", "ie", "etc", "other", "others", "related", "field", "fields", "years", "year", "plus", "preferred", "minimum", "qualification", "qualifications", "role", "roles", "team", "teams", "new", "more", "most", "both", "all", "any", "some", "who", "what", "how", "when", "will", "would", "can", "could", "should", "may", "might", "must", "have", "has", "had", "do", "does", "did", "level", "senior", "junior", "mid", "lead", "leading", "build", "building", "built", "design", "designing", "designed", "develop", "developing", "developed"]
)


class Verdict(str, Enum):
    STRONG = "strong"
    PARTIAL = "partial"
    GAP = "gap"


@dataclass
class Row:
    requirement: Requirement
    verdict: Verdict
    evidence_ids: list[str] = field(default_factory=list)
    skill_names: list[str] = field(default_factory=list)
    evidenced_years: float | None = None
    note: str | None = None


@dataclass
class Scorecard:
    rows: list[Row] = field(default_factory=list)
    hard_filters: list[Row] = field(default_factory=list)

    def by_verdict(self, verdict: Verdict) -> list[Row]:
        return [r for r in self.rows if r.verdict is verdict]

    def relevance(self) -> dict[str, int]:
        """How many requirements each bullet helped satisfy — drives selection."""
        counts: dict[str, int] = {}
        for row in self.rows + self.hard_filters:
            for bullet_id in row.evidence_ids:
                counts[bullet_id] = counts.get(bullet_id, 0) + 1
        return counts


def _tokens(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOPWORDS and len(w) > 2}


def _phrase_in(needle: str, haystack: str) -> bool:
    """Whole-phrase containment, so 'ADK' does not match inside 'adkins'."""
    pattern = r"(?<![a-z0-9])" + re.escape(needle.lower()) + r"(?![a-z0-9])"
    return re.search(pattern, haystack.lower()) is not None


def _bullet_hit(bullet: Bullet, req_tokens: set[str], req_text: str) -> int:
    """A crude relevance count: shared tags weigh more than shared prose."""
    score = 0
    for tag in bullet.tags:
        if tag.lower() in req_tokens or _phrase_in(tag.replace("-", " "), req_text):
            score += 2
    overlap = _tokens(f"{bullet.claim} {bullet.mechanism}") & req_tokens
    score += min(len(overlap), 3)
    return score


def _today() -> YearMonth:
    now = datetime.now(tz=UTC)
    return YearMonth(now.year, now.month)


def _evidenced_years(corpus: Corpus, req_tokens: set[str]) -> float | None:
    """Total months spanned by roles whose tags or bullets touch the requirement.

    Reported alongside the posting's threshold rather than compared to it. The
    engine says what the corpus evidences; whether that clears the bar is the
    reader's call, because overlapping roles make any automatic sum arguable.
    """
    now = _today()
    months = 0
    for role in corpus.roles:
        touches = any(t.lower() in req_tokens for t in role.tags) or any(
            _bullet_hit(b, req_tokens, "") > 0 for b in role.bullets
        )
        if not touches:
            continue
        span = role.months(now=now)
        if span:
            months = max(months, span)
    return round(months / 12, 1) if months else None


def score(jd: JobDescription, corpus: Corpus) -> Scorecard:
    card = Scorecard()

    for req in jd.requirements:
        req_tokens = _tokens(req.text)

        matched_skills = [s for s in corpus.skills if _skill_matches(s, req.text, req_tokens)]
        skill_evidence: list[str] = []
        for skill in matched_skills:
            skill_evidence.extend(skill.evidence_refs)

        hits = sorted(
            (
                (bullet, _bullet_hit(bullet, req_tokens, req.text))
                for bullet in corpus.all_bullets()
            ),
            key=lambda pair: pair[1],
            reverse=True,
        )
        strong_hits = [b for b, s in hits if s >= 3]
        weak_hits = [b for b, s in hits if 0 < s < 3]

        evidence = list(dict.fromkeys(skill_evidence + [b.id for b in strong_hits]))[:4]

        if skill_evidence and matched_skills or len(strong_hits) >= 2:
            verdict = Verdict.STRONG
        elif strong_hits or weak_hits:
            verdict = Verdict.PARTIAL
            evidence = evidence or [b.id for b in weak_hits[:2]]
        else:
            verdict = Verdict.GAP
            evidence = []

        row = Row(
            requirement=req,
            verdict=verdict,
            evidence_ids=evidence,
            skill_names=[s.name for s in matched_skills],
            evidenced_years=_evidenced_years(corpus, req_tokens) if req.years_required else None,
        )

        if req.is_degree and verdict is Verdict.GAP and corpus.education:
            row.note = "check against the education section by hand — degrees are not tagged"

        if req.is_hard_filter:
            card.hard_filters.append(row)
        else:
            card.rows.append(row)

    # Every requirement appears exactly once overall; a caller wanting the full
    # list iterates rows + hard_filters.
    return card


def _skill_matches(skill, req_text: str, req_tokens: set[str]) -> bool:
    """A skill matches only under a name or alias the corpus already declares.

    This is the vocabulary bridge, and the reason it is narrow: an undeclared
    phrasing must not be adopted into a CV, so it must not score here either.
    """
    if not skill.evidence_refs:
        return False
    for name in [skill.name, *skill.aliases]:
        if _phrase_in(name, req_text):
            return True
        parts = _tokens(name)
        if parts and parts <= req_tokens and len(parts) > 1:
            return True
    return False


__all__ = ["Row", "Scorecard", "Verdict", "score"]
