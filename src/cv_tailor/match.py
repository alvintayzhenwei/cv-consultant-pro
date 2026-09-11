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
    #: The evidence shown on the scorecard, capped so a row stays readable.
    evidence_ids: list[str] = field(default_factory=list)
    #: Every bullet that actually supports this requirement, uncapped.
    #:
    #: Kept separate because the two lists answer different questions, and
    #: conflating them was a real bug: relevance read the CAPPED list, so a
    #: bullet that genuinely matched could be left off the CV purely because it
    #: came fifth in something formatted for a human to read. A presentation
    #: limit must never decide content.
    all_evidence_ids: list[str] = field(default_factory=list)
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
        """How many requirements each bullet helped satisfy — drives selection.

        Reads the UNCAPPED list. See Row.all_evidence_ids for why.
        """
        counts: dict[str, int] = {}
        for row in self.rows + self.hard_filters:
            for bullet_id in row.all_evidence_ids:
                counts[bullet_id] = counts.get(bullet_id, 0) + 1
        return counts


def _tokens(text: str) -> set[str]:
    """Words worth matching on.

    The character class admits '.', '/' and '-' so that node.js, ci/cd and
    hands-on survive as single tokens. They must be stripped at the EDGES
    though: nearly every requirement line ends in a full stop, and without this
    the last word of every requirement tokenised as 'enablement.' and matched
    nothing. That silently degraded every score in the first real run.
    """
    out: set[str] = set()
    for raw in _WORD.findall(text.lower()):
        word = raw.strip("./-")
        if word and word not in _STOPWORDS and len(word) > 2:
            out.add(word)
    return out


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
    """Calendar time the corpus evidences for a requirement — the UNION of spans.

    The first version took the longest single role, which reported "4.9 years"
    for someone with twelve years of continuous history, because three concurrent
    titles at one employer each looked short. Summing them instead would
    double-count the overlap and claim more than the calendar allows. Union does
    neither: concurrent roles collapse, gapped ones add.

    Still reported alongside the threshold rather than compared to it. Whether a
    span clears a bar is the reader's call.
    """
    now = _today()
    spans: list[tuple[int, int]] = []
    for role in corpus.roles:
        touches = any(t.lower() in req_tokens for t in role.tags) or any(
            _bullet_hit(b, req_tokens, "") > 0 for b in role.bullets
        )
        if not touches or role.start is None:
            continue
        end = now if role.is_current else role.end
        if end is None:
            continue
        spans.append((role.start.year * 12 + role.start.month, end.year * 12 + end.month))

    if not spans:
        return None

    spans.sort()
    months = 0
    cur_start, cur_end = spans[0]
    for start, end in spans[1:]:
        if start <= cur_end:  # overlapping or contiguous
            cur_end = max(cur_end, end)
        else:
            months += cur_end - cur_start
            cur_start, cur_end = start, end
    months += cur_end - cur_start
    return round(months / 12, 1) if months else None


# A requirement phrased "A and B" is two demands. Splitting on these keeps the
# original wording for display while scoring each half, so half a match cannot
# read as a whole one.
_SPLIT = re.compile(r"\bboth\b|(?:,\s*)?\band\b|;|(?:,\s*)?\bas well as\b", re.IGNORECASE)


def _parts(text: str) -> list[str]:
    """Split a compound requirement into the demands it actually makes."""
    pieces = [p.strip(" ,.;") for p in _SPLIT.split(text)]
    substantive = [p for p in pieces if len(_tokens(p)) >= 2]
    return substantive if len(substantive) > 1 else [text]


def score(jd: JobDescription, corpus: Corpus) -> Scorecard:
    card = Scorecard()

    for req in jd.requirements:
        req_tokens = _tokens(req.text)

        # A degree is answered by the education section, not by work bullets.
        # Citing bullets here produced nonsense — two unrelated delivery entries
        # offered as evidence of a Computer Science degree.
        if req.is_degree:
            card.rows.append(_degree_row(req, corpus))
            continue

        # An eligibility filter — visa, citizenship, location, language — is not
        # something a bullet can evidence. Matching one against the corpus found
        # "Singapore" in an unrelated role and called it proof of a right to work.
        if req.is_hard_filter and req.years_required is None:
            card.hard_filters.append(
                Row(
                    requirement=req,
                    verdict=Verdict.PARTIAL,
                    note="eligibility — answer this yourself; no corpus entry can evidence it",
                )
            )
            continue

        part_results = [_score_part(part, corpus) for part in _parts(req.text)]
        verdict = min((r[0] for r in part_results), key=_RANK.__getitem__)

        evidence: list[str] = []
        skill_names: list[str] = []
        for _v, ev, names in part_results:
            evidence.extend(ev)
            skill_names.extend(names)
        evidence = list(dict.fromkeys(evidence))
        skill_names = list(dict.fromkeys(skill_names))
        supported = verdict is not Verdict.GAP

        row = Row(
            requirement=req,
            verdict=verdict,
            evidence_ids=evidence[:EVIDENCE_SHOWN] if supported else [],
            all_evidence_ids=evidence if supported else [],
            skill_names=skill_names,
            evidenced_years=_evidenced_years(corpus, req_tokens) if req.years_required else None,
        )
        if len(part_results) > 1 and verdict is not Verdict.STRONG:
            row.note = "compound requirement — scored by its weakest part"

        if req.is_hard_filter:
            card.hard_filters.append(row)
        else:
            card.rows.append(row)

    # Every requirement appears exactly once overall; a caller wanting the full
    # list iterates rows + hard_filters.
    return card


_RANK = {Verdict.GAP: 0, Verdict.PARTIAL: 1, Verdict.STRONG: 2}

# How many evidence ids a scorecard row shows before it stops being scannable.
# A DISPLAY limit only — see Row.all_evidence_ids.
EVIDENCE_SHOWN = 4


def _degree_row(req: Requirement, corpus: Corpus) -> Row:
    if not corpus.education:
        return Row(requirement=req, verdict=Verdict.GAP, note="no education recorded in the corpus")
    held = corpus.education[0]
    text = req.text.lower()
    wants_post_grad = "master" in text or "phd" in text or "ph.d" in text
    has_post_grad = any(
        "master" in e.qualification.lower() or "phd" in e.qualification.lower()
        for e in corpus.education
    )
    verdict = Verdict.STRONG
    if wants_post_grad and not has_post_grad:
        verdict = Verdict.PARTIAL if "or equivalent" in text or "bachelor" in text else Verdict.GAP
    return Row(
        requirement=req,
        verdict=verdict,
        note=f"{held.qualification} - {held.institution}",
    )


def _score_part(part: str, corpus: Corpus) -> tuple[Verdict, list[str], list[str]]:
    tokens = _tokens(part)

    matched_skills = [s for s in corpus.skills if _skill_matches(s, part, tokens)]
    skill_evidence: list[str] = []
    for skill in matched_skills:
        skill_evidence.extend(skill.evidence_refs)

    hits = sorted(
        ((bullet, _bullet_hit(bullet, tokens, part)) for bullet in corpus.all_bullets()),
        key=lambda pair: pair[1],
        reverse=True,
    )
    strong_hits = [b for b, s in hits if s >= 3]
    weak_hits = [b for b, s in hits if 0 < s < 3]

    evidence = list(dict.fromkeys(skill_evidence + [b.id for b in strong_hits]))
    names = [s.name for s in matched_skills]

    if matched_skills and skill_evidence:
        return Verdict.STRONG, evidence, names
    if len(strong_hits) >= 2:
        return Verdict.STRONG, evidence, names
    if strong_hits or weak_hits:
        return Verdict.PARTIAL, evidence or [b.id for b in weak_hits[:2]], names
    return Verdict.GAP, [], names


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
