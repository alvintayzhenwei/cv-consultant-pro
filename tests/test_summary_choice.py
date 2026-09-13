"""Which summary opens the CV, and who decides.

Two separate problems, found by running the engine against two real Apple
postings for the same person:

  - The picker read only requirement TEXT, never the job title. An Engineering
    Product Manager posting lists React in its minimum qualifications, so the
    front-end summary outscored the product-management one and the application
    opened "Front-end engineer and lead".
  - Even picked correctly, a JD-tailored summary is wrong for a centralised
    talent pool, where one stored CV has to answer every search. Two postings
    produced summaries describing two different professions.
"""

from __future__ import annotations

from cv_consultant_pro.corpus import load_corpus_text
from cv_consultant_pro.jd import parse_jd
from cv_consultant_pro.match import score
from cv_consultant_pro.render import pick_summary, summary_choices

CORPUS = """
person:
  name: Test Person
summaries:
  - id: sum-frontend
    tags: [frontend, react, web, javascript]
    text: Front-end engineer who ships web interfaces.
  - id: sum-pm
    tags: [product-management, delivery, program, roadmap]
    text: Engineering product manager who still writes code.
  - id: sum-broad
    tags: [data, cloud, platform]
    text: Engineer across data platforms and cloud.
roles:
  - id: r-one
    org: Acme
    title: Engineer
    start: "2019-01"
    end: present
    tags: [frontend]
    bullets:
      - id: b-one
        claim: Shipped a customer-facing web application
        mechanism: React and a component library
        tags: [frontend, react]
"""

# The real shape of the Apple posting: a product-management ROLE whose
# qualifications are full of front-end words.
PM_POSTING = """Engineering Product Manager

Minimum Qualifications
Hands-on experience in frontend software engineering, including React and JavaScript
Demonstrated ability to deliver web applications from concept through production
"""


def _card(posting: str, title: str | None):
    corpus = load_corpus_text(CORPUS)
    return corpus, score(parse_jd(posting, title=title), corpus)


# ── the title is a signal, and it was being thrown away ─────────────────────
def test_the_job_title_decides_more_than_a_requirement_keyword() -> None:
    """A title says what the job IS; requirements only say what it needs."""
    corpus, card = _card(PM_POSTING, "Engineering Product Manager")
    assert pick_summary(corpus, card, title="Engineering Product Manager").id == "sum-pm"


def test_without_a_title_the_requirements_still_decide() -> None:
    corpus, card = _card(PM_POSTING, None)
    assert pick_summary(corpus, card, title=None) is not None


# ── the pool case: the user chooses, the engine does not ────────────────────
def test_every_authored_summary_is_offered_with_the_jd_match_marked() -> None:
    """The user picks from what they wrote. Nothing is composed or ranked away."""
    corpus, card = _card(PM_POSTING, "Engineering Product Manager")
    choices = summary_choices(corpus, card, title="Engineering Product Manager")
    assert [c.id for c in choices] == ["sum-frontend", "sum-pm", "sum-broad"]
    assert [c.id for c in choices if c.jd_match] == ["sum-pm"]


def test_a_pinned_summary_overrides_the_jd_match() -> None:
    """The whole point: the same corpus and JD, a different opening paragraph."""
    corpus, card = _card(PM_POSTING, "Engineering Product Manager")
    assert pick_summary(corpus, card, title=None, pinned="sum-broad").id == "sum-broad"


def test_pinning_something_that_is_not_there_falls_back_rather_than_crashing() -> None:
    corpus, card = _card(PM_POSTING, None)
    assert pick_summary(corpus, card, title=None, pinned="no-such-summary") is not None


def test_a_corpus_with_no_summaries_still_renders() -> None:
    """A CV opens without a summary rather than with an invented one."""
    corpus = load_corpus_text(CORPUS.split("summaries:")[0] + CORPUS.split("roles:")[1].join(["roles:", ""]))
    assert pick_summary(corpus, score(parse_jd(PM_POSTING), corpus), title=None) is None


# ── the script asks before it writes ────────────────────────────────────────
def test_the_user_is_asked_which_summary_before_the_cv_is_written() -> None:
    """The opening paragraph is a claim about who you are. Nobody else picks it."""
    from cv_consultant_pro.session import Session, Stage

    session = Session()
    session.corpus, session.card = _card(PM_POSTING, "Engineering Product Manager")
    session.layout = "signal"
    session.jd = parse_jd(PM_POSTING, title="Engineering Product Manager")

    step = session.next_step()
    assert step.stage is Stage.NEEDS_SUMMARY
    assert step.then_call == "cv_summary"


def test_once_chosen_the_script_moves_on() -> None:
    from cv_consultant_pro.session import Session, Stage

    session = Session()
    session.corpus, session.card = _card(PM_POSTING, "Engineering Product Manager")
    session.layout = "signal"
    session.jd = parse_jd(PM_POSTING, title="Engineering Product Manager")
    session.summary_id = "sum-pm"

    step = session.next_step()
    assert step.stage is Stage.SCORED
    assert step.then_call == "cv_render"


def test_a_corpus_with_one_summary_is_not_asked_about() -> None:
    """There is no choice to make, so asking would be ceremony.

    Every one of the five profession fixtures has exactly one summary, which is
    why none of them surfaced this problem.
    """
    from cv_consultant_pro.session import Session, Stage

    single = CORPUS.split("  - id: sum-pm")[0]
    corpus = load_corpus_text(single + "roles:" + CORPUS.split("roles:")[1])
    session = Session()
    session.corpus = corpus
    session.card = score(parse_jd(PM_POSTING), corpus)
    session.layout = "signal"
    session.jd = parse_jd(PM_POSTING)

    assert session.next_step().stage is Stage.SCORED
