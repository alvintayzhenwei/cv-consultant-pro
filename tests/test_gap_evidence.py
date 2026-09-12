"""A gap cites nothing on the scorecard, but its partial matches still count.

Found live. The Google posting's strongest preferred qualification reads:

    Knowledge of "LLM-native" metrics (e.g., tokens/sec, cost-per-request) and
    techniques for optimizing state management and granular tracing.

It is compound, so it correctly scored GAP rather than STRONG. But a GAP
discarded ALL its evidence, so the two bullets that genuinely answered its first
half — a model router making spend observable per call, and a gateway owning
tracing — contributed nothing to selection and dropped off the CV completely.

Same class of defect as the display cap driving content: a decision about how to
SCORE a requirement leaked into what goes on the page.
"""

from __future__ import annotations

from cv_tailor.corpus import load_corpus_text
from cv_tailor.jd import parse_jd
from cv_tailor.match import Verdict, score
from cv_tailor.render import select

CORPUS = """
person:
  name: Test Person
roles:
  - id: r1
    org: Acme
    title: Engineer
    start: "2020-01"
    end: present
    tags: [observability]
    bullets:
      - id: b-tracing
        claim: Instrumented granular tracing across every agent call
        mechanism: OpenTelemetry into a self-hosted backend
        tags: [tracing, observability, telemetry]
skills:
  - name: Granular tracing
    aliases: [granular tracing, tracing, observability]
    evidence_refs: [b-tracing]
"""

# Half of this is evidenced; half is not. The verdict must reflect the unmet
# half; the selection must still see the met one.
POSTING = (
    "Preferred qualifications:\n"
    "- Knowledge of granular tracing and quantum error correction techniques.\n"
)


def test_a_compound_gap_shows_no_evidence_on_the_scorecard() -> None:
    card = score(parse_jd(POSTING), load_corpus_text(CORPUS))
    row = card.rows[0]
    assert row.verdict is Verdict.GAP
    assert row.evidence_ids == [], "a gap must not claim evidence it does not have"


def test_but_a_partially_matched_bullet_still_reaches_the_cv() -> None:
    corpus = load_corpus_text(CORPUS)
    card = score(parse_jd(POSTING), corpus)
    assert card.relevance().get("b-tracing", 0) > 0, (
        "the bullet answering the met half must count toward selection"
    )

    selection = select(corpus, card)
    assert "b-tracing" in selection.bullet_ids()


def test_a_true_gap_with_no_match_at_all_still_counts_nothing() -> None:
    corpus = load_corpus_text(CORPUS)
    card = score(
        parse_jd("Preferred qualifications:\n- Experience with underwater welding.\n"), corpus
    )
    assert card.rows[0].verdict is Verdict.GAP
    assert card.relevance() == {}
