"""The tools, and the refusals that are the reason they are tools at all.

A skill is markdown a model may quietly ignore. These tests exist to prove the
server does not: each one puts a tool in a state where the wrong thing is the
easy thing, and asserts it comes back as an error rather than a document.
"""

from __future__ import annotations

import json

import pytest

from cv_consultant_pro import mcp_server
from cv_consultant_pro.session import Session, Stage

from .fixtures import NURSE, TEACHER


def call(tool, **kwargs) -> dict:
    """Invoke a tool the way a host does, and read its JSON back."""
    return json.loads(tool(**kwargs))


@pytest.fixture(autouse=True)
def fresh_session(tmp_path, monkeypatch):
    """A clean session and a real corpus file, per test."""
    corpus = tmp_path / "career-corpus.yaml"
    corpus.write_text(NURSE.corpus, encoding="utf-8")
    monkeypatch.setattr(mcp_server, "_session", Session())
    monkeypatch.setattr(mcp_server, "_preview", None)
    monkeypatch.chdir(tmp_path)
    yield corpus
    if mcp_server._preview is not None:
        mcp_server._preview.stop()


@pytest.fixture
def scored(fresh_session):
    call(mcp_server.cv_validate, corpus_path=str(fresh_session))
    call(mcp_server.cv_preview, layout="signal")
    call(mcp_server.cv_ingest_jd, posting=NURSE.posting)
    return call(mcp_server.cv_score)


# ── every answer carries the next question ──────────────────────────────────
def test_every_tool_says_what_to_do_next(fresh_session) -> None:
    """Without this an agent improvises the conversation, differently each time."""
    result = call(mcp_server.cv_status)
    assert "next_step" in result
    assert result["next_step"]["say"]


def test_an_error_still_says_what_to_do_next() -> None:
    """The moment an agent most needs the script is when something went wrong."""
    result = call(mcp_server.cv_score)
    assert "error" in result
    assert result["next_step"]["then_call"]


def test_a_fresh_session_asks_for_evidence_first() -> None:
    assert call(mcp_server.cv_status)["next_step"]["stage"] == Stage.NO_CORPUS


# ── the pipeline in order ───────────────────────────────────────────────────
def test_scoring_without_a_posting_is_refused_rather_than_guessed(fresh_session) -> None:
    call(mcp_server.cv_validate, corpus_path=str(fresh_session))
    result = call(mcp_server.cv_score)
    assert "error" in result and "posting" in result["error"]


def test_rendering_before_scoring_is_refused(fresh_session) -> None:
    call(mcp_server.cv_validate, corpus_path=str(fresh_session))
    assert "error" in call(mcp_server.cv_render)


def test_an_empty_posting_is_refused(fresh_session) -> None:
    assert "error" in call(mcp_server.cv_ingest_jd, posting="   ")


def test_a_posting_with_no_recognisable_requirements_says_why(fresh_session) -> None:
    result = call(mcp_server.cv_ingest_jd, posting="We are hiring. Apply within.")
    assert "error" in result
    assert "headings" in result["hint"]


def test_the_scorecard_separates_what_disqualifies_from_what_scores(scored) -> None:
    """A missing registration is a closed door, not a low score."""
    assert scored["hard_filters"]
    assert all(
        filt["requirement"] not in [row["requirement"] for row in scored["rows"]]
        for filt in scored["hard_filters"]
    )


def test_a_rendered_kit_lists_every_hole_it_left_visible(scored, tmp_path) -> None:
    result = call(mcp_server.cv_render, out_dir=str(tmp_path / "kit"))
    assert (tmp_path / "kit" / "cv.docx").is_file()
    assert result["submit_this"].endswith("cv.docx")
    assert "traceability" in result
    for hole in result["placeholders"]:
        assert not any(char.isdigit() for char in hole["placeholder"])


# ── the interview's gate ────────────────────────────────────────────────────
def test_no_question_is_served_before_the_user_agrees(scored) -> None:
    """The declaration is a gate. A banner nobody reads would be decoration."""
    call(mcp_server.cv_interview)
    result = call(mcp_server.cv_next_question)
    assert "error" in result
    assert "cv_acknowledge" in result["hint"]


def test_starting_the_interview_returns_the_notice_to_be_shown(scored) -> None:
    result = call(mcp_server.cv_interview)
    assert "your own experience" in result["notice"].lower()
    assert "cv_acknowledge" in result["instruction"]


def test_an_interview_cannot_start_before_there_is_anything_to_ask_about() -> None:
    assert "error" in call(mcp_server.cv_interview)


def test_coaching_carries_its_disclaimer_on_every_question(scored) -> None:
    """Advice presented as fact is the failure mode this whole feature invites."""
    call(mcp_server.cv_interview)
    call(mcp_server.cv_acknowledge)
    question = call(mcp_server.cv_next_question)
    disclaimer = question["coaching_disclaimer"].lower()
    assert "wrong" in disclaimer, "it must say the guidance can be wrong"
    assert "verify" in disclaimer, "and that the user has to check it themselves"


def test_an_agent_cannot_submit_its_own_wording_as_the_users_answer() -> None:
    """The guarantee is the absence of the parameter, not a warning in the text."""
    import inspect

    params = set(inspect.signature(mcp_server.cv_record_answer).parameters)
    assert params == {"question_id", "user_said"}


def test_nothing_reaches_the_cv_until_the_user_confirms_it(scored) -> None:
    call(mcp_server.cv_interview)
    call(mcp_server.cv_acknowledge)
    question = call(mcp_server.cv_next_question)
    recorded = call(
        mcp_server.cv_record_answer,
        question_id=question["id"],
        user_said="I ran that programme for three years.",
    )
    assert all(p["needs_confirmation"] for p in recorded["proposals"])
    assert recorded["next_step"]["stage"] == Stage.EVIDENCE_PENDING


def test_confirming_evidence_marks_anything_already_written_out_of_date(
    scored, tmp_path
) -> None:
    """A kit is a snapshot. Five of six went quietly stale once already."""
    call(mcp_server.cv_render, out_dir=str(tmp_path / "kit"))
    call(mcp_server.cv_interview)
    call(mcp_server.cv_acknowledge)
    question = call(mcp_server.cv_next_question)
    recorded = call(
        mcp_server.cv_record_answer,
        question_id=question["id"],
        user_said="I led the preceptorship programme.",
    )
    result = call(
        mcp_server.cv_confirm_evidence,
        proposal_id=recorded["proposals"][0]["id"],
        verified=False,
    )
    assert result["verified"] is False
    assert call(mcp_server.cv_status)["kit_out_of_date"] is True


# ── the layout preview ──────────────────────────────────────────────────────
def test_the_preview_serves_on_loopback_only(fresh_session) -> None:
    call(mcp_server.cv_validate, corpus_path=str(fresh_session))
    result = call(mcp_server.cv_preview, open_in_browser=False)
    assert result["open_this"].startswith("http://127.0.0.1:")


def test_a_layout_can_be_previewed_before_any_posting_exists(fresh_session) -> None:
    """Layout is chosen first, so the preview must not need a scorecard."""
    call(mcp_server.cv_validate, corpus_path=str(fresh_session))
    assert "error" not in call(mcp_server.cv_preview, open_in_browser=False)


def test_choosing_a_layout_that_a_parser_mishandles_says_so(fresh_session) -> None:
    call(mcp_server.cv_validate, corpus_path=str(fresh_session))
    human = call(mcp_server.cv_preview, layout="rail")
    assert human["portal_safe"] is False
    assert "portal" in human["warning"]
    portal = call(mcp_server.cv_preview, layout="signal")
    assert portal["portal_safe"] is True and portal["warning"] is None


# ── writing back into the corpus ────────────────────────────────────────────
def test_evidence_is_added_to_the_file_the_session_actually_loaded(
    fresh_session, tmp_path
) -> None:
    """It resolved the default path instead once, and wrote to the wrong file."""
    elsewhere = tmp_path / "nested" / "other-corpus.yaml"
    elsewhere.parent.mkdir()
    elsewhere.write_text(NURSE.corpus, encoding="utf-8")
    call(mcp_server.cv_validate, corpus_path=str(elsewhere))

    role_id = mcp_server._session.corpus.roles[0].id
    call(
        mcp_server.cv_corpus_add,
        role_id=role_id,
        claim="Chaired the falls-prevention group",
        mechanism="monthly review of every inpatient fall on the ward",
        tags=["leadership"],
    )
    assert "falls-prevention" in elsewhere.read_text(encoding="utf-8")
    assert "falls-prevention" not in fresh_session.read_text(encoding="utf-8")


def test_a_claim_with_no_mechanism_is_refused(fresh_session) -> None:
    """Half a bullet is an assertion, and an assertion is what a CV is full of."""
    call(mcp_server.cv_validate, corpus_path=str(fresh_session))
    role_id = mcp_server._session.corpus.roles[0].id
    result = call(
        mcp_server.cv_corpus_add,
        role_id=role_id,
        claim="Improved patient flow",
        tags=["flow"],
    )
    assert "error" in result
    assert "HOW" in result["hint"]


def test_an_edit_that_would_break_the_corpus_changes_nothing(fresh_session) -> None:
    call(mcp_server.cv_validate, corpus_path=str(fresh_session))
    before = fresh_session.read_text(encoding="utf-8")
    result = call(
        mcp_server.cv_corpus_add, role_id="no-such-role", start="2020-01", is_current=True
    )
    assert "error" in result
    assert fresh_session.read_text(encoding="utf-8") == before


# ── the account it gives of itself ──────────────────────────────────────────
def test_the_explanation_names_the_gaps_rather_than_softening_them(scored) -> None:
    result = call(mcp_server.cv_explain)
    assert "gaps_from_scoring" in result
    assert "exposure to" in result["reminder"]


def test_there_is_nothing_to_explain_before_anything_is_scored() -> None:
    assert "error" in call(mcp_server.cv_explain)


# ── it is not a tool for one career ─────────────────────────────────────────
def test_the_whole_pipeline_runs_for_a_profession_this_was_not_written_for(
    tmp_path, monkeypatch
) -> None:
    corpus = tmp_path / "teacher.yaml"
    corpus.write_text(TEACHER.corpus, encoding="utf-8")
    call(mcp_server.cv_validate, corpus_path=str(corpus))
    call(mcp_server.cv_preview, layout="ledger")
    call(mcp_server.cv_ingest_jd, posting=TEACHER.posting)
    card = call(mcp_server.cv_score)
    assert card["strong"] + card["partial"] + card["gap"] > 0
    kit = call(mcp_server.cv_render, out_dir=str(tmp_path / "kit"))
    assert kit["roles"] >= 1


# ── the server a host actually sees ─────────────────────────────────────────
def test_every_tool_is_registered_with_the_server() -> None:
    """Calling the functions directly proves nothing about what a host can reach.

    `@mcp.tool()` registers as a side effect and hands the plain function back,
    so every test above would still pass if the decorator were removed and no
    tool were exposed at all. This asks the server itself.
    """
    import asyncio

    registered = {tool.name for tool in asyncio.run(mcp_server.mcp.list_tools())}
    assert registered == {
        "cv_status",
        "cv_seed",
        "cv_validate",
        "cv_corpus_add",
        "cv_preview",
        "cv_ingest_jd",
        "cv_score",
        "cv_render",
        "cv_interview",
        "cv_acknowledge",
        "cv_next_question",
        "cv_record_answer",
        "cv_confirm_evidence",
        "cv_explain",
    }


def test_every_tool_tells_the_agent_how_to_use_it() -> None:
    """A description is the only instruction a host model reliably reads."""
    import asyncio

    for tool in asyncio.run(mcp_server.mcp.list_tools()):
        assert tool.description and len(tool.description) > 80, tool.name


def test_the_tools_that_carry_the_honesty_rules_say_so_where_an_agent_will_read_it() -> None:
    """The rules have to be in the tool description, not only in this repo.

    An agent calling `cv_record_answer` has the description in front of it and
    nothing else. If "the user's own words" is not written there, it does not
    exist as far as the calling model is concerned.
    """
    import asyncio

    described = {t.name: t.description.lower() for t in asyncio.run(mcp_server.mcp.list_tools())}
    assert "own words" in described["cv_record_answer"]
    assert "own words" in described["cv_corpus_add"]
    assert "measured" in described["cv_confirm_evidence"]
    assert "acknowledge" in described["cv_interview"]


def test_the_server_carries_its_rules_where_a_host_loads_them() -> None:
    """Not every host installs the skill; every host reads the server instructions."""
    instructions = mcp_server.mcp.instructions.lower()
    assert "own wording" in instructions
    assert "estimated_placeholder" in instructions
    assert "exposure to" in instructions
    assert "cv_status" in instructions
