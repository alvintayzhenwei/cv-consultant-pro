"""Reading a LinkedIn profile PDF: what it takes, and what it refuses to take.

The fixture below is a fictional profile written in LinkedIn's own layout — two
columns on page one, wrapped mid-phrase, several titles grouped under one
employer — because every defect these tests pin came from that shape rather than
from anything a hand-written sample would have shown.

The profession is deliberately not a technology one. A seeder that only works on
the career of the person who wrote it is not a seeder.
"""

from __future__ import annotations

import pytest

from cv_tailor.corpus import load_corpus_text
from cv_tailor.seed import (
    SeedError,
    parse_profile,
    read_pdf,
    to_corpus_yaml,
    to_notes_markdown,
)

# Layout-mode extraction keeps BOTH columns on one line, padded apart — which is
# the single fact that makes page one parseable and made the first attempt fail.
_COL = 51


def _row(left: str = "", right: str = "") -> str:
    return f"    {left}".ljust(_COL) + right


PAGE_ONE = [
    _row("Contact", "Maren Halvorsen"),
    _row("+47 22 00 11 22 (Mobile)"),
    _row("maren.halvorsen@example.no", "Ward Sister, Acute Medical Unit at Bergen"),
    _row("www.linkedin.com/in/maren-", "Sykehus"),
    _row("halvorsen (LinkedIn)", "Bergen, Norway"),
    _row("maren.example.no (Portfolio)"),
    _row("", "Summary"),
    _row("Top Skills", "Twenty years on acute wards. I trained as a nurse in"),
    _row("Acute care", "Bergen and have stayed in acute medicine since &amp; never"),
    _row("Preceptorship", "regretted it."),
    _row("Wound care"),
    _row("Languages"),
    _row("Norwegian"),
    _row("English"),
    _row("Certifications"),
    _row("Advanced Life Support for"),
    _row("Adults"),
    _row("Mentorship and Assessment in"),
    _row("Practice"),
    _row("Immediate Life Support (ILS)"),
    _row("", "Page 1 of 2"),
]

PAGE_TWO = [
    "   ",
    "Experience",
    "Bergen Sykehus",
    "9 years 4 months",
    "Ward Sister, Acute Medical Unit",
    "May 2021 - Present (4 years 5 months)",
    "Bergen, Norway",
    "Led the ward through a full rebuild of the admissions pathway, working",
    "with the medical team and the discharge co-ordinators.",
    "Ran the preceptorship programme for newly registered nurses. Equipment:",
    # The line below is short, unpunctuated and sits directly above the next
    # title, with no employer line between — which is exactly where an employer
    # name would sit. Only the hanging colon above it says otherwise.
    "NPWT, doppler, bladder scanner",
    "Staff Nurse, Acute Medical Unit",
    "January 2017 - May 2021 (4 years 5 months)",
    "Bergen, Norway",
    "Assessed and triaged acute admissions, and carried the ward's complex",
    "wound caseload.",
    "Fjordane Kommune",
    "District Nurse",
    "August 2013 - December 2016 (3 years 5 months)",
    "Sogn og Fjordane, Norway",
    "Ran a rural caseload of housebound patients across a wide area.",
    "Education",
    "Universitetet i Bergen",
    "Bachelor of Nursing, Acute care · (2010 - 2013)",
    "  Page 2 of 2",
]

PAGES = [PAGE_ONE, PAGE_TWO]


@pytest.fixture
def profile():
    return parse_profile(PAGES)


# ── page one is two columns, not one stream ─────────────────────────────────
def test_the_name_is_read_from_the_main_column_not_the_sidebar(profile) -> None:
    """Read as one stream, the first main-column line came out as "Summary"."""
    assert profile.name == "Maren Halvorsen"
    assert profile.location == "Bergen, Norway"


def test_the_sidebar_is_read_as_the_sidebar(profile) -> None:
    assert profile.email == "maren.halvorsen@example.no"
    assert profile.phone is not None and profile.phone.startswith("+47")
    assert profile.top_skills == ["Acute care", "Preceptorship", "Wound care"]
    assert profile.languages == ["Norwegian", "English"]


def test_a_name_wrapped_by_the_narrow_column_is_rejoined(profile) -> None:
    """"Advanced Life Support for" / "Adults" is one certification, not two."""
    assert "Advanced Life Support for Adults" in profile.certifications
    assert "Mentorship and Assessment in Practice" in profile.certifications
    assert "Adults" not in profile.certifications


def test_a_wrapped_url_keeps_the_hyphen_it_wrapped_on(profile) -> None:
    """Prose hyphenates when it wraps; a URL wraps at a hyphen it already owns.

    Treating the two the same silently corrupted the address.
    """
    assert any("in/maren-halvorsen" in link for link in profile.links)
    assert any("maren.example.no" in link for link in profile.links)


def test_the_two_contact_links_stay_two_links(profile) -> None:
    assert len(profile.links) == 2


def test_linkedins_unescaped_entities_do_not_reach_the_corpus(profile) -> None:
    assert "&amp;" not in (profile.headline or "") + " ".join(profile.top_skills)


# ── the career history ──────────────────────────────────────────────────────
def test_every_role_is_found_with_its_dates(profile) -> None:
    assert [role.title for role in profile.roles] == [
        "Ward Sister, Acute Medical Unit",
        "Staff Nurse, Acute Medical Unit",
        "District Nurse",
    ]
    first = profile.roles[0]
    assert (first.start.year, first.start.month) == (2021, 5)
    assert first.is_current and first.end is None
    assert profile.roles[2].end is not None


def test_titles_grouped_under_one_employer_keep_that_employer(profile) -> None:
    """LinkedIn prints the employer once and the titles beneath it."""
    assert [role.org for role in profile.roles] == [
        "Bergen Sykehus",
        "Bergen Sykehus",
        "Fjordane Kommune",
    ]
    assert profile.roles[1].org_inferred is True
    assert profile.roles[0].org_inferred is False


def test_the_tail_of_a_wrapped_sentence_is_not_mistaken_for_an_employer(
    profile,
) -> None:
    """The defect this rule exists for, from a real profile.

    "Equipment used:" leaves its line hanging, so "NPWT, doppler, bladder
    scanner" beneath it is prose — yet it is short and unpunctuated and looks
    exactly like a company name. It was recorded as one.
    """
    assert "NPWT, doppler, bladder scanner" not in {role.org for role in profile.roles}
    assert profile.roles[2].org == "Fjordane Kommune"


def test_the_location_line_is_not_kept_as_a_bullet(profile) -> None:
    assert profile.roles[0].location == "Bergen, Norway"
    assert "Bergen, Norway" not in profile.roles[0].prose


def test_education_is_read(profile) -> None:
    assert profile.education[0].institution == "Universitetet i Bergen"
    assert "Bachelor of Nursing" in profile.education[0].qualification


def test_an_employer_the_parse_had_to_infer_is_named_in_the_notes(profile) -> None:
    """A guess that is not reported is a guess presented as a fact."""
    assert any("carried over" in note for note in profile.notes)


# ── the draft it writes ─────────────────────────────────────────────────────
def test_the_draft_corpus_loads(profile) -> None:
    """A seed that produces a file the validator rejects has seeded nothing."""
    corpus = load_corpus_text(to_corpus_yaml(profile))
    assert len(corpus.roles) == 3
    assert corpus.person.name == "Maren Halvorsen"
    assert corpus.blocking_todos() == []


def test_dates_are_written_in_the_corpus_format_not_the_rendered_one(profile) -> None:
    """Storage is YYYY-MM; a CV prints MM/YYYY. Confusing them failed every role."""
    yaml = to_corpus_yaml(profile)
    assert 'start: "2021-05"' in yaml
    assert "05/2021" not in yaml


def test_an_employer_with_an_awkward_name_survives_yaml(profile) -> None:
    """Real employers begin with digits and contain colons. Quote everything."""
    profile.roles[0].org = "365: Solutions Sdn Bhd"
    corpus = load_corpus_text(to_corpus_yaml(profile))
    assert corpus.roles[0].org == "365: Solutions Sdn Bhd"


def test_role_ids_are_unique_even_when_two_titles_match(profile) -> None:
    profile.roles[1].title = profile.roles[0].title
    profile.roles[1].org = profile.roles[0].org
    corpus = load_corpus_text(to_corpus_yaml(profile))
    assert len({role.id for role in corpus.roles}) == 3


def test_no_bullet_is_invented_from_the_profiles_prose(profile) -> None:
    """The contract, and the reason the notes file exists at all.

    A LinkedIn line is a claim with no mechanism and no tags behind it. Writing
    it into the corpus as a bullet would be the engine authoring evidence — so
    every role comes out empty and the prose goes somewhere that renders nothing.
    """
    corpus = load_corpus_text(to_corpus_yaml(profile))
    assert corpus.all_bullets() == []
    assert "preceptorship programme" not in to_corpus_yaml(profile)


def test_the_prose_is_kept_verbatim_for_the_user_to_work_through(profile) -> None:
    notes = to_notes_markdown(profile)
    assert "Ran the preceptorship programme for newly registered nurses." in notes
    assert "Ward Sister, Acute Medical Unit" in notes
    assert "carried over" in notes


# ── failing honestly ────────────────────────────────────────────────────────
def test_a_missing_file_says_so(tmp_path) -> None:
    with pytest.raises(SeedError) as err:
        read_pdf(tmp_path / "nothing.pdf")
    assert "no such file" in str(err.value)


def test_a_file_that_is_not_a_pdf_says_so_without_a_traceback(tmp_path) -> None:
    decoy = tmp_path / "profile.pdf"
    decoy.write_text("this is not a pdf", encoding="utf-8")
    with pytest.raises(SeedError):
        read_pdf(decoy)


def test_a_profile_with_no_experience_section_says_so_rather_than_seeding_nothing() -> None:
    profile = parse_profile([PAGE_ONE])
    assert profile.roles == []
    assert any("Experience" in note for note in profile.notes)
