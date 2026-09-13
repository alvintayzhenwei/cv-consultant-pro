"""Select, render, and refuse to write anything untraceable.

Three rules govern everything here:

  1. Selection drops whole entries, never truncates one. A bullet cut in half is
     worse than a bullet absent.
  2. Nothing is written that does not trace to a corpus entry id.
  3. An unverified figure renders as its placeholder, never as a guess.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .corpus import Bullet, Corpus, Role
from .document import CvDocument, RenderedRole
from .jd import JobDescription
from .match import Scorecard

# A one-page CV runs to roughly this many body lines once a header, a skills
# block and an education footer are accounted for. Approximate by construction:
# real length depends on font metrics, so the number is reported rather than
# trusted.
LINE_BUDGET = 46

# Sixteen is about what a reader scans before the block becomes wallpaper.
MAX_SKILLS = 16

# Of those, at most this many may be skills the posting never asked for.
MAX_SKILL_TAIL = 5

# Roles shorter than a year are dropped unless they are the only evidence for
# something the posting asked for. Twelve months is the point at which a role
# stops reading as a stint and starts reading as a chapter.
MIN_ROLE_MONTHS = 12


def _sole_evidence_bullets(card: Scorecard) -> set[str]:
    """Bullets that are the ONLY thing answering some requirement.

    These keep their role alive however short it was. The duration rule is a
    tie-breaker for space, not a judgement about what counts as experience —
    losing the single piece of evidence for a requirement to save one line is a
    bad trade every time.
    """
    sole: set[str] = set()
    for row in card.rows + card.hard_filters:
        if len(row.evidence_ids) == 1:
            sole.add(row.evidence_ids[0])
    return sole


@dataclass
class Selection:
    roles: list[tuple[Role, list[Bullet]]] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    estimated_lines: int = 0
    dropped_roles: list[str] = field(default_factory=list)

    def bullet_ids(self) -> list[str]:
        return [b.id for _, bullets in self.roles for b in bullets]


@dataclass
class Kit:
    markdown: str
    #: The same CV as structure. Every other format renders from this, never
    #: from the markdown — see document.py.
    document: CvDocument
    traceability: list[tuple[str, str]]
    placeholders: list[tuple[str, str]]
    selection: Selection


class AuditError(Exception):
    """Rendering produced something that does not trace to the corpus."""


def _bullet_rank(bullet: Bullet, relevance: dict[str, int]) -> tuple[int, int]:
    """Relevance first, then whether the claim is measured.

    Two bullets can match a posting equally and be worth very different amounts.
    "Built automation that made processes at least 50% faster" and "learned the
    languages to build that tooling" carried the same tags, and the CV rendered
    the second — an activity where an outcome was available. A verified figure
    is the one signal that separates them, and it is exactly what a recruiter
    scans for.

    An unverified metric scores between the two: the bullet is shaped like an
    accomplishment and is honest that the number is missing, which is better
    than no outcome at all but worse than a real one.
    """
    weight = relevance.get(bullet.id, 0)
    if bullet.metric is None:
        measured = 0
    elif bullet.metric.verified:
        measured = 2
    else:
        measured = 1
    return (weight, measured)


def select(corpus: Corpus, card: Scorecard, *, budget: int = LINE_BUDGET) -> Selection:
    relevance = card.relevance()

    scored_roles: list[tuple[Role, list[Bullet], int]] = []
    for role in corpus.roles:
        ranked = sorted(role.bullets, key=lambda b: _bullet_rank(b, relevance), reverse=True)
        kept = [b for b in ranked if relevance.get(b.id, 0) > 0]
        weight = sum(relevance.get(b.id, 0) for b in role.bullets)
        scored_roles.append((role, kept, weight))

    # Recency breaks ties: two equally relevant roles, the newer one wins.
    scored_roles.sort(
        key=lambda item: (item[2], item[0].start.year if item[0].start else 0), reverse=True
    )

    # A role shorter than this has to earn its line by being the ONLY evidence
    # for something. Six months as an intern was surviving while a two-year role
    # was dropped, because relevance counted hits and nothing else.
    sole_evidence = _sole_evidence_bullets(card)

    selection = Selection()
    lines = 0
    for role, kept, weight in scored_roles:
        if weight == 0 or not kept:
            selection.dropped_roles.append(role.id)
            continue

        months = role.months(now=None)
        if (
            months is not None
            and months < MIN_ROLE_MONTHS
            and not any(b.id in sole_evidence for b in kept)
        ):
            selection.dropped_roles.append(role.id)
            continue

        room = budget - lines - 1  # one line for the role heading
        if room <= 0:
            selection.dropped_roles.append(role.id)
            continue
        take = kept[: max(1, min(len(kept), room))]
        selection.roles.append((role, take))
        lines += 1 + len(take)

    # Restore chronological order for rendering; relevance decided inclusion,
    # not sequence. A CV that jumps about in time is unreadable.
    selection.roles.sort(
        key=lambda pair: (pair[0].start.year, pair[0].start.month) if pair[0].start else (0, 0),
        reverse=True,
    )
    selection.estimated_lines = lines

    # Rank by how many of THIS posting's requirements each skill answered, then
    # cap. The first version appended every remaining corpus skill unranked,
    # which put React second on an AI enablement role — a keyword block that
    # reads as a list of everything you have ever touched persuades nobody.
    demand: dict[str, int] = {}
    for row in card.rows + card.hard_filters:
        for name in row.skill_names:
            demand[name] = demand.get(name, 0) + 1

    # Skills the posting actually asked for come first, most-demanded first.
    asked = sorted(demand, key=lambda n: -demand[n])

    # Then a short tail of the best-evidenced remaining skills. The tail is
    # capped hard: filling sixteen slots from the corpus in declaration order is
    # what put React second on an AI enablement role. A skills block that lists
    # everything you have ever touched reads as padding and dilutes the matches
    # above it.
    rest = [s for s in corpus.skills if s.name not in demand and s.evidence_refs]
    rest.sort(key=lambda s: -len(s.evidence_refs))
    tail = [s.name for s in rest][:MAX_SKILL_TAIL]

    selection.skills = (asked + tail)[:MAX_SKILLS]
    return selection


def _pick_summary(corpus: Corpus, card: Scorecard) -> str | None:
    """Choose the closest authored summary. Never compose one.

    Select-only applies to the opening paragraph as much as to a bullet: the
    engine may pick among summaries the corpus already holds, and if it holds
    none the CV opens without one rather than with an invention.
    """
    if not corpus.summaries:
        return None
    wanted: set[str] = set()
    for row in card.rows + card.hard_filters:
        wanted |= {w.lower() for w in re.findall(r"[a-z][a-z-]{2,}", row.requirement.text.lower())}

    best = max(
        corpus.summaries,
        key=lambda s: sum(1 for t in s.tags if t.lower() in wanted),
    )
    return best.text


# A bullet longer than this stops being read. The mechanism is dropped WHOLE
# rather than truncated, for the same reason a role is: half a clause is worse
# than no clause. The claim always survives, because it is the accomplishment.
#
# 150, down from 185: at the higher limit most bullets kept their mechanism and
# ran to three printed lines, which is a paragraph wearing a bullet's hat. A
# recruiter scans; the claim is what gets scanned.
MAX_BULLET = 150


def _bullet_text(bullet: Bullet) -> str:
    text = bullet.claim.rstrip(". ")
    if bullet.mechanism:
        combined = f"{text}, {bullet.mechanism.rstrip('. ')}"
        if len(combined) <= MAX_BULLET:
            text = combined
    metric = bullet.metric
    # A verified figure is appended only when the claim does not already carry it,
    # so a bullet never says "45 minutes to seconds (45 minutes to seconds)".
    if (
        metric is not None
        and metric.verified
        and metric.value
        and metric.value.lower() not in text.lower()
    ):
        text = f"{text} ({metric.value})"
    return f"{text}."


def build_document(
    corpus: Corpus, jd: JobDescription, card: Scorecard, selection: Selection
) -> tuple[CvDocument, list[tuple[str, str]], list[tuple[str, str]]]:
    """Assemble the CV as structure, plus its traceability and placeholder lists."""
    p = corpus.person
    trace: list[tuple[str, str]] = []
    placeholders: list[tuple[str, str]] = []

    roles: list[RenderedRole] = []
    for role, bullets in selection.roles:
        lines: list[str] = []
        for bullet in bullets:
            lines.append(_bullet_text(bullet))
            trace.append((bullet.id, bullet.claim))
            if bullet.metric is not None and not bullet.metric.verified:
                placeholders.append((bullet.id, bullet.metric.placeholder or ""))
        roles.append(
            RenderedRole(
                title=role.title,
                org=role.org,
                dates=role.rendered_dates(),
                location=role.location,
                bullets=lines,
            )
        )

    education: list[str] = []
    for edu in corpus.education:
        spec = f", {edu.specialisation}" if edu.specialisation else ""
        ending = f" | {edu.end.render()}" if edu.end else ""
        education.append(f"{edu.qualification}{spec} - {edu.institution}{ending}")

    document = CvDocument(
        name=p.name,
        contact=[x for x in [p.location, p.email, p.phone] if x],
        links=list(p.links.values()),
        languages=list(p.languages),
        target_title=jd.title,
        summary=_pick_summary(corpus, card),
        skills=list(selection.skills),
        roles=roles,
        education=education,
        # In-progress certifications render, labelled. Omitting them loses real
        # signal — someone sitting an exam next month is worth knowing about —
        # and printing them unlabelled would claim something untrue.
        certifications=[
            c.name if c.held else f"{c.name} (in progress)" for c in corpus.certifications
        ],
        artifacts=[a.name for a in corpus.artifacts],
    )
    return document, trace, placeholders


def _markdown(doc: CvDocument) -> str:
    out: list[str] = [doc.name.upper()]
    if doc.contact:
        out.append(" | ".join(doc.contact))
    if doc.links:
        out.append(" | ".join(doc.links))
    if doc.languages:
        out.append("Languages: " + ", ".join(doc.languages))
    out.append("")

    if doc.target_title:
        out += [doc.target_title.upper(), ""]
    if doc.summary:
        out += ["SUMMARY", doc.summary, ""]
    if doc.skills:
        out += ["CORE SKILLS", ", ".join(doc.skills), ""]

    out += ["EXPERIENCE", ""]
    for role in doc.roles:
        head = f"{role.title.upper()} - {role.org}"
        if role.location:
            head += f", {role.location}"
        out.append(f"{head} | {role.dates}" if role.dates else head)
        out += [f"- {b}" for b in role.bullets]
        out.append("")

    if doc.education:
        out += ["EDUCATION", *doc.education, ""]
    if doc.certifications:
        out += ["CERTIFICATIONS", " | ".join(doc.certifications), ""]

    return "\n".join(out).rstrip() + "\n"


def render(corpus: Corpus, jd: JobDescription, card: Scorecard, selection: Selection) -> Kit:
    document, trace, placeholders = build_document(corpus, jd, card, selection)
    markdown = _markdown(document)

    _audit(markdown, corpus, selection)

    return Kit(
        markdown=markdown,
        document=document,
        traceability=trace,
        placeholders=placeholders,
        selection=selection,
    )


def _audit(markdown: str, corpus: Corpus, selection: Selection) -> None:
    """Every rendered bullet must trace to a corpus entry.

    Tracing is by id carried through selection, not by matching rendered text
    back to source text — re-wording is allowed, so a text comparison would
    reject legitimate output and prove nothing about provenance.
    """
    known = {b.id for b in corpus.all_bullets()}
    unknown = [bid for bid in selection.bullet_ids() if bid not in known]
    if unknown:
        raise AuditError(
            "refusing to write a CV containing claims that trace to no corpus entry: "
            + ", ".join(unknown)
        )

    for _role, bullets in selection.roles:
        for bullet in bullets:
            if bullet.metric is not None and not bullet.metric.verified:
                holder = bullet.metric.placeholder or ""
                if holder and holder not in markdown:
                    raise AuditError(
                        f"bullet {bullet.id} carries an unverified figure whose placeholder "
                        f"{holder!r} did not survive rendering. An unmeasured number must "
                        "never render as a real one"
                    )


__all__ = ["AuditError", "Kit", "Selection", "render", "select"]
