"""The interview: the gate, verbatim capture, confirmation and confirmed gaps.

These are the guards the whole feature rests on, so each test names the thing it
prevents rather than the method it calls.
"""

from __future__ import annotations

import pytest

from cv_consultant_pro.corpus import load_corpus_text
from cv_consultant_pro.interview import (
    QUESTION_COUNT,
    Interview,
    InterviewError,
    Preparedness,
    build_questions,
    interview_from_scorecard,
)
from cv_consultant_pro.jd import parse_jd
from cv_consultant_pro.match import Verdict, score

from .fixtures import NURSE, TEACHER

CORPUS = load_corpus_text(NURSE.corpus)
CARD = score(parse_jd(NURSE.posting), CORPUS)


def _started() -> Interview:
    interview = interview_from_scorecard(CARD, CORPUS)
    interview.acknowledge()
    return interview


# ── the gate ────────────────────────────────────────────────────────────────
def test_no_question_is_served_before_the_notice_is_acknowledged() -> None:
    """The declaration is a gate, not a banner nobody reads."""
    interview = interview_from_scorecard(CARD, CORPUS)
    with pytest.raises(InterviewError) as err:
        interview.next_question()
    assert "acknowledged" in str(err.value)


def test_no_answer_is_recorded_before_the_notice_is_acknowledged() -> None:
    interview = interview_from_scorecard(CARD, CORPUS)
    with pytest.raises(InterviewError):
        interview.record_answer("q1", "something")


def test_the_notice_says_the_answers_must_be_the_users_own() -> None:
    notice = interview_from_scorecard(CARD, CORPUS).notice().lower()
    assert "your own experience" in notice
    assert "do not ask an ai" in notice
    assert "reused by every cv" in notice, (
        "the notice must say corpus poisoning outlives this one application — "
        "that is the argument that actually lands"
    )


# ── question selection ──────────────────────────────────────────────────────
def test_ten_questions_not_twenty() -> None:
    interview = _started()
    assert len(interview.questions) <= QUESTION_COUNT


def test_questions_lead_with_what_the_corpus_cannot_answer() -> None:
    """A question about a requirement you already evidence is a rehearsal.

    A question about one you do not is where unrecorded capability surfaces, so
    the scarce slots go there first.
    """
    requirements = [
        ("Experience with A", Verdict.STRONG),
        ("Experience with B", Verdict.GAP),
        ("Experience with C", Verdict.PARTIAL),
    ]
    questions = build_questions(requirements, CORPUS, limit=3)
    assert questions[0].verdict is Verdict.GAP
    assert questions[1].verdict is Verdict.PARTIAL
    assert questions[2].verdict is Verdict.STRONG


def test_a_question_says_whether_you_have_a_recorded_position_on_it() -> None:
    corpus = load_corpus_text(
        TEACHER.corpus
        + """
positions:
  - id: pos-phonics
    topic: Early reading
    question: How do you lead a systematic synthetic phonics programme?
    answer: Train the staff first, then hold a fortnightly assessment cycle.
"""
    )
    questions = build_questions(
        [("Experience leading a systematic synthetic phonics programme", Verdict.GAP)],
        corpus,
    )
    assert questions[0].preparedness is Preparedness.PREPARED
    assert questions[0].position_id == "pos-phonics"


# ── capture ─────────────────────────────────────────────────────────────────
def test_an_answer_is_recorded_verbatim() -> None:
    """What lands on the CV is what the user said, not an improved version."""
    interview = _started()
    said = "I ran the preceptorship programme for three years, about 12 nurses a year."
    answer = interview.record_answer(interview.questions[0].id, said)
    assert answer.user_said == said
    assert answer.proposals[0].user_said == said


def test_a_proposal_carries_a_figure_only_when_the_user_stated_one() -> None:
    interview = _started()
    qid = interview.questions[0].id
    answer = interview.record_answer(qid, "I trained about 12 nurses a year on it.")
    assert answer.proposals[0].metric_value is not None

    interview2 = _started()
    answer2 = interview2.record_answer(qid, "I ran the training for the ward.")
    assert answer2.proposals[0].metric_value is None, "no number said, none invented"


def test_an_empty_answer_records_nothing() -> None:
    interview = _started()
    with pytest.raises(InterviewError):
        interview.record_answer(interview.questions[0].id, "   ")


# ── the honesty guards ──────────────────────────────────────────────────────
def test_a_proposal_does_nothing_until_it_is_confirmed() -> None:
    interview = _started()
    answer = interview.record_answer(interview.questions[0].id, "I led that programme.")
    assert answer.proposals[0].confirmed is False
    assert interview.pending(), "the proposal must be waiting, not applied"


def test_confirming_requires_an_explicit_verified_decision() -> None:
    interview = _started()
    answer = interview.record_answer(interview.questions[0].id, "I trained 12 nurses a year.")
    proposal = interview.confirm(answer.proposals[0].id, verified=False)
    assert proposal.confirmed is True
    assert proposal.verified is False
    assert not interview.pending()


def test_an_admission_of_inexperience_proposes_nothing_and_is_recorded_as_a_gap() -> None:
    """A confirmed gap is better information than an unconfirmed one.

    It must never be softened into "exposure to" on the CV, and it must never
    quietly become a proposal.
    """
    interview = _started()
    question = interview.questions[0]
    answer = interview.record_answer(
        question.id, "Honestly I have never done that — it was someone else's remit."
    )
    assert answer.confirms_gap is True
    assert answer.proposals == []
    assert question.requirement in interview.confirmed_gaps()


def test_there_is_no_parameter_for_an_agent_to_submit_its_own_wording() -> None:
    """The guarantee is the absence of an API, not a warning in a docstring."""
    import inspect

    params = set(inspect.signature(Interview.record_answer).parameters)
    assert params == {"self", "question_id", "user_said"}, (
        "record_answer grew a parameter. If an agent can pass text that is not the "
        f"user's own, the whole truth loop is decorative. Found: {params}"
    )
