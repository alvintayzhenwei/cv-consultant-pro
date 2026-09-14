"""The MCP server — cv-consultant-pro for Claude Code, Codex, and anything else.

Every plugin system worth the name bundles MCP servers, so this is the payload
that both plugin manifests wrap. It is also why the guarantees live *here* and
not in a skill: a skill is markdown loaded into a model's context, and a model
may disregard it — quietly, in exactly the cases that matter most. A running
process returns an error.

So each tool REFUSES rather than warns:

  * rendering refuses a corpus that does not validate, and refuses any bullet it
    cannot trace back to a corpus id;
  * the interview refuses to serve a question until the authenticity notice has
    been acknowledged;
  * confirming evidence refuses text that did not arrive through
    `cv_record_answer` — there is no parameter for an agent's own wording,
    because the guarantee is the absence of the API rather than a warning in a
    docstring.

Tools also return the next beat of the conversation alongside their result, so
the host agent knows what to ask next without inventing it. A bag of tools with
no script produces a different interview on every model; see session.py.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .corpus import resolve_corpus_path
from .docx import write_docx
from .edit import (
    EditError,
    NewBullet,
    add_bullet,
    add_tags,
    apply,
    set_metric,
    set_role_dates,
)
from .interview import (
    COACHING_DISCLAIMER,
    ELABORATE_PROMPT,
    InterviewError,
    interview_from_scorecard,
)
from .jd import parse_jd
from .match import Scorecard, Verdict, score
from .preview import start_preview
from .render import AuditError, build_document, render, select, summary_choices
from .seed import SeedError, seed_from_pdf, to_corpus_yaml, to_notes_markdown
from .session import Session
from .templates import TEMPLATES, get_template, render_html

#: Loaded by the host alongside the tool list, so it reaches clients that never
#: install the skill. Kept short deliberately - an instruction block long enough
#: to skim is an instruction block that gets skimmed.
INSTRUCTIONS = """cv-consultant-pro builds a CV by SELECTING from the user's own career
evidence. It never authors a claim and never invents a figure.

Call cv_status first. Every tool returns a next_step saying which stage the
session is in, what to say to the user, and what to call next - read that out
rather than improvising around it, and call cv_status again whenever a result
surprises you.

Three rules the tools enforce and you must not work around:

1. Pass the user's OWN wording to cv_record_answer and cv_corpus_add. Never a
   tidied, expanded or improved version, and never your own suggested answer.
   If what they said is too thin, ask them for more.
2. A figure is measured or it is a hole. Only pass measured_figure when the user
   says it was counted; otherwise write the claim with a bracketed gap and pass
   that gap as estimated_placeholder.
3. A gap stays a gap. Never soften "I have not done that" into "exposure to".

Report the score before rendering anything, and lead with any hard filter - a
registration or right-to-work requirement disqualifies rather than scores."""

mcp = FastMCP("cv-consultant-pro", instructions=INSTRUCTIONS)

#: One session per server process. A stdio MCP server serves a single client,
#: and sharing a corpus between clients would be a privacy failure rather than a
#: feature.
_session = Session()
#: The layout preview, if one is open. Held so it can be closed rather than left
#: serving a career history for the life of the process.
_preview = None


def _ok(payload: dict[str, Any]) -> str:
    """Every result carries the next beat, so the agent never has to guess."""
    payload["next_step"] = _session.next_step().as_dict()
    return json.dumps(payload, indent=2, default=str)


def _err(message: str, *, hint: str | None = None) -> str:
    payload: dict[str, Any] = {"error": message}
    if hint:
        payload["hint"] = hint
    payload["next_step"] = _session.next_step().as_dict()
    return json.dumps(payload, indent=2, default=str)


#: Words that make a number a recollection rather than a measurement.
#:
#: Deliberately NOT a ban on hedged figures — "~45 minutes to seconds" and
#: "around 2 months" are honest, because the hedge is the user's own and travels
#: with the claim onto the CV, where they can defend it. These are different:
#: they mark the speaker as unsure WHICH number it was, and an unsure number
#: presented as measured is the thing this tool exists not to do.
_UNSURE = ("i think", "i guess", "not sure", "unsure", "maybe", "can't remember",
           "cannot remember", "or thereabouts", "something like", "no idea")


def _figure_problem(figure: str) -> str | None:
    """Why this string is not a measured figure, or None if it is one."""
    text = figure.strip()
    if not text:
        return "a measured figure cannot be blank"
    if not any(ch.isdigit() for ch in text):
        return f"{text!r} carries no number, so it cannot be a measured figure"
    if len(text) > 40:
        return (
            f"{text!r} is a sentence, not a figure. Pass just the measurement "
            "and let the claim carry the rest."
        )
    lowered = text.lower()
    hedge = next((word for word in _UNSURE if word in lowered), None)
    if hedge:
        return (
            f"{text!r} says {hedge!r}, so it is a recollection rather than a "
            "measurement. Record it as a placeholder instead — a visible gap is "
            "honest, a remembered number presented as measured is not."
        )
    return None


# ── where we are ────────────────────────────────────────────────────────────
@mcp.tool()
def cv_status() -> str:
    """Where this session is, what is missing, and the exact question to ask next.

    Call this first, and any time you are unsure what to do. It drives the whole
    conversation: read `next_step.say` out rather than improvising around it,
    then call `next_step.then_call`.
    """
    corpus = _session.corpus
    return _ok(
        {
            "corpus_loaded": corpus is not None,
            "corpus_path": str(resolve_corpus_path(None)),
            "roles": len(corpus.roles) if corpus else 0,
            "bullets": len(corpus.all_bullets()) if corpus else 0,
            "outstanding": [
                {"ref": t.ref, "what": t.what, "blocks_rendering": t.blocking}
                for t in (corpus.todos() if corpus else [])
            ],
            "layout": _session.layout,
            "has_posting": _session.jd is not None,
            "scored": _session.card is not None,
            "kit": str(_session.kit_dir) if _session.kit_dir else None,
            "kit_out_of_date": _session.kit_stale,
        }
    )


# ── evidence in ─────────────────────────────────────────────────────────────
@mcp.tool()
def cv_seed(pdf_path: str, out_path: str = "career-corpus.yaml") -> str:
    """Draft a corpus from a LinkedIn profile PDF (your profile → Save to PDF).

    Reads what the page states — employers, titles, dates, certifications,
    education — and writes a draft corpus plus a notes file holding the
    profile's own prose, verbatim.

    It writes NO bullets, and that is deliberate. A bullet needs a claim, the
    mechanism behind it and its tags; a profile carries only the first. Work
    through the notes file with the user and add each one with `cv_corpus_add`,
    in their words.
    """
    try:
        profile = seed_from_pdf(pdf_path)
    except SeedError as exc:
        return _err(str(exc))

    target = Path(out_path)
    if target.exists():
        return _err(
            f"{target} already exists",
            hint="Seeding would overwrite a corpus. Point out_path somewhere else.",
        )
    notes = target.with_suffix(".notes.md")
    target.write_text(to_corpus_yaml(profile), encoding="utf-8", newline="\n")
    notes.write_text(to_notes_markdown(profile), encoding="utf-8", newline="\n")

    _session.load(str(target))
    return _ok(
        {
            "corpus": str(target),
            "notes": str(notes),
            "name": profile.name,
            "roles": [
                {
                    "title": role.title,
                    "org": role.org,
                    "employer_carried_over": role.org_inferred,
                    "lines_of_prose": len(role.prose),
                }
                for role in profile.roles
            ],
            "certifications": profile.certifications,
            "check_these": profile.notes,
            "instruction": (
                "Show the user what was found and ask them to confirm the employers "
                "marked as carried over. Then work down the notes file one line at a "
                "time — for each, ask how they actually did it, which is the part a "
                "profile never says."
            ),
        }
    )


@mcp.tool()
def cv_validate(corpus_path: str | None = None) -> str:
    """Load the career corpus and report every problem and every gap at once.

    Problems are refusals: the corpus will not load until they are fixed.
    Outstanding items are holes the user still has to fill — unknown dates, and
    figures nobody has measured — which load fine and must never be guessed at.
    """
    _session.load(corpus_path)
    if _session.corpus_error:
        return _err("corpus is not valid", hint="walk through these one at a time")
    corpus = _session.corpus
    assert corpus is not None
    return _ok(
        {
            "valid": True,
            "path": str(resolve_corpus_path(corpus_path)),
            "roles": len(corpus.roles),
            "bullets": len(corpus.all_bullets()),
            "skills": len(corpus.skills),
            "positions": len(corpus.positions),
            "outstanding": [
                {"ref": t.ref, "what": t.what, "blocks_rendering": t.blocking}
                for t in corpus.todos()
            ],
        }
    )


@mcp.tool()
def cv_corpus_add(
    role_id: str,
    claim: str | None = None,
    mechanism: str | None = None,
    tags: list[str] | None = None,
    bullet_id: str | None = None,
    measured_figure: str | None = None,
    estimated_placeholder: str | None = None,
    start: str | None = None,
    end: str | None = None,
    is_current: bool = False,
    role_tags: list[str] | None = None,
) -> str:
    """Add one thing to the corpus — a date, a role's tags, or a piece of evidence.

    `claim` and `mechanism` must both be the USER'S OWN WORDS. Do not tidy,
    expand or improve them, and never supply your own version of what they
    probably meant: this text is what lands on their CV and what they will be
    asked about in an interview.

    A figure goes in `measured_figure` only if the user said it was actually
    measured. If it is an estimate, write the claim with a bracketed hole in it
    ("trained [N] nurses a year") and pass that hole as `estimated_placeholder`
    — it renders as a visible gap rather than a number they would have to
    defend.

    Dates go in as YYYY-MM. `is_current` replaces `end`.
    """
    path = str(_session.corpus_path) if _session.corpus_path else None
    try:
        if start:
            apply(
                path,
                lambda text: set_role_dates(
                    text, role_id, start=start, end=end, is_current=is_current
                ),
            )
        if role_tags:
            apply(path, lambda text: add_tags(text, role_id, role_tags))
        if claim:
            if not mechanism:
                return _err(
                    "a claim with no mechanism is an assertion",
                    hint=(
                        "Ask the user HOW they brought it about. That is the half a "
                        "profile never states, and the half that makes a bullet evidence."
                    ),
                )
            bullet = NewBullet(
                id=bullet_id or _suggest_bullet_id(role_id, claim),
                claim=claim,
                mechanism=mechanism,
                tags=tags or [],
                metric_value=measured_figure,
                placeholder=estimated_placeholder,
            )
            apply(path, lambda text: add_bullet(text, role_id, bullet))
    except EditError as exc:
        return _err(str(exc))

    _session.load(path)
    _session.kit_stale = _session.kit_dir is not None
    return _ok({"added_to": role_id})


def _suggest_bullet_id(role_id: str, claim: str) -> str:
    words = [word for word in claim.lower().split() if word.isalnum()][:3]
    return f"{role_id[:20]}-{'-'.join(words)}"[:48].strip("-")


# ── choosing a layout ───────────────────────────────────────────────────────
@mcp.tool()
def cv_preview(layout: str | None = None, open_in_browser: bool = True) -> str:
    """Show the five layouts in a browser, with the user's own CV in them.

    Choosing from five prose descriptions is guessing. This renders all five and
    serves them on 127.0.0.1 only, on a random port behind a random token, for
    as long as this session lasts.

    Portal-safe layouts are single column with no sidebar, icons or images,
    because parsing is the only hard gate on an application. The other two look
    better by doing what a parser mishandles — say so, rather than leaving the
    user to find out. Call again with a `layout` id to choose one.
    """
    global _preview

    if layout:
        template = get_template(layout)
        _session.layout = template.id
        return _ok(
            {
                "chosen": template.id,
                "portal_safe": template.ats_safe,
                "warning": None
                if template.ats_safe
                else "Submit cv.docx through a portal; send this one to a person.",
            }
        )

    if _session.corpus is None:
        return _err("no corpus loaded", hint="call cv_validate first")

    # A layout is chosen before a posting exists, so the preview must not depend
    # on one: with no scorecard the selection simply ranks on its own merits.
    card = _session.card or Scorecard()
    document, _trace, _placeholders = build_document(
        _session.corpus, _session.jd or parse_jd(""), card, select(_session.corpus, card)
    )
    if _preview is not None:
        _preview.stop()
    _preview = start_preview(document, open_browser=open_in_browser)
    return _ok(
        {
            "open_this": _preview.url,
            "layouts": [
                {
                    "id": t.id,
                    "name": t.name,
                    "blurb": t.blurb,
                    "portal_safe": t.ats_safe,
                }
                for t in TEMPLATES.values()
            ],
            "instruction": (
                "Give the user the URL, say which layouts are portal-safe and why, "
                "then call cv_preview again with their choice."
            ),
        }
    )


# ── the posting ─────────────────────────────────────────────────────────────
@mcp.tool()
def cv_ingest_jd(posting: str, title: str | None = None) -> str:
    """Read a job posting into structured requirements.

    Pass the posting text. Minimum and preferred are split by the posting's own
    headings, and eligibility filters — registration, licensure, right to work,
    a years threshold — are kept separate from scored requirements, because
    failing one of those is a closed door rather than a low score.
    """
    if not posting.strip():
        return _err("no posting supplied")
    jd = parse_jd(posting, title=title)
    if not jd.requirements:
        return _err(
            "no requirements found",
            hint=(
                "The parser reads a posting's own headings — Minimum qualifications, "
                "Essential criteria, Person specification, Responsibilities and the "
                "like. Check they survived the copy and paste."
            ),
        )
    _session.jd = jd
    _session.card = None
    return _ok(
        {
            "title": jd.title,
            "requirements": len(jd.requirements),
            "hard_filters": [r.text for r in jd.requirements if r.is_hard_filter],
        }
    )


@mcp.tool()
def cv_score() -> str:
    """Score the corpus against the posting: strong, partial or gap, with evidence.

    Report this to the user BEFORE rendering anything. A finished-looking
    document buries the gaps, and the gaps are the most useful thing here. Hard
    filters are listed separately and are not averaged into anything — they
    disqualify, and only the user can answer them.
    """
    if _session.corpus is None:
        return _err("no corpus loaded", hint="call cv_validate first")
    if _session.jd is None:
        return _err("no posting", hint="call cv_ingest_jd first")

    card = score(_session.jd, _session.corpus)
    _session.card = card
    return _ok(
        {
            "strong": len(card.by_verdict(Verdict.STRONG)),
            "partial": len(card.by_verdict(Verdict.PARTIAL)),
            "gap": len(card.by_verdict(Verdict.GAP)),
            "rows": [
                {
                    "requirement": r.requirement.text,
                    "verdict": str(r.verdict),
                    "evidence": r.evidence_ids,
                    "note": r.note,
                }
                for r in card.rows
            ],
            "hard_filters": [
                {
                    "requirement": r.requirement.text,
                    "note": r.note,
                    "years_required": r.requirement.years_required,
                    "years_evidenced": r.evidenced_years,
                }
                for r in card.hard_filters
            ],
        }
    )


@mcp.tool()
def cv_summary(summary_id: str | None = None) -> str:
    """Show the user their own summaries and let them choose which opens the CV.

    Call with no argument to list them. Show the WHOLE list and say plainly what
    the choice is:

      * **tailored to this posting** — the marked one. Right when this CV is
        going to this employer for this role.
      * **general** — any of the others. Right when the CV lands in a
        centralised talent pool, where one stored document has to answer every
        search and a posting-shaped opening misrepresents them for the rest.

    Then call again with their chosen `summary_id`. Do not pick for them: the
    opening paragraph is a claim about who they are, and they wrote all of these.
    """
    if _session.corpus is None or _session.card is None:
        return _err("score a posting first", hint="call cv_score")

    if summary_id:
        known = {s.id for s in _session.corpus.summaries}
        if summary_id not in known:
            return _err(
                f"no summary with id {summary_id!r}",
                hint=f"the corpus holds: {sorted(known)}",
            )
        _session.summary_id = summary_id
        _session.kit_stale = _session.kit_dir is not None
        return _ok({"chosen": summary_id})

    title = _session.jd.title if _session.jd else None
    choices = summary_choices(_session.corpus, _session.card, title=title)
    if not choices:
        return _err(
            "the corpus holds no summary",
            hint=(
                "The CV will open without one rather than with an invented "
                "paragraph. Offer to add one with cv_corpus_add."
            ),
        )
    return _ok(
        {
            "summaries": [
                {
                    "id": c.id,
                    "text": c.text,
                    "tags": c.tags,
                    "matches_this_posting": c.jd_match,
                }
                for c in choices
            ],
            "instruction": (
                "Read the list out. Say which one this posting would pick and why, then "
                "ask: is this CV going to THIS employer, or into a talent pool where one "
                "document answers every search? Call cv_summary again with their choice."
            ),
        }
    )



@mcp.tool()
def cv_fill_placeholder(
    bullet_id: str | None = None,
    measured_figure: str | None = None,
    keep_placeholder: bool = False,
) -> str:
    """Settle a figure that would otherwise render as a hole on the CV.

    Call with no argument to see which placeholders will appear on THIS CV —
    only those, not every hole in the corpus.

    Then, for each, ask the user and call again:

      * `measured_figure` — a real number they actually measured. It replaces
        the placeholder and renders as a figure.
      * `keep_placeholder=True` — they do not have one. The bullet keeps its
        visible gap, which is honest and often better than a vague number.

    Never supply a figure yourself, and never talk them into one. A number on a
    CV is something they will be asked to defend in a room.
    """
    if _session.corpus is None or _session.card is None:
        return _err("score a posting first", hint="call cv_score")

    holes = _session.pending_placeholders()
    if not bullet_id:
        if not holes:
            _session.figures_settled = True
        return _ok({"placeholders": holes, "count": len(holes)})

    known = {h["bullet"] for h in holes}
    if bullet_id not in known:
        return _err(
            f"{bullet_id!r} carries no placeholder on this CV",
            hint=f"the ones that will appear are: {sorted(known)}",
        )

    if keep_placeholder:
        _session.acknowledged_placeholders.add(bullet_id)
    elif measured_figure:
        # There is no verbatim answer to check against here — this tool edits the
        # corpus directly — so the check is on the SHAPE. An outside tester got
        # "roughly 30 I think, maybe 40" written as `verified: true`, one line
        # under a claim saying nobody ever ran the numbers.
        problem = _figure_problem(measured_figure)
        if problem:
            return _err(
                problem,
                hint=(
                    "If they do not have a measured number, call again with "
                    "keep_placeholder=True. The bullet keeps its visible gap, which "
                    "is honest and often better than a vague number."
                ),
            )
        path = str(_session.corpus_path) if _session.corpus_path else None
        try:
            apply(path, lambda text: set_metric(text, bullet_id, measured_figure))
        except EditError as exc:
            return _err(str(exc))
        _session.load(path)
        _session.kit_stale = _session.kit_dir is not None
    else:
        return _err(
            "say which it is",
            hint=(
                "Either pass measured_figure with a number the user actually measured, "
                "or keep_placeholder=True if they do not have one."
            ),
        )

    remaining = [
        h for h in _session.pending_placeholders()
        if h["bullet"] not in _session.acknowledged_placeholders
    ]
    if not remaining:
        _session.figures_settled = True
    return _ok({"settled": bullet_id, "remaining": remaining})



# ── the document ────────────────────────────────────────────────────────────
@mcp.tool()
def cv_render(out_dir: str = "kits/latest", target: str | None = None) -> str:
    """Write the application kit. Refuses anything it cannot trace to the corpus.

    Produces cv.md, cv.docx (the format to submit through a portal) and cv.html
    in the chosen layout, along with the placeholders still to fill and the
    bullet-by-bullet traceability. An unverified figure renders as its
    placeholder and is never guessed at.

    `target` is the line under the name. It defaults to the posting title, which
    is right when applying for that posting and wrong when the CV goes anywhere
    else: uploaded to a centralised candidate pool it claims an application that
    was never made. Ask the user where this CV is going. For a pool, pass a short
    headline a recruiter would search, or "current" for their current role
    title, or "none" to leave the line off.
    """
    if _session.corpus is None or _session.jd is None or _session.card is None:
        return _err("not ready to render", hint="call cv_validate, cv_ingest_jd, cv_score")

    template = get_template(_session.layout)
    selection = select(_session.corpus, _session.card)
    try:
        kit = render(
            _session.corpus,
            _session.jd,
            _session.card,
            selection,
            summary_id=_session.summary_id,
            target=target,
        )
    except AuditError as exc:
        return _err(f"the audit refused to write this: {exc}")

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "cv.md").write_text(kit.markdown, encoding="utf-8", newline="\n")
    write_docx(kit.document, out / "cv.docx")
    (out / "cv.html").write_text(
        render_html(kit.document, template), encoding="utf-8", newline="\n"
    )

    _session.kit_dir = out
    _session.kit_stale = False
    return _ok(
        {
            "kit": str(out),
            "layout": template.id,
            "portal_safe": template.ats_safe,
            "submit_this": str(out / "cv.docx"),
            # No PDF is generated, and that is a decision rather than an
            # omission: producing one needs a browser engine or a native
            # toolchain, and this installs with `uvx` and four pure
            # dependencies. The HTML is already print-ready — A4 @page, zero
            # margin, colour-adjust on — so the browser the user already has
            # renders it exactly. That only helps if the tool says so.
            "pdf": (
                f"Open {out / 'cv.html'} in a browser and print to PDF. Set paper to "
                "A4, margins to None, and turn Background graphics ON — without it a "
                "name band or a coloured rail prints white and the layout falls apart."
            ),
            "docx_note": (
                "cv.docx deliberately ignores the chosen layout. It is the SUBMIT "
                "format: one column, no tables, a standard font, dull on purpose, "
                "because parsing is the only hard gate on an application and several "
                "of these layouts look good precisely by doing what a parser "
                "mishandles. Send cv.html or its PDF to a person; send cv.docx to a "
                "portal."
            ),
            "roles": len(kit.document.roles),
            "dropped_roles": selection.dropped_roles,
            "placeholders": [{"bullet": b, "placeholder": p} for b, p in kit.placeholders],
            "traceability": [{"bullet": b, "claim": c} for b, c in kit.traceability],
        }
    )


# ── the interview ───────────────────────────────────────────────────────────
@mcp.tool()
def cv_interview() -> str:
    """Start the interview. Returns the authenticity notice, which MUST be shown.

    Ten questions, weighted toward what the corpus cannot yet answer — because a
    question about something already evidenced is a rehearsal, while a question
    about a gap is where genuinely unrecorded experience surfaces.

    Show `notice` to the user and get their agreement before calling
    `cv_acknowledge`. No question is served until you do.
    """
    if _session.card is None or _session.corpus is None:
        return _err("score a posting first", hint="call cv_score")
    _session.interview = interview_from_scorecard(_session.card, _session.corpus)
    return _ok(
        {
            "notice": _session.interview.notice(),
            "questions": len(_session.interview.questions),
            "instruction": (
                "Show the notice as it is written. Ask the user to confirm the answers "
                "will be their own experience. Then call cv_acknowledge."
            ),
        }
    )


@mcp.tool()
def cv_acknowledge() -> str:
    """Record that the user has agreed the answers will be their own experience.

    Call this only after they have actually said so. It unlocks the questions.
    """
    if _session.interview is None:
        return _err("no interview", hint="call cv_interview first")
    _session.interview.acknowledge()
    return _ok({"acknowledged": True})


@mcp.tool()
def cv_next_question() -> str:
    """The next question, what it is probing, and the standing disclaimer.

    ASK IT AND STOP. Do not offer a model answer, an example, or a list of what
    a good answer contains — the user answers the suggestion instead of the
    question, and ten such asides lose the thread of the interview entirely.
    Coaching happens ONCE, at the end, through `cv_interview_summary`.

    Say the `elaborate` line with the question. Shown what the corpus already
    holds, people repeat it back; the answer is only worth recording where it
    goes beyond what is on record.

    Then record their reply verbatim with `cv_record_answer`.
    """
    if _session.interview is None:
        return _err("no interview", hint="call cv_interview first")
    try:
        question = _session.interview.next_question()
    except InterviewError as exc:
        return _err(str(exc), hint="call cv_acknowledge once the user has agreed")
    if question is None:
        return _ok({"done": True})
    answered, total = _session.interview.progress()
    return _ok(
        {
            "id": question.id,
            "question": question.text,
            "requirement": question.requirement,
            "verdict": str(question.verdict),
            "preparedness": str(question.preparedness),
            "position_id": question.position_id,
            "probes": question.probes,
            "progress": f"{answered + 1} of {total}",
            "elaborate": ELABORATE_PROMPT,
            "instruction": (
                "Ask the question and stop. Do NOT suggest an answer, give an example, "
                "or list what a strong answer contains — that arrives before they have "
                "thought, and they answer it instead of the question. Say the "
                "`elaborate` line with it. Record their reply verbatim with "
                "cv_record_answer, then call cv_next_question. Coaching comes once, at "
                "the end, from cv_interview_summary."
            ),
            "coaching_disclaimer": COACHING_DISCLAIMER,
        }
    )


@mcp.tool()
def cv_interview_summary() -> str:
    """The whole interview in one table, once every question has been put.

    Coaching used to happen question by question, which cost the user the thread
    of the interview: each aside invited a discussion, and the next question
    arrived after it. This is the one place it belongs — every question beside
    what they actually said, read in a single sitting when nothing is riding on
    the next answer.

    The `recommended_answer` column comes back EMPTY. This server runs no model
    and has no business inventing advice; fill each cell yourself, from the
    requirement and their answer, and show `coaching_disclaimer` beneath the
    table. Nothing here reaches the corpus — a recommendation is preparation for
    a room, never a claim on a CV.
    """
    if _session.interview is None:
        return _err("no interview", hint="call cv_interview first")

    interview = _session.interview
    answered, total = interview.progress()
    rows = []
    for question in interview.questions:
        answer = interview.answers.get(question.id)
        rows.append(
            {
                "question_id": question.id,
                "question": question.text,
                "requirement": question.requirement,
                "verdict": str(question.verdict),
                "answered": answer.user_said if answer else None,
                "confirms_gap": bool(answer and answer.confirms_gap),
                "proposals": [p.id for p in answer.proposals] if answer else [],
                "recommended_answer": "",
            }
        )
    return _ok(
        {
            "answered": answered,
            "total": total,
            "rows": rows,
            "confirmed_gaps": interview.confirmed_gaps(),
            "instruction": (
                "Render this as a table: question, what they answered, and your "
                "recommended answer. Write the recommendation column yourself — the "
                "server supplies the column, not the advice. Mark a row with "
                "confirms_gap as a confirmed gap and recommend nothing for it: it "
                "stays off the CV rather than being softened. Show the "
                "coaching_disclaimer under the table."
            ),
            "coaching_disclaimer": COACHING_DISCLAIMER,
        }
    )


@mcp.tool()
def cv_record_answer(question_id: str, user_said: str) -> str:
    """Record the user's answer VERBATIM, and propose evidence drawn from it.

    `user_said` must be the user's own words, exactly as they gave them. Do not
    pass a tidied, expanded or improved version, and never pass a suggested
    answer of your own: what goes in here is what may end up on their CV, and
    what they will be asked to stand behind.

    An admission of inexperience proposes nothing and is recorded as a confirmed
    gap — which stays off the CV rather than being softened into "exposure to".
    """
    if _session.interview is None:
        return _err("no interview", hint="call cv_interview first")
    try:
        answer = _session.interview.record_answer(question_id, user_said)
    except InterviewError as exc:
        return _err(str(exc))
    return _ok(
        {
            "recorded": answer.question_id,
            "confirms_gap": answer.confirms_gap,
            "proposals": [
                {
                    "id": p.id,
                    "claim": p.claim,
                    "figure": p.metric_value,
                    "needs_confirmation": True,
                }
                for p in answer.proposals
            ],
            "instruction": (
                "Read any proposal back to the user in their own words, and ask whether "
                "a figure in it was measured or is an estimate. Nothing is written "
                "until cv_confirm_evidence is called."
            )
            if answer.proposals
            else "Nothing proposed — move on to the next question.",
        }
    )


@mcp.tool()
def cv_confirm_evidence(
    proposal_id: str,
    verified: bool,
    role_id: str | None = None,
    mechanism: str | None = None,
    claim: str | None = None,
    measured_figure: str | None = None,
) -> str:
    """Accept a proposed entry and WRITE it to the corpus.

    This is the only route from an answer onto the CV, and it has to actually be
    one: it used to set a flag and return, so the guarded path — verbatim
    capture, then confirmation — reached nothing, and the only tool that wrote
    was `cv_corpus_add`, which takes the agent's own text. The guarantee was
    inverted in practice.

    `claim` is the user's wording, theirs to shorten at this point: a proposal is
    their raw answer, which is usually longer than a bullet. Do not improve it.

    `mechanism` is the user's answer to HOW they brought it about. Ask them; a
    claim with no mechanism is an assertion.

    A figure is written ONLY from `measured_figure`, and only when `verified` is
    true. The `figure` a proposal carries is a hint and nothing more: it is the
    first number found anywhere in the answer, so it is routinely bound to a
    sentence that never contained it, and it has matched list numbering ("1.")
    as readily as a real metric. Ask the user what the number is and whether they
    counted it; pass their answer. Never pass the proposal's hint unchecked.
    """
    if _session.interview is None:
        return _err("no interview")
    try:
        proposal = _session.interview.confirm(proposal_id, verified=verified, claim=claim)
    except InterviewError as exc:
        return _err(str(exc))

    if not role_id:
        return _err(
            "a bullet belongs to a role — say which one",
            hint=(
                "Pass role_id. The roles in this corpus are: "
                + ", ".join(r.id for r in _session.corpus.roles)
                if _session.corpus
                else "Pass role_id."
            ),
        )
    if not mechanism:
        return _err(
            "a claim with no mechanism is an assertion",
            hint=(
                "Ask the user HOW they brought it about, and pass their answer. That is "
                "the half a profile never states, and the half that makes a bullet evidence."
            ),
        )

    figure = measured_figure.strip() if (verified and measured_figure) else None
    if figure:
        # The figure has to have come from the user. `measured_figure` was added
        # so a number could never again be lifted from a different sentence by
        # the proposal's own extractor; it closed that and left the wider hole
        # open, because whatever the agent passed was written as measured with
        # nothing tying it to the user at all. An outside tester answered with a
        # sentence containing no number and got `value: "500 sites"` onto the CV.
        #
        # A docstring asking the agent to pass the user's answer is not a
        # guarantee. The Proposal keeps `user_said` verbatim precisely so a
        # claim can be traced, so it is the thing to check against.
        problem = _figure_problem(figure)
        if problem:
            return _err(problem)
        said = proposal.user_said.lower()
        digits = re.findall(r"\d[\d,.]*", figure)
        grounded = (
            any(d.rstrip(".,") in said for d in digits) if digits else figure.lower() in said
        )
        if not grounded:
            return _err(
                f"{figure!r} does not appear in what the user said, so it cannot be "
                "recorded as something they measured",
                hint=(
                    "They said: "
                    f"{proposal.user_said[:160]!r}. Ask them for the figure and pass "
                    "their answer, or leave the bullet without one."
                ),
            )

    path = str(_session.corpus_path) if _session.corpus_path else None
    bullet = NewBullet(
        id=_suggest_bullet_id(role_id, proposal.claim),
        claim=proposal.claim,
        mechanism=mechanism,
        tags=proposal.tags,
        metric_value=figure,
    )
    try:
        apply(path, lambda text: add_bullet(text, role_id, bullet))
    except EditError as exc:
        return _err(str(exc))
    _session.load(path)
    _session.kit_stale = _session.kit_dir is not None
    return _ok(
        {
            "confirmed": proposal.id,
            "written_to": role_id,
            "bullet": bullet.id,
            "claim": proposal.claim,
            "verified": bool(figure),
            "figure": figure,
            "note": (
                "Anything already written to disk is now out of date. Re-render before "
                "the user sends it anywhere."
            ),
        }
    )


# ── the account of itself ───────────────────────────────────────────────────
@mcp.tool()
def cv_explain() -> str:
    """Why this CV looks the way it does: what was chosen, cut, and still missing.

    Walk the user through this at the end. It is also the honest record — every
    rendered bullet traces to a corpus entry, and every confirmed gap is named
    rather than quietly dropped.
    """
    if _session.card is None:
        return _err("nothing to explain yet")
    gaps = [r.requirement.text for r in _session.card.rows if r.verdict is Verdict.GAP]
    confirmed = _session.interview.confirmed_gaps() if _session.interview else []
    template = get_template(_session.layout)
    return _ok(
        {
            "layout": {
                "id": template.id,
                "why": template.blurb,
                "portal_safe": template.ats_safe,
            },
            "kit": str(_session.kit_dir) if _session.kit_dir else None,
            "kept": [
                {"requirement": r.requirement.text, "evidence": r.evidence_ids}
                for r in _session.card.rows
                if r.verdict is Verdict.STRONG
            ],
            "gaps_from_scoring": gaps,
            "gaps_confirmed_by_the_user": confirmed,
            "hard_filters": [r.requirement.text for r in _session.card.hard_filters],
            "reminder": (
                "Confirmed gaps are deliberately absent from the CV. Do not soften them "
                "into 'exposure to' — they are the most useful thing on the scorecard, "
                "and they are what to prepare for."
            ),
        }
    )


def main() -> None:
    """Entry point for `uvx cv-consultant-pro-mcp` and for both plugin manifests."""
    mcp.run()


if __name__ == "__main__":  # pragma: no cover
    main()
