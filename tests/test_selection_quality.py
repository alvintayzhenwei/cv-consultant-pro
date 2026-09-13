"""Which bullets and roles earn a place on one page.

Written from two specific complaints about a generated CV:

  - A Hogarth role rendered "Learned Apple Script from zero" instead of
    "automation that made processes at least 50% faster". Both matched the
    posting; only one is an accomplishment.
  - A six-month 2012 internship survived while a two-year role was dropped,
    because relevance counted hits and ignored everything else.
"""

from __future__ import annotations

from cv_consultant_pro.corpus import load_corpus_text
from cv_consultant_pro.jd import parse_jd
from cv_consultant_pro.match import score
from cv_consultant_pro.render import select

CORPUS = """
person:
  name: Test Person
roles:
  - id: r-main
    org: Acme
    title: Engineer
    start: "2019-01"
    end: present
    tags: [automation]
    bullets:
      # Declared FIRST deliberately: declaration order must not decide this, or
      # the test proves nothing. The measured bullet has to win on its merits.
      - id: b-learning
        claim: Learned several languages from zero to build that tooling
        mechanism: self-directed learning
        tags: [automation, tooling]
      - id: b-measured
        claim: Built automation that made daily processes at least 50% faster
        mechanism: tooling for repetitive work
        tags: [automation, tooling]
        metric:
          verified: true
          value: at least 50% faster
  - id: r-brief
    org: Tiny Co
    title: Intern
    start: "2012-02"
    end: "2012-07"
    tags: [automation]
    bullets:
      - id: b-intern
        claim: Completed an internship supporting internal automation
        mechanism: on-site work
        tags: [automation]
  - id: r-substantial
    org: Long Co
    title: Developer
    start: "2013-10"
    end: "2015-07"
    tags: [automation]
    bullets:
      - id: b-substantial
        claim: Delivered automation for regional clients
        mechanism: bespoke tooling
        tags: [automation, tooling]
"""

POSTING = "Responsibilities\n- Build automation and tooling for repetitive work.\n"


def _selection():
    corpus = load_corpus_text(CORPUS)
    jd = parse_jd(POSTING)
    card = score(jd, corpus)
    return corpus, select(corpus, card)


def test_a_measured_accomplishment_outranks_an_equally_relevant_one_without_a_figure() -> None:
    """Both bullets match the same tags. The one with a verified number wins.

    A recruiter scans for outcomes, and the ML rankers weight quantified results
    higher. Relevance alone cannot see that difference.
    """
    _corpus, selection = _selection()
    main = next(bullets for role, bullets in selection.roles if role.id == "r-main")
    assert main[0].id == "b-measured"


def test_a_role_too_short_to_matter_is_dropped_before_a_substantial_one() -> None:
    """Six months as an intern is not worth a line a two-year role could have."""
    _corpus, selection = _selection()
    kept = {role.id for role, _ in selection.roles}
    assert "r-brief" not in kept, "a six-month role should not outrank a two-year one"
    assert "r-substantial" in kept


def test_a_short_role_survives_when_it_is_the_only_evidence() -> None:
    """Dropping it would lose the only thing answering the posting.

    The minimum-duration rule is a tie-breaker, not a ban: a brief role that is
    the sole evidence for a requirement is worth more than the space it costs.
    """
    corpus = load_corpus_text(
        """
person:
  name: Test Person
roles:
  - id: r-brief-only
    org: Tiny Co
    title: Intern
    start: "2012-02"
    end: "2012-07"
    tags: [quantum]
    bullets:
      - id: b-only
        claim: Built the calibration harness for a quantum error correction experiment
        mechanism: automated pulse sequencing across the qubit array
        tags: [quantum, research]
"""
    )
    jd = parse_jd("Responsibilities\n- Experience with quantum error correction research.\n")
    selection = select(corpus, score(jd, corpus))
    assert "r-brief-only" in {role.id for role, _ in selection.roles}


def test_no_single_role_eats_the_whole_page() -> None:
    """A role wants a handful of bullets, not everything that matches.

    `select` capped only the GLOBAL line budget, so the most relevant role took
    as many bullets as would fit and later roles were squeezed to one or two.
    Recovering evidence then made the document worse: a real run put thirteen
    bullets under each of two roles and dropped seven newly recovered ones.
    """
    bullets = "\n".join(
        f"""      - id: b-{n}
        claim: Ran an automation project number {n} that cut manual effort
        mechanism: tooling for repetitive work
        tags: [automation, tooling]"""
        for n in range(12)
    )
    corpus_text = f"""
person:
  name: Test Person
roles:
  - id: r-big
    org: Acme
    title: Engineer
    start: "2019-01"
    end: present
    tags: [automation]
    bullets:
{bullets}
  - id: r-second
    org: Beta
    title: Engineer
    start: "2015-01"
    end: "2018-12"
    tags: [automation]
    bullets:
      - id: b-second
        claim: Built automation that removed a class of manual error
        mechanism: tooling for repetitive work
        tags: [automation, tooling]
"""
    corpus = load_corpus_text(corpus_text)
    jd = parse_jd("Requirements\n- Experience with automation and tooling\n")
    selection = select(corpus, score(jd, corpus))
    per_role = {role.id: len(bs) for role, bs in selection.roles}
    assert per_role, "nothing was selected"
    assert max(per_role.values()) <= 6, per_role
    assert "r-second" in per_role, "the later role was squeezed out by the first"
