"""The interview: ten questions, an authenticity gate, and evidence recovery.

The purpose is not assessment. It is recovering capability the corpus does not
know about, because people under-record themselves — a fact this project ran
into head-first when a career's worth of evidence turned out to be missing from
its owner's own website.

So the loop is: ask, capture what the user said verbatim, notice a fact the
corpus lacks, propose it, and write it only once the user confirms. Three things
keep that honest, and all three are enforced here rather than asked for:

  * the gate — no question is served until the user has declared the answers
    will be their own;
  * verbatim capture — only text the user typed can become a proposal, and
    `record_answer` has no parameter through which an agent could submit its own
    wording instead;
  * confirmation — a proposal is inert until `confirm` is called on it.

A coached suggestion from the host agent is welcome and useful, and it has no
path into the corpus at all.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum

from .corpus import Corpus
from .match import Scorecard, Verdict

#: Ten, not twenty. Twenty is a lot to sit through in a chat, and the last ten
#: are always the least targeted — so this spends every slot on a gap or a
#: partial, where the chance of recovering unrecorded evidence is highest.
QUESTION_COUNT = 10

AUTHENTICITY_NOTICE = (
    "Answer from your own experience only. Do not ask an AI to write these "
    "answers for you, and do not paste one in.\n\n"
    "Everything you say here can become a line on your CV. An answer you did "
    "not live is a claim you cannot defend in the room — and it does not stop "
    "at this application. It is written into your corpus and reused by every CV "
    "you generate afterwards."
)

ELABORATE_PROMPT = (
    "Answer in more detail than whatever is already on record. What is recorded is "
    "the part that needs no interview; this is for what is not — what you actually "
    "did, what you decided, and what it changed. A sentence repeating the summary "
    "above recovers nothing."
)

COACHING_DISCLAIMER = (
    "This is a suggestion about the question, not a fact about you. AI guidance "
    "is often wrong on specifics, and confidently so. Verify anything you intend "
    "to say in an interview — the person across the table will."
)


class Preparedness(StrEnum):
    PREPARED = "prepared"
    UNPREPARED = "unprepared"


@dataclass
class Question:
    id: str
    text: str
    #: The requirement this probes, verbatim from the posting.
    requirement: str
    verdict: Verdict
    preparedness: Preparedness
    #: The corpus position to answer from, when one exists.
    position_id: str | None = None
    #: What this question is really testing, for the agent to relay.
    probes: str = ""


@dataclass
class Proposal:
    """A corpus entry drawn from something the user said. Inert until confirmed."""

    id: str
    question_id: str
    #: The user's own words, unedited. The provenance of everything below.
    user_said: str
    claim: str
    role_id: str | None
    tags: list[str] = field(default_factory=list)
    #: A figure the user stated, if any. Never inferred.
    metric_value: str | None = None
    confirmed: bool = False
    verified: bool = False


@dataclass
class Answer:
    question_id: str
    user_said: str
    #: True when the user's reply says they have not done this. Recorded as
    #: deliberately as a strength — a confirmed gap is better information than
    #: an unconfirmed one, and it must never be softened on the CV.
    confirms_gap: bool = False
    proposals: list[Proposal] = field(default_factory=list)


class InterviewError(Exception):
    """The interview was used out of order."""


_GAP_PHRASES = (
    "i haven't", "i have not", "i've never", "i have never", "never done",
    "no experience", "not really", "not something i", "haven't done",
    "i don't have", "i do not have", "only shipped one", "didn't tune",
    "did not tune", "not my area", "someone else did", "i wasn't involved",
)

_NUMBER = re.compile(
    r"\b\d[\d,.]*\s*(?:%|percent|per cent|k\b|m\b|people|users|staff|students|"
    r"patients|customers|teams?|days?|weeks?|months?|years?|hours?|minutes?)?",
    re.IGNORECASE,
)

#: The "1." and "2)" a person types when answering several things at once.
#:
#: Stripped before any figure is looked for, because a bare digit satisfies
#: _NUMBER and an answer opening "1. My site is a playground…" offered **1.** as
#: the bullet's measured value. Making the unit mandatory instead was tried and
#: is worse: it also discards "12 nurses a year", since the unit list is a
#: curated allowlist and cannot hold every noun. This targets the actual defect
#: and leaves real figures alone.
_LIST_MARKER = re.compile(r"^[ \t]*\d+[.)]\s+", re.MULTILINE)

#: Denials carrying no first-person verb, which the phrase list above cannot see.
#: "No ML training or fine-tuning, only applied AI via LLM" is as plain an
#: admission as English offers and matched none of the seventeen — so it was
#: recorded as evidence and offered back as a bullet to put on a CV.
#:
#: Each is anchored so it cannot swallow an achievement. "No customer-visible
#: downtime across eighteen months of weekly releases" opens on the same word and
#: is a claim, not a confession, so a bare leading "no" counts only when the whole
#: answer is SHORT: someone conceding a gap says so briefly and stops.
_GAP_PATTERNS = (
    re.compile(
        r"\bno\b[\w\s-]{0,24}\b(experience|training|exposure|background|involvement)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bnever\b\s+(done|used|worked|built|led|managed|shipped|run)\b", re.IGNORECASE),
    re.compile(r"\bnot\s+(something|part of|my|an area)\b", re.IGNORECASE),
    re.compile(r"^(no|none|nope)\b.{0,90}$", re.IGNORECASE | re.DOTALL),
)


def _gap_admission(text: str) -> bool:
    lowered = text.lower()
    if any(phrase in lowered for phrase in _GAP_PHRASES):
        return True
    return any(pattern.search(text.strip()) for pattern in _GAP_PATTERNS)


def _unpack(item) -> tuple[str, Verdict, list[str], list[str]]:
    """Accept a scorecard Row, or the bare (text, verdict) pair.

    The pair form is what the ranking tests use, and it carries no evidence, so
    it can only ever produce the blunt note. A Row knows whether anything in the
    corpus actually supports the requirement and whether a declared skill
    matched its phrasing — which is the difference between a truthful probe and
    a reassuring one.
    """
    if isinstance(item, tuple):
        text, verdict = item
        return text, verdict, [], []
    return (
        item.requirement.text,
        item.verdict,
        list(item.all_evidence_ids),
        list(item.skill_names),
    )


def build_questions(
    jd_requirements,
    corpus: Corpus,
    *,
    limit: int = QUESTION_COUNT,
) -> list[Question]:
    """Ten questions, weighted toward what the corpus cannot yet answer.

    Gaps first, then partials, then the strongest matches — because a question
    about a requirement you already evidence is a rehearsal, while a question
    about one you do not is the one that might recover something.
    """
    order = {Verdict.GAP: 0, Verdict.PARTIAL: 1, Verdict.STRONG: 2}
    unpacked = [_unpack(item) for item in jd_requirements]
    ranked = sorted(unpacked, key=lambda row: order[row[1]])

    positions = {p.id: p for p in corpus.positions}
    questions: list[Question] = []

    for index, (requirement, verdict, evidence, skills) in enumerate(ranked[:limit], start=1):
        position = _closest_position(requirement, corpus)
        questions.append(
            Question(
                id=f"q{index}",
                text=_phrase_as_question(requirement),
                requirement=requirement,
                verdict=verdict,
                preparedness=(
                    Preparedness.PREPARED if position else Preparedness.UNPREPARED
                ),
                position_id=position.id if position else None,
                probes=_probe_note(verdict, evidence, skills),
            )
        )
        if position:
            positions.pop(position.id, None)
    return questions


def _probe_note(verdict: Verdict, evidence: list[str] | None = None, skills: list[str] | None = None) -> str:
    evidence = evidence or []
    skills = skills or []

    if verdict is Verdict.GAP:
        # A GAP is not proof of an empty corpus, and saying so sends the user off
        # to re-describe work they have already recorded. Two other causes are
        # far commoner: a compound line failing on its weakest part while the
        # corpus answers the rest, and a line missing only because no declared
        # skill uses the posting's words. The second is a one-line fix in the
        # corpus, not an interview answer — so it has to be said, not hidden
        # behind a message about missing experience.
        if evidence and not skills:
            return (
                f"{len(evidence)} bullets in the corpus support this, but no declared "
                "skill matches the posting's phrasing, so it scores as a gap. If you do "
                "have this, the fix is usually an alias on an existing skill rather than "
                "a new answer. Say so if the wording is the only thing missing."
            )
        if evidence:
            return (
                f"Scored a gap, yet {len(evidence)} bullets support part of it — most "
                "likely a compound requirement failing on one half. Answer the half the "
                "corpus cannot."
            )
        return (
            "The corpus holds no evidence for this. If you have done it and simply "
            "never recorded it, this is where it gets recovered."
        )
    if verdict is Verdict.PARTIAL:
        if evidence and not skills:
            return (
                "Partly evidenced by bullets, but no declared skill matches the posting's "
                "wording — an alias may be worth more here than a new answer."
            )
        return "Partly evidenced. A specific may be missing rather than the whole thing."
    return "Already evidenced. Worth rehearsing rather than researching."


def _closest_position(requirement: str, corpus: Corpus):
    """The recorded position nearest this requirement, by shared vocabulary."""
    words = {w for w in re.findall(r"[a-z]{4,}", requirement.lower())}
    best, best_score = None, 0
    for position in corpus.positions:
        haystack = f"{position.topic} {position.question}".lower()
        overlap = len({w for w in words if w in haystack})
        if overlap > best_score:
            best, best_score = position, overlap
    return best if best_score >= 2 else None


def _phrase_as_question(requirement: str) -> str:
    """Turn a requirement into something a person would actually be asked.

    Deliberately plain. A requirement rewritten into interview-speak reads as
    generated filler, and the point is to prompt a memory rather than to perform.
    """
    text = requirement.strip().rstrip(".")
    text = re.sub(r"^(experience|demonstrable experience|evidence)\s+(of|with|in|leading)\s+",
                  "", text, flags=re.IGNORECASE)
    text = re.sub(r"^(strong|proven|working)\s+", "", text, flags=re.IGNORECASE)
    text = text[:1].lower() + text[1:] if text else text
    return f"Tell me about your experience with {text}."


class Interview:
    """One interview session. Holds the gate, the questions and the proposals."""

    def __init__(self, questions: list[Question]) -> None:
        self.questions = questions
        self.acknowledged = False
        self.answers: dict[str, Answer] = {}
        self._proposals: dict[str, Proposal] = {}
        self._counter = 0

    # ── the gate ────────────────────────────────────────────────────────────
    def notice(self) -> str:
        return AUTHENTICITY_NOTICE

    def acknowledge(self) -> None:
        self.acknowledged = True

    def next_question(self) -> Question | None:
        if not self.acknowledged:
            raise InterviewError(
                "the authenticity notice has not been acknowledged. Show the user "
                "interview.notice() and have them agree before any question is served."
            )
        for question in self.questions:
            if question.id not in self.answers:
                return question
        return None

    # ── capture ─────────────────────────────────────────────────────────────
    def record_answer(self, question_id: str, user_said: str) -> Answer:
        """Record what the user typed, and propose evidence drawn from it.

        `user_said` is the user's own text. There is deliberately no second
        parameter through which an agent could submit a rewritten or improved
        version — the absence is the guarantee.
        """
        if not self.acknowledged:
            raise InterviewError(
                "cannot record an answer before the authenticity notice is acknowledged"
            )
        question = next((q for q in self.questions if q.id == question_id), None)
        if question is None:
            raise InterviewError(f"no such question: {question_id}")
        if not user_said.strip():
            raise InterviewError("an empty answer records nothing")

        answer = Answer(
            question_id=question_id,
            user_said=user_said.strip(),
            confirms_gap=_gap_admission(user_said),
        )

        if not answer.confirms_gap:
            proposal = self._propose(question, answer.user_said)
            if proposal is not None:
                answer.proposals.append(proposal)
                self._proposals[proposal.id] = proposal

        self.answers[question_id] = answer
        return answer

    def _propose(self, question: Question, user_said: str) -> Proposal | None:
        """Draft a corpus entry from the user's words. Never from the agent's."""
        self._counter += 1
        claim = user_said.strip()
        if len(claim) > 240:
            # Too long to be a bullet. Keep the whole thing as provenance and let
            # the user shorten it at confirmation — truncating here would put
            # words in their mouth by omission.
            claim = claim[:240].rsplit(" ", 1)[0]
        # Read the figure out of the CLAIM, never out of the whole answer. The
        # answer-wide search bound a number from one sentence to a claim
        # truncated before it ever reached that sentence: a 95% accuracy figure
        # landed on a claim about two unrelated tools, and a two-month launch
        # figure on a claim about ideation.
        numbers = _NUMBER.findall(_LIST_MARKER.sub("", claim))
        return Proposal(
            id=f"p{self._counter}",
            question_id=question.id,
            user_said=user_said,
            claim=claim,
            role_id=None,
            tags=sorted({w for w in re.findall(r"[a-z]{4,}", question.requirement.lower())})[:6],
            metric_value=numbers[0].strip() if numbers else None,
        )

    # ── confirmation ────────────────────────────────────────────────────────
    def pending(self) -> list[Proposal]:
        return [p for p in self._proposals.values() if not p.confirmed]

    def confirm(self, proposal_id: str, *, verified: bool, claim: str | None = None) -> Proposal:
        """Promote a proposal. The only route from an answer into the corpus."""
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise InterviewError(f"no such proposal: {proposal_id}")
        if claim is not None:
            if not claim.strip():
                raise InterviewError("a confirmed claim cannot be empty")
            proposal.claim = claim.strip()
        proposal.confirmed = True
        proposal.verified = verified
        return proposal

    def confirmed_gaps(self) -> list[str]:
        """Requirements the user has said, in their own words, they do not meet."""
        out = []
        for question in self.questions:
            answer = self.answers.get(question.id)
            if answer and answer.confirms_gap:
                out.append(question.requirement)
        return out

    def progress(self) -> tuple[int, int]:
        return len(self.answers), len(self.questions)


def interview_from_scorecard(card: Scorecard, corpus: Corpus) -> Interview:
    return Interview(build_questions(card.rows, corpus))


__all__ = [
    "AUTHENTICITY_NOTICE",
    "COACHING_DISCLAIMER",
    "ELABORATE_PROMPT",
    "QUESTION_COUNT",
    "Answer",
    "Interview",
    "InterviewError",
    "Preparedness",
    "Proposal",
    "Question",
    "interview_from_scorecard",
]
