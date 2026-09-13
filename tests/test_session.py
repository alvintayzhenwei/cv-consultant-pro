"""The script the server reads out: one stage at a time, in a fixed order.

These tests exist because the alternative is worse than untested — it is
*inconsistent*. Hand an agent a bag of tools with no state machine and the
interview it runs depends on the model behind it: a strong host asks about gaps
first, a weak one renders a CV before it has a layout, and neither is
reproducible. Every assertion below pins an ordering that a user should be able
to rely on whichever assistant they are talking to.
"""

from __future__ import annotations

from pathlib import Path

from cv_consultant_pro.corpus import load_corpus_text
from cv_consultant_pro.interview import interview_from_scorecard
from cv_consultant_pro.jd import parse_jd
from cv_consultant_pro.match import score
from cv_consultant_pro.session import Session, Stage

from .fixtures import ACCOUNTANT, NURSE


def _ready() -> Session:
    """A session with everything the engine can get without asking the user."""
    session = Session()
    session.corpus = load_corpus_text(NURSE.corpus)
    session.layout = "signal"
    return session


# ── the order of the questions ──────────────────────────────────────────────
def test_an_empty_session_asks_for_evidence_before_anything_else() -> None:
    step = Session().next_step()
    assert step.stage is Stage.NO_CORPUS
    assert step.then_call == "cv_seed"


def test_a_corpus_that_does_not_load_blocks_everything_downstream() -> None:
    session = Session()
    session.corpus_error = ["bullet b-1: metric is verified but carries no value"]
    step = session.next_step()
    assert step.stage is Stage.CORPUS_INCOMPLETE
    assert step.detail["problems"] == session.corpus_error


def test_an_outstanding_gap_is_asked_about_one_at_a_time() -> None:
    """A list of eleven holes is a wall; one question is a conversation."""
    session = Session()
    session.corpus = load_corpus_text(
        NURSE.corpus.replace('start: "2021-03"', "start: TODO", 1)
    )
    step = session.next_step()
    assert step.stage is Stage.CORPUS_INCOMPLETE
    assert step.then_call == "cv_corpus_add"
    assert step.detail["ask_about"] == step.detail["outstanding"][0]["ref"]
    assert len(step.detail["outstanding"]) >= 1


def test_a_layout_is_chosen_before_a_posting_is_read() -> None:
    session = Session()
    session.corpus = load_corpus_text(NURSE.corpus)
    step = session.next_step()
    assert step.stage is Stage.NEEDS_LAYOUT
    assert step.then_call == "cv_preview"


def test_a_posting_is_asked_for_once_the_layout_is_settled() -> None:
    step = _ready().next_step()
    assert step.stage is Stage.NEEDS_JD
    assert step.then_call == "cv_ingest_jd"


def test_a_posting_that_has_been_read_is_scored_without_being_asked_about() -> None:
    """Scoring needs nothing from the user, so it must not stop to ask."""
    session = _ready()
    session.jd = parse_jd(NURSE.posting)
    step = session.next_step()
    assert step.then_call == "cv_score"


# ── the honest read comes before the document ───────────────────────────────
def test_the_summary_is_chosen_before_a_cv_is_written() -> None:
    """With more than one authored summary, the user picks which opens the CV.

    A posting-shaped opening is right for one application and wrong for a talent
    pool. The engine does not decide that.
    """
    session = _ready()
    session.jd = parse_jd(NURSE.posting)
    session.card = score(session.jd, session.corpus)
    step = session.next_step()
    assert step.stage is Stage.NEEDS_SUMMARY
    assert step.then_call == "cv_summary"


def test_the_score_is_reported_before_a_cv_is_written() -> None:
    """Rendering first would bury the gaps under a finished-looking document."""
    session = _ready()
    session.jd = parse_jd(NURSE.posting)
    session.card = score(session.jd, session.corpus)
    session.summary_id = session.corpus.summaries[0].id
    step = session.next_step()
    assert step.stage is Stage.SCORED
    assert step.then_call == "cv_render"
    assert "hard filter" in step.say
    assert step.detail["hard_filters"] == len(session.card.hard_filters)


def test_the_interview_is_offered_once_the_kit_exists() -> None:
    session = _ready()
    session.jd = parse_jd(NURSE.posting)
    session.card = score(session.jd, session.corpus)
    session.summary_id = session.corpus.summaries[0].id
    session.kit_dir = Path("kits/latest")
    step = session.next_step()
    assert step.stage is Stage.RENDERED
    assert step.then_call == "cv_interview"
    assert "ten questions" in step.say


# ── the interview ───────────────────────────────────────────────────────────
def _interviewing() -> Session:
    session = _ready()
    session.jd = parse_jd(NURSE.posting)
    session.card = score(session.jd, session.corpus)
    session.summary_id = session.corpus.summaries[0].id
    session.kit_dir = Path("kits/latest")
    session.interview = interview_from_scorecard(session.card, session.corpus)
    session.interview.acknowledge()
    return session


def test_an_open_interview_keeps_asking_and_counts_out_loud() -> None:
    session = _interviewing()
    step = session.next_step()
    assert step.stage is Stage.INTERVIEWING
    assert step.then_call == "cv_next_question"
    assert step.say.startswith("Question 1 of ")


def test_a_proposal_interrupts_the_interview_until_the_user_confirms_it() -> None:
    """Nothing reaches the CV unseen. The confirmation cannot wait until the end.

    Asked at the end, a user is confirming a list they have lost the context
    for; asked now, they are still holding the answer they just gave.
    """
    session = _interviewing()
    answer = session.interview.record_answer(
        session.interview.questions[0].id, "I led that programme for three years."
    )
    step = session.next_step()
    assert step.stage is Stage.EVIDENCE_PENDING
    assert step.then_call == "cv_confirm_evidence"
    assert step.detail["pending"][0]["id"] == answer.proposals[0].id
    assert step.detail["pending"][0]["from_answer"] == answer.user_said


def test_confirmed_evidence_makes_the_kit_on_disk_stale_and_says_so() -> None:
    """A generated kit is a snapshot. Five of six went quietly out of date once."""
    session = _interviewing()
    for question in list(session.interview.questions):
        session.interview.record_answer(question.id, "I have never done that, honestly.")
    session.kit_stale = True
    step = session.next_step()
    assert step.stage is Stage.STALE
    assert step.then_call == "cv_render"


def test_a_finished_interview_ends_on_the_explanation_not_the_file() -> None:
    session = _interviewing()
    for question in list(session.interview.questions):
        session.interview.record_answer(question.id, "I have never done that, honestly.")
    step = session.next_step()
    assert step.stage is Stage.DONE
    assert step.then_call == "cv_explain"


# ── the script does not depend on the profession ────────────────────────────
def test_the_same_script_runs_for_a_career_this_tool_was_not_written_for() -> None:
    session = Session()
    session.corpus = load_corpus_text(ACCOUNTANT.corpus)
    session.layout = "ledger"
    session.jd = parse_jd(ACCOUNTANT.posting)
    session.card = score(session.jd, session.corpus)
    session.summary_id = session.corpus.summaries[0].id
    assert session.next_step().stage is Stage.SCORED
