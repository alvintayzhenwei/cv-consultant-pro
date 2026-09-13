"""The corpus data model.

Three entry kinds, deliberately not collapsed into one:

  bullet    a dated, attributable accomplishment. Evidence.
  position  a worked answer to a question. A stated view, not a delivered thing.
  skill     a capability, pointing at the bullets that substantiate it.

Keeping `position` separate from `bullet` is what stops an opinion about how to
control inference cost from scoring as evidence of having controlled it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .dates import YearMonth

DEFAULT_LANGUAGE = "en"


@dataclass(frozen=True)
class Todo:
    """Something the corpus knows it is missing."""

    ref: str
    what: str
    #: Whether this must be answered before a CV can be rendered at all.
    #:
    #: An unknown employment DATE blocks: every CV format prints one, there is
    #: no honest way to omit it, and the marker leaked onto a rendered CV as the
    #: literal word "TODO" once already. An unverified FIGURE does not block -
    #: the anti-fabrication contract already has an answer for it, which is to
    #: render the placeholder visibly. Gating on those would mean one unmeasured
    #: number anywhere in a career stopped the whole pipeline, which is a worse
    #: outcome than a CV that says "[N]" in one bullet and invites a real answer.
    blocking: bool = False


@dataclass
class Metric:
    """A figure attached to a claim — or an admission that there isn't one.

    Exactly one of these two states is legal, and the validator enforces it:

      verified=True   `value` holds a real, measured figure.
      verified=False  `placeholder` holds a visible hole such as "[X]%".

    There is no third state, because the third state is where invention lives.
    """

    verified: bool
    value: str | None = None
    placeholder: str | None = None

    def render(self) -> str:
        return (self.value if self.verified else self.placeholder) or ""


@dataclass
class Bullet:
    id: str
    claim: str
    mechanism: str
    tags: list[str] = field(default_factory=list)
    metric: Metric | None = None
    language: str = DEFAULT_LANGUAGE

    @property
    def has_placeholder(self) -> bool:
        return self.metric is not None and not self.metric.verified


@dataclass
class Role:
    id: str
    org: str
    title: str
    start: YearMonth | None = None
    end: YearMonth | None = None
    is_current: bool = False
    needs_dates: bool = False
    location: str | None = None
    title_framings: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    bullets: list[Bullet] = field(default_factory=list)

    def rendered_dates(self) -> str:
        """The date range as a CV shows it, or an empty string when unknown.

        `TODO` is a corpus-internal marker and must never reach a rendered CV —
        it leaked once, printing "TODO - Present" on a page meant for an
        employer. An undated entry is a real problem (some parsers penalise
        one), so `needs_dates` and `todos()` keep saying so; what must not happen
        is the marker being mistaken for output.
        """
        if self.start is None:
            return ""
        start = self.start.render()
        if self.is_current:
            return f"{start} - Present"
        if self.end is None:
            return start
        return f"{start} - {self.end.render()}"

    def months(self, *, now: YearMonth | None = None) -> int | None:
        """Duration in months, or None when the dates are not known.

        Used to answer a posting's "minimum N years" line with a computed figure
        rather than an assertion.
        """
        if self.start is None:
            return None
        end = self.end
        if self.is_current:
            end = now
        if end is None:
            return None
        return (end.year - self.start.year) * 12 + (end.month - self.start.month)


@dataclass
class Summary:
    """One authored positioning paragraph, tagged for the postings it suits.

    The corpus carries several because the engine may not write one. Select-only
    means a summary is chosen, never composed — so the variety has to exist in
    the corpus or the CV opens with nothing.
    """

    id: str
    text: str
    tags: list[str] = field(default_factory=list)
    language: str = DEFAULT_LANGUAGE


@dataclass
class Position:
    """A worked answer to a question the holder has a real view on."""

    id: str
    topic: str
    question: str
    answer: str
    source: str | None = None
    language: str = DEFAULT_LANGUAGE


@dataclass
class Skill:
    name: str
    aliases: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)

    def matches(self, text: str) -> bool:
        """True when `text` names this skill under its own name or a declared alias.

        This is the vocabulary bridge: it is what permits a rendered CV to adopt
        a posting's exact wording without adopting a claim. A phrasing that is
        not declared here is not adopted.
        """
        needle = text.strip().casefold()
        return needle == self.name.casefold() or any(
            needle == alias.casefold() for alias in self.aliases
        )


@dataclass
class Education:
    institution: str
    qualification: str
    start: YearMonth | None = None
    end: YearMonth | None = None
    specialisation: str | None = None


@dataclass
class Certification:
    name: str
    held: bool = True
    issuer: str | None = None


@dataclass
class Artifact:
    """Something published: a package, an article, a talk."""

    name: str
    kind: str
    url: str | None = None
    blurb: str | None = None


@dataclass
class Person:
    name: str
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    links: dict[str, str] = field(default_factory=dict)
    languages: list[str] = field(default_factory=list)


@dataclass
class Corpus:
    person: Person
    language: str = DEFAULT_LANGUAGE
    roles: list[Role] = field(default_factory=list)
    skills: list[Skill] = field(default_factory=list)
    summaries: list[Summary] = field(default_factory=list)
    positions: list[Position] = field(default_factory=list)
    education: list[Education] = field(default_factory=list)
    certifications: list[Certification] = field(default_factory=list)
    artifacts: list[Artifact] = field(default_factory=list)

    def all_bullets(self) -> list[Bullet]:
        return [bullet for role in self.roles for bullet in role.bullets]

    def bullet(self, bullet_id: str) -> Bullet | None:
        for bullet in self.all_bullets():
            if bullet.id == bullet_id:
                return bullet
        return None

    def blocking_todos(self) -> list[Todo]:
        """Only what must be answered before anything can be rendered."""
        return [todo for todo in self.todos() if todo.blocking]

    def todos(self) -> list[Todo]:
        """Everything the corpus knows is missing, for the user to fill in.

        Reported rather than hidden: a corpus that quietly renders an incomplete
        history produces a CV that looks finished and is not.
        """
        found: list[Todo] = []
        for role in self.roles:
            if role.needs_dates:
                found.append(
                    Todo(ref=role.id, what="employment dates are unknown", blocking=True)
                )
        for bullet in self.all_bullets():
            if bullet.has_placeholder and bullet.metric is not None:
                found.append(
                    Todo(
                        ref=bullet.id,
                        what=f"unverified figure {bullet.metric.placeholder!r} needs a real value",
                    )
                )
        return found
