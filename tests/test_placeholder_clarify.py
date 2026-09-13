"""Placeholders are settled BEFORE the CV is written, not listed afterwards.

An unverified figure renders as `[N]`. That is the anti-fabrication contract
working — but a kit that hands back a finished-looking CV plus a "placeholders
to fill" file has put the holes in the output and the question in a footnote.
The user reads the CV, not the footnote, and sends it.

So the script asks first, about the placeholders that will actually appear on
THIS CV. "Leave it as a placeholder" stays a legitimate answer; being asked is
the point, not being forced to produce a number.
"""

from __future__ import annotations

from cv_consultant_pro.corpus import load_corpus_text
from cv_consultant_pro.jd import parse_jd
from cv_consultant_pro.match import score
from cv_consultant_pro.render import select
from cv_consultant_pro.session import Session, Stage

CORPUS = """
person:
  name: Test Person
summaries:
  - id: sum-only
    tags: [automation]
    text: Engineer who automates repetitive work.
roles:
  - id: r-shown
    org: Acme
    title: Engineer
    start: "2019-01"
    end: present
    tags: [automation]
    bullets:
      - id: b-placeholder
        claim: Cut release preparation to [N] minutes
        mechanism: automated the reporting pipeline
        tags: [automation, release]
        metric:
          verified: false
          placeholder: "[N]"
      - id: b-measured
        claim: Automated the weekly report
        mechanism: a scheduled job
        tags: [automation]
  - id: r-unrelated
    org: Other Co
    title: Analyst
    start: "2015-01"
    end: "2018-01"
    tags: [finance]
    bullets:
      - id: b-offscreen
        claim: Reconciled [X] ledgers each quarter
        mechanism: manual review
        tags: [finance]
        metric:
          verified: false
          placeholder: "[X]"
"""

POSTING = "Responsibilities\n- Build automation for release processes.\n"


def _scored() -> Session:
    session = Session()
    session.corpus = load_corpus_text(CORPUS)
    session.layout = "signal"
    session.jd = parse_jd(POSTING)
    session.card = score(session.jd, session.corpus)
    session.summary_id = "sum-only"
    return session


def test_the_user_is_asked_about_placeholders_before_the_cv_is_written() -> None:
    step = _scored().next_step()
    assert step.stage is Stage.NEEDS_FIGURES
    assert step.then_call == "cv_fill_placeholder"


def test_only_the_placeholders_that_will_APPEAR_are_asked_about() -> None:
    """Asking about a hole on a bullet this CV drops is noise, not diligence."""
    session = _scored()
    refs = [p["bullet"] for p in session.next_step().detail["placeholders"]]
    assert refs == ["b-placeholder"]
    assert "b-offscreen" not in refs


def test_the_question_carries_the_sentence_the_hole_sits_in() -> None:
    """"Give me a number for b-placeholder" is unanswerable out of context."""
    detail = _scored().next_step().detail["placeholders"][0]
    assert detail["placeholder"] == "[N]"
    assert "release preparation" in detail["claim"]


def test_settling_them_lets_the_script_move_on() -> None:
    session = _scored()
    session.figures_settled = True
    assert session.next_step().stage is Stage.SCORED


def test_a_cv_with_no_placeholders_is_never_asked() -> None:
    session = _scored()
    session.corpus = load_corpus_text(CORPUS.replace('placeholder: "[N]"', 'placeholder: "[N]"')
                                      .split("  - id: r-unrelated")[0])
    session.corpus.roles[0].bullets = [
        b for b in session.corpus.roles[0].bullets if b.id != "b-placeholder"
    ]
    session.card = score(session.jd, session.corpus)
    assert session.next_step().stage is Stage.SCORED


def test_selection_is_what_decides_not_the_whole_corpus() -> None:
    """The list must come from what `select` kept, or it drifts from the CV."""
    session = _scored()
    chosen = {b.id for _, bullets in select(session.corpus, session.card).roles for b in bullets}
    asked = {p["bullet"] for p in session.next_step().detail["placeholders"]}
    assert asked <= chosen


# ── filling one for real ────────────────────────────────────────────────────
def test_a_measured_figure_replaces_the_hole_in_the_SENTENCE_too() -> None:
    """The token is written into the claim, not only into the metric block.

    Changing only the metric would leave the CV printing "[N]" while the corpus
    claimed a number — an unfilled CV and a corpus that says it is filled.
    """
    from cv_consultant_pro.edit import set_metric

    filled = set_metric(CORPUS, "b-placeholder", "under two")
    corpus = load_corpus_text(filled)
    bullet = next(b for b in corpus.roles[0].bullets if b.id == "b-placeholder")
    assert "[N]" not in bullet.claim
    assert "under two" in bullet.claim
    assert bullet.metric.verified is True
    assert bullet.metric.value == "under two"
    assert not bullet.has_placeholder


def test_filling_a_bullet_that_has_no_hole_is_refused() -> None:
    import pytest

    from cv_consultant_pro.edit import EditError, set_metric

    with pytest.raises(EditError) as err:
        set_metric(CORPUS, "b-measured", "12")
    assert "no placeholder" in str(err.value)


def test_a_blank_figure_is_refused_rather_than_written() -> None:
    """A blank is not an answer; keeping the visible gap is."""
    import pytest

    from cv_consultant_pro.edit import EditError, set_metric

    with pytest.raises(EditError) as err:
        set_metric(CORPUS, "b-placeholder", "   ")
    assert "keep the placeholder" in str(err.value)


def test_the_other_bullets_are_untouched() -> None:
    from cv_consultant_pro.edit import set_metric

    filled = set_metric(CORPUS, "b-placeholder", "under two")
    assert "Reconciled [X] ledgers" in filled
