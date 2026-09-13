"""Behaviours added after the first real run produced a materially weak CV.

Each test names the defect it closes. They were written from an actual generated
kit, not from imagination — which is why they are specific.
"""

from __future__ import annotations

from pathlib import Path

from cv_consultant_pro.corpus import load_corpus_text
from cv_consultant_pro.docx import write_docx
from cv_consultant_pro.jd import parse_jd
from cv_consultant_pro.match import Verdict, score
from cv_consultant_pro.render import render, select

CORPUS = """
person:
  name: Test Person
  location: Singapore
summaries:
  - id: sum-enablement
    tags: [enablement, training, curriculum]
    text: Engineer who builds agentic platforms and teaches organisations to use them.
  - id: sum-delivery
    tags: [delivery, programme, release]
    text: Delivery lead shipping platforms in regulated environments.
roles:
  - id: r-now
    org: Acme
    title: Lead
    start: "2022-01"
    end: present
    tags: [enablement]
    bullets:
      - id: b-enablement
        claim: Ran the enablement programme that trained every new engineer
        mechanism: a curriculum of workshops and capstones
        tags: [enablement, training, curriculum, onboarding]
      - id: b-rag
        claim: Shipped a retrieval-augmented generation assistant
        mechanism: grounded answers over policy documents
        tags: [rag, llm]
      - id: b-verbose
        claim: Delivered an extremely long accomplishment whose claim alone already runs to
          a considerable length and comfortably exceeds any sensible single line on a page
        mechanism: by means of an equally long mechanism clause that would push the rendered
          line well past what a one-page curriculum vitae can reasonably carry on one row
        tags: [enablement]
  - id: r-old
    org: Beta
    title: Engineer
    start: "2015-01"
    end: "2018-01"
    tags: [enablement]
    bullets:
      - id: b-old
        claim: Built internal tooling
        mechanism: scripts
        tags: [enablement, tooling]
skills:
  - name: Technical enablement
    aliases: [enablement programs, technical enablement programs, training]
    evidence_refs: [b-enablement]
  - name: Retrieval-augmented generation
    aliases: [RAG, retrieval-augmented generation]
    evidence_refs: [b-rag]
education:
  - institution: Example University
    qualification: BSc (Hons) Computer Science
    end: "2013-09"
"""


def _card(posting: str):
    corpus = load_corpus_text(CORPUS)
    jd = parse_jd(posting, title="Test Role")
    return corpus, jd, score(jd, corpus)


def test_a_compound_requirement_scores_by_its_weakest_part() -> None:
    """Fix 3. 'A and B' was scoring strong on A alone.

    The live failure: a posting wanting vector databases AND RAG pipelines scored
    strong because the corpus had RAG. Half a requirement is not a match.
    """
    _, _, card = _card(
        "Minimum qualifications:\n"
        "- Experience building pipelines using both vector databases and "
        "Retrieval-Augmented Generation architectures.\n"
    )
    row = card.rows[0]
    assert row.verdict is not Verdict.STRONG, "an unmet half must stop this scoring strong"


def test_a_degree_requirement_is_answered_from_education_not_from_bullets() -> None:
    """Fix 4. A degree line was citing two unrelated delivery bullets."""
    _, _, card = _card(
        "Minimum qualifications:\n- Bachelor's degree in Computer Science or equivalent.\n"
    )
    row = card.rows[0]
    assert row.evidence_ids == [], "bullets are not evidence of a degree"
    assert row.note and "BSc" in row.note


def test_an_eligibility_filter_cites_no_bullet_evidence() -> None:
    """Fix 4. The right-to-work line was citing bullets that matched on 'Singapore'."""
    _, _, card = _card(
        "Applicants must have a current right to work in Singapore without visa sponsorship.\n"
    )
    row = card.hard_filters[0]
    assert row.evidence_ids == []
    assert row.note, "an eligibility filter must say it is for the reader to answer"


def test_evidenced_years_is_the_union_of_role_spans_not_the_longest_role() -> None:
    """Fix: '4.9 years in a single role' understated twelve years of history."""
    _, _, card = _card(
        "Minimum qualifications:\n- 5 years of experience in enablement.\n"
    )
    row = card.hard_filters[0]
    assert row.evidenced_years is not None
    # 2015-01..2018-01 is 3 years; 2022-01..now is 3+. The union exceeds either.
    assert row.evidenced_years > 3.5, "overlapping and gapped roles must be unioned"


def test_a_summary_is_selected_by_tag_overlap_never_written() -> None:
    """Fix 2. The generated CV had no summary at all.

    Select-only means the engine cannot compose one, so the corpus carries
    several and the engine picks the closest.
    """
    corpus, jd, card = _card(
        "Responsibilities\n- Develop deep technical enablement programs and training.\n"
    )
    kit = render(corpus, jd, card, select(corpus, card))
    assert "teaches organisations" in kit.markdown
    assert "regulated environments" not in kit.markdown


def test_a_long_bullet_drops_its_mechanism_rather_than_running_on() -> None:
    """Fix 5. Bullets rendered as 40-word claim+mechanism run-ons."""
    corpus, jd, card = _card(
        "Responsibilities\n- Deliver extremely long accomplishments with considerable length.\n"
    )
    kit = render(corpus, jd, card, select(corpus, card))
    for line in kit.markdown.splitlines():
        if line.startswith("- "):
            assert len(line) <= 200, f"bullet line too long to read: {line[:80]}..."


def test_the_skills_block_is_ranked_and_capped() -> None:
    """Fix 6. Twenty-two skills dumped unranked, React second on an AI role."""
    corpus, _jd, card = _card(
        "Minimum qualifications:\n- Experience running technical enablement programs.\n"
    )
    selection = select(corpus, card)
    assert selection.skills[0] == "Technical enablement"
    assert len(selection.skills) <= 16


def test_the_docx_is_single_column_with_no_tables_or_images(tmp_path: Path) -> None:
    """Fix 7. Parsing is the only real gate, so the document must stay plain."""
    import docx

    corpus, jd, card = _card(
        "Responsibilities\n- Develop deep technical enablement programs.\n"
    )
    kit = render(corpus, jd, card, select(corpus, card))
    target = tmp_path / "cv.docx"
    write_docx(kit.document, target)

    doc = docx.Document(str(target))
    assert doc.tables == [], "a table is the most common cause of a parsing failure"
    assert len(doc.inline_shapes) == 0, "no images"

    text = [p.text for p in doc.paragraphs if p.text.strip()]
    assert text[0] == "TEST PERSON", "reading order must match visual order"
    assert any("EXPERIENCE" == t for t in text)
