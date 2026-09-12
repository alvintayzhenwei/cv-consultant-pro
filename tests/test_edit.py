"""Writing back into a file the user hand-edits.

The corpus is the one artefact a user cannot reconstruct, so these tests are
mostly about what must NOT happen to it: comments surviving, a rejected edit
leaving no trace, and nothing being invented on the way in.
"""

from __future__ import annotations

import pytest

from cv_tailor.corpus import load_corpus_text
from cv_tailor.edit import (
    EditError,
    NewBullet,
    add_bullet,
    add_tags,
    apply,
    set_role_dates,
)

DRAFT = '''# Drafted from a LinkedIn profile PDF. Nothing here is final.

person:
  name: "Maren Halvorsen"

language: en

roles:
  - id: bergen-ward-sister
    org: "Bergen Sykehus"
    title: "Ward Sister"
    start: TODO
    end: present
    location: "Bergen, Norway"
    # Employer carried over from the role above. Check it.
    tags: []          # what this role was about, in your words
    bullets: []       # add with cv_corpus_add, from the notes file
  - id: fjordane-district-nurse
    org: "Fjordane Kommune"
    title: "District Nurse"
    start: "2013-08"
    end: "2016-12"
    tags: ["community"]
    bullets:
      - id: dn-caseload
        claim: "Ran a rural caseload of housebound patients"
        mechanism: "weekly visiting rounds across three valleys"
        tags: ["community"]
'''

BULLET = NewBullet(
    id="ws-preceptorship",
    claim="Ran the preceptorship programme for newly registered nurses",
    mechanism="paired each new nurse with a named mentor for six months",
    tags=["preceptorship", "leadership"],
)


# ── filling in what blocks everything else ──────────────────────────────────
def test_a_date_the_corpus_did_not_know_can_be_filled_in() -> None:
    updated = set_role_dates(DRAFT, "bergen-ward-sister", start="2021-05", end=None, is_current=True)
    corpus = load_corpus_text(updated)
    role = next(r for r in corpus.roles if r.id == "bergen-ward-sister")
    assert role.start is not None and (role.start.year, role.start.month) == (2021, 5)
    assert role.is_current
    assert corpus.blocking_todos() == []


def test_a_date_in_the_wrong_shape_is_refused_before_it_reaches_the_file() -> None:
    with pytest.raises(EditError) as err:
        set_role_dates(DRAFT, "bergen-ward-sister", start="May 2021", end=None, is_current=True)
    assert "YYYY-MM" in str(err.value)


def test_editing_a_role_that_is_not_there_says_so() -> None:
    with pytest.raises(EditError) as err:
        set_role_dates(DRAFT, "no-such-role", start="2021-05", end=None, is_current=True)
    assert "no-such-role" in str(err.value)


def test_only_the_named_role_is_touched() -> None:
    updated = set_role_dates(DRAFT, "bergen-ward-sister", start="2021-05", end=None, is_current=True)
    assert 'start: "2013-08"' in updated
    assert 'end: "2016-12"' in updated


# ── adding evidence ─────────────────────────────────────────────────────────
def test_a_bullet_can_be_added_to_a_role_that_had_none() -> None:
    updated = add_bullet(DRAFT, "bergen-ward-sister", BULLET)
    corpus = load_corpus_text(updated)
    role = next(r for r in corpus.roles if r.id == "bergen-ward-sister")
    assert [b.id for b in role.bullets] == ["ws-preceptorship"]
    assert role.bullets[0].claim == BULLET.claim
    assert role.bullets[0].mechanism == BULLET.mechanism


def test_a_bullet_is_appended_to_a_role_that_already_has_some() -> None:
    updated = add_bullet(DRAFT, "fjordane-district-nurse", BULLET)
    role = next(r for r in load_corpus_text(updated).roles if r.id == "fjordane-district-nurse")
    assert [b.id for b in role.bullets] == ["dn-caseload", "ws-preceptorship"]


def test_a_measured_figure_is_recorded_as_measured() -> None:
    bullet = NewBullet(**{**BULLET.__dict__, "metric_value": "12 nurses a year"})
    role = next(
        r
        for r in load_corpus_text(add_bullet(DRAFT, "bergen-ward-sister", bullet)).roles
        if r.id == "bergen-ward-sister"
    )
    assert role.bullets[0].metric is not None
    assert role.bullets[0].metric.verified is True
    assert role.bullets[0].metric.value == "12 nurses a year"


def test_an_estimate_is_recorded_as_a_visible_hole_not_a_number() -> None:
    """The anti-fabrication contract, at the one point where text enters."""
    bullet = NewBullet(
        **{
            **BULLET.__dict__,
            "claim": "Ran the preceptorship programme for [N] newly registered nurses a year",
            "placeholder": "[N]",
        }
    )
    role = next(
        r
        for r in load_corpus_text(add_bullet(DRAFT, "bergen-ward-sister", bullet)).roles
        if r.id == "bergen-ward-sister"
    )
    assert role.bullets[0].metric is not None
    assert role.bullets[0].metric.verified is False
    assert role.bullets[0].has_placeholder


def test_a_placeholder_that_appears_nowhere_in_the_sentence_is_refused() -> None:
    """It would load, render nothing, and leave the hole invisible.

    The point of a placeholder is that the reader SEES the gap — a metric that
    renders off the page is a claim with a missing figure, silently.
    """
    with pytest.raises(EditError) as err:
        NewBullet(**{**BULLET.__dict__, "placeholder": "[N] nurses a year"})
    assert "appear in the claim" in str(err.value)


def test_a_figure_cannot_be_both_measured_and_estimated() -> None:
    with pytest.raises(EditError):
        NewBullet(**{**BULLET.__dict__, "metric_value": "12", "placeholder": "[N]"})


def test_a_bullet_with_no_tags_is_refused() -> None:
    """It would load and then never match anything, which is worse than an error."""
    with pytest.raises(EditError):
        NewBullet(**{**BULLET.__dict__, "tags": []})


def test_a_claim_containing_a_colon_survives_the_round_trip() -> None:
    """Unquoted, "Migrated: phase one" is a YAML mapping, not a sentence."""
    bullet = NewBullet(**{**BULLET.__dict__, "claim": "Migrated: phase one, then the rest"})
    role = next(
        r
        for r in load_corpus_text(add_bullet(DRAFT, "bergen-ward-sister", bullet)).roles
        if r.id == "bergen-ward-sister"
    )
    assert role.bullets[0].claim == "Migrated: phase one, then the rest"


# ── tags ────────────────────────────────────────────────────────────────────
def test_tags_can_be_given_to_a_role_that_had_none() -> None:
    role = next(
        r
        for r in load_corpus_text(add_tags(DRAFT, "bergen-ward-sister", ["acute", "leadership"])).roles
        if r.id == "bergen-ward-sister"
    )
    assert role.tags == ["acute", "leadership"]


def test_adding_a_tag_keeps_the_ones_already_there() -> None:
    role = next(
        r
        for r in load_corpus_text(add_tags(DRAFT, "fjordane-district-nurse", ["rural"])).roles
        if r.id == "fjordane-district-nurse"
    )
    assert role.tags == ["community", "rural"]


# ── what the file looks like afterwards ─────────────────────────────────────
def test_the_users_own_comments_survive_an_edit() -> None:
    """A tool that reformats your file every time is one you stop using on it."""
    updated = add_bullet(DRAFT, "bergen-ward-sister", BULLET)
    assert "# Drafted from a LinkedIn profile PDF. Nothing here is final." in updated
    assert "# Employer carried over from the role above. Check it." in updated


def test_an_untouched_role_is_byte_identical_afterwards() -> None:
    updated = add_bullet(DRAFT, "bergen-ward-sister", BULLET)
    tail = DRAFT[DRAFT.index("  - id: fjordane-district-nurse") :]
    assert tail in updated


# ── saving ──────────────────────────────────────────────────────────────────
def test_an_edit_is_saved_when_it_leaves_a_valid_corpus(tmp_path) -> None:
    path = tmp_path / "career-corpus.yaml"
    path.write_text(DRAFT, encoding="utf-8")
    apply(path, lambda text: add_bullet(text, "bergen-ward-sister", BULLET))
    assert "ws-preceptorship" in path.read_text(encoding="utf-8")


def test_an_edit_that_would_break_the_corpus_writes_nothing_at_all(tmp_path) -> None:
    """Half an edit to the one file the user cannot reconstruct is the worst case."""
    path = tmp_path / "career-corpus.yaml"
    path.write_text(DRAFT, encoding="utf-8")
    with pytest.raises(EditError) as err:
        apply(path, lambda text: text.replace('claim: "Ran a rural', "claim: ["))
    assert "nothing was written" in str(err.value)
    assert path.read_text(encoding="utf-8") == DRAFT


def test_a_duplicate_bullet_id_is_refused_rather_than_saved(tmp_path) -> None:
    path = tmp_path / "career-corpus.yaml"
    path.write_text(DRAFT, encoding="utf-8")
    clash = NewBullet(**{**BULLET.__dict__, "id": "dn-caseload"})
    with pytest.raises(EditError):
        apply(path, lambda text: add_bullet(text, "bergen-ward-sister", clash))
    assert path.read_text(encoding="utf-8") == DRAFT


def test_editing_a_corpus_that_is_not_there_says_so(tmp_path) -> None:
    with pytest.raises(EditError) as err:
        apply(tmp_path / "missing.yaml", lambda text: text)
    assert "no corpus" in str(err.value)
