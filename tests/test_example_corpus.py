"""The committed example is what CI validates, so it has to earn that job.

The real corpus is gitignored and never reaches CI. If the example were a thin
stub, the schema would be effectively untested on every pull request — the
validator would be green against nothing. So the example must exercise the
fields that actually have rules attached.
"""

from __future__ import annotations

from pathlib import Path

from cv_tailor.corpus import load_corpus_text

EXAMPLE = Path(__file__).resolve().parents[1] / "career-corpus.example.yaml"


def test_the_example_exists_and_is_valid() -> None:
    corpus = load_corpus_text(EXAMPLE.read_text(encoding="utf-8"))
    assert corpus.person.name
    assert corpus.roles


def test_the_example_exercises_both_metric_states() -> None:
    """A corpus with only verified metrics would never test the guard."""
    metrics = [b.metric for b in load_corpus_text(EXAMPLE.read_text("utf-8")).all_bullets()]
    present = [m for m in metrics if m is not None]
    assert any(m.verified for m in present), "needs at least one verified metric"
    assert any(not m.verified for m in present), "needs at least one placeholder metric"


def test_the_example_exercises_undated_roles_positions_and_skill_evidence() -> None:
    corpus = load_corpus_text(EXAMPLE.read_text("utf-8"))
    assert any(r.needs_dates for r in corpus.roles), "needs a TODO-dated role"
    assert corpus.positions, "needs at least one position"
    assert len(corpus.summaries) > 1, (
        "needs SEVERAL summaries — one is the same paragraph on every application, "
        "and with none the rendered CV opens with nothing at all"
    )
    assert any(s.evidence_refs for s in corpus.skills), "needs a skill citing evidence"
    assert corpus.todos(), "todos() must surface the gaps the example deliberately contains"


def test_the_example_names_no_real_employer() -> None:
    """It is fictional data, not a redaction of the real corpus.

    A redacted real corpus leaks shape even when names are removed, and it
    invites someone to 'restore' a name later. Inventing from scratch does not.
    """
    text = EXAMPLE.read_text("utf-8").casefold()
    for real in ("toppan", "ecquaria", "hogarth", "patroids", "apple", "alvin"):
        assert real not in text, f"the example must not name {real!r}"
