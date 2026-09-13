"""The session state machine — the script the host agent reads out.

An MCP server cannot hold a conversation; tools get called, they do not ask
questions. Hand an agent a bag of tools and it will run a different interview
every time, and a worse one on a weaker host.

So the server owns the script. Every tool returns the next beat: which stage the
session is in, what is missing, and the exact sentence to put to the user. The
agent is the mouth. Behaviour is then the same everywhere, because the wording
does not depend on the model.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path

from .corpus import Corpus, CorpusError, load_corpus, resolve_corpus_path
from .interview import Interview
from .jd import JobDescription
from .match import Scorecard, Verdict


class Stage(StrEnum):
    NO_CORPUS = "no_corpus"
    CORPUS_INCOMPLETE = "corpus_incomplete"
    NEEDS_LAYOUT = "needs_layout"
    NEEDS_JD = "needs_jd"
    SCORED = "scored"
    RENDERED = "rendered"
    INTERVIEWING = "interviewing"
    EVIDENCE_PENDING = "evidence_pending"
    STALE = "stale"
    DONE = "done"


@dataclass
class NextStep:
    """What the agent should do and say next."""

    stage: Stage
    #: The sentence to put to the user. Read it out; do not improvise around it.
    say: str
    #: The tool to call once the user has replied.
    then_call: str | None = None
    #: Anything the agent needs in order to ask well.
    detail: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        out = asdict(self)
        out["stage"] = str(self.stage)
        return out


@dataclass
class Session:
    corpus_path: Path | None = None
    corpus: Corpus | None = None
    corpus_error: list[str] = field(default_factory=list)
    layout: str | None = None
    jd: JobDescription | None = None
    card: Scorecard | None = None
    kit_dir: Path | None = None
    interview: Interview | None = None
    #: Set when the corpus changes after a kit was written. A generated kit is a
    #: snapshot, and five of six went silently stale once already.
    kit_stale: bool = False

    def load(self, path: str | None = None) -> None:
        """Load the corpus, remembering WHERE it came from.

        The path is kept because every later edit writes back to this same file:
        forgetting it meant an edit resolved the default location instead, so a
        session started against a corpus elsewhere quietly wrote somewhere else.
        """
        self.corpus_path = Path(resolve_corpus_path(path))
        try:
            self.corpus = load_corpus(path)
            self.corpus_error = []
        except CorpusError as exc:
            self.corpus = None
            self.corpus_error = exc.problems

    def next_step(self) -> NextStep:
        if self.corpus is None and not self.corpus_error:
            return NextStep(
                stage=Stage.NO_CORPUS,
                say=(
                    "Before I can build anything I need your career evidence — not a CV, "
                    "the raw material. Do you have a LinkedIn profile PDF? It seeds your "
                    "roles and dates so you are not typing years from memory."
                ),
                then_call="cv_seed",
            )

        if self.corpus_error:
            return NextStep(
                stage=Stage.CORPUS_INCOMPLETE,
                say=(
                    "The corpus will not load yet. Here is what is wrong — I can walk "
                    "through these one at a time."
                ),
                then_call="cv_validate",
                detail={"problems": self.corpus_error},
            )

        assert self.corpus is not None
        # Only DATES block. An unverified figure renders as its own placeholder
        # and is offered back at the end, because refusing to build a CV over one
        # unmeasured number would be a rule nobody could satisfy.
        blocking = self.corpus.blocking_todos()
        if blocking:
            first = blocking[0]
            return NextStep(
                stage=Stage.CORPUS_INCOMPLETE,
                say=(
                    f"One gap before we go further — {first.ref}: {first.what}. "
                    "Ask the user for this one thing; do not present the whole list at once."
                ),
                then_call="cv_corpus_add",
                detail={
                    "outstanding": [{"ref": t.ref, "what": t.what} for t in blocking],
                    "ask_about": first.ref,
                },
            )

        if self.layout is None:
            return NextStep(
                stage=Stage.NEEDS_LAYOUT,
                say=(
                    "Which layout do you want? Call cv_preview to open all five side by "
                    "side in the browser, and tell the user which are safe to submit "
                    "through a portal."
                ),
                then_call="cv_preview",
            )

        if self.jd is None:
            return NextStep(
                stage=Stage.NEEDS_JD,
                say="Paste the job description, or give me its URL.",
                then_call="cv_ingest_jd",
            )

        if self.card is None:
            return NextStep(stage=Stage.NEEDS_JD, say="Scoring.", then_call="cv_score")

        if self.interview is not None:
            if self.interview.pending():
                return NextStep(
                    stage=Stage.EVIDENCE_PENDING,
                    say=(
                        "The user said something the corpus does not hold. Show them the "
                        "exact wording you would add, in their words, and ask whether the "
                        "figure is measured or an estimate."
                    ),
                    then_call="cv_confirm_evidence",
                    detail={
                        "pending": [
                            {"id": p.id, "claim": p.claim, "from_answer": p.user_said}
                            for p in self.interview.pending()
                        ]
                    },
                )
            answered, total = self.interview.progress()
            if answered < total:
                return NextStep(
                    stage=Stage.INTERVIEWING,
                    say=f"Question {answered + 1} of {total}.",
                    then_call="cv_next_question",
                )
            if self.kit_stale:
                return NextStep(
                    stage=Stage.STALE,
                    say=(
                        "The interview added evidence, so the CV on disk is out of date. "
                        "Re-render before the user sends anything."
                    ),
                    then_call="cv_render",
                )
            return NextStep(
                stage=Stage.DONE,
                say=(
                    "Done. Walk the user through why the CV looks the way it does, and "
                    "what is still a gap."
                ),
                then_call="cv_explain",
            )

        if self.kit_dir is None:
            gaps = len([r for r in self.card.rows if r.verdict is Verdict.GAP])
            return NextStep(
                stage=Stage.SCORED,
                say=(
                    "Give the user the honest read first — strong, partial and gap counts, "
                    "and any hard filter they must answer themselves. Then ask whether "
                    "they want the CV now or want to close a gap first."
                ),
                then_call="cv_render",
                detail={"gaps": gaps, "hard_filters": len(self.card.hard_filters)},
            )

        return NextStep(
            stage=Stage.RENDERED,
            say=(
                "The kit is written. Offer the interview — it is ten questions, and it is "
                "how unrecorded experience gets onto the CV."
            ),
            then_call="cv_interview",
            detail={"kit": str(self.kit_dir)},
        )


__all__ = ["NextStep", "Session", "Stage"]
