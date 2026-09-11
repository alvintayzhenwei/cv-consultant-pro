"""Select, render, and refuse to write anything untraceable.

Three rules govern everything here:

  1. Selection drops whole entries, never truncates one. A bullet cut in half is
     worse than a bullet absent.
  2. Nothing is written that does not trace to a corpus entry id.
  3. An unverified figure renders as its placeholder, never as a guess.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .corpus import Bullet, Corpus, Role
from .jd import JobDescription
from .match import Scorecard

# A one-page CV runs to roughly this many body lines once a header, a skills
# block and an education footer are accounted for. Approximate by construction:
# real length depends on font metrics, so the number is reported rather than
# trusted.
LINE_BUDGET = 46


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
    traceability: list[tuple[str, str]]
    placeholders: list[tuple[str, str]]
    selection: Selection


class AuditError(Exception):
    """Rendering produced something that does not trace to the corpus."""


def select(corpus: Corpus, card: Scorecard, *, budget: int = LINE_BUDGET) -> Selection:
    relevance = card.relevance()

    scored_roles: list[tuple[Role, list[Bullet], int]] = []
    for role in corpus.roles:
        ranked = sorted(role.bullets, key=lambda b: relevance.get(b.id, 0), reverse=True)
        kept = [b for b in ranked if relevance.get(b.id, 0) > 0]
        weight = sum(relevance.get(b.id, 0) for b in role.bullets)
        scored_roles.append((role, kept, weight))

    # Recency breaks ties: two equally relevant roles, the newer one wins.
    scored_roles.sort(
        key=lambda item: (item[2], item[0].start.year if item[0].start else 0), reverse=True
    )

    selection = Selection()
    lines = 0
    for role, kept, weight in scored_roles:
        if weight == 0 or not kept:
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

    matched = [name for row in card.rows + card.hard_filters for name in row.skill_names]
    seen: set[str] = set()
    ordered: list[str] = []
    for name in matched:
        if name not in seen:
            seen.add(name)
            ordered.append(name)
    for skill in corpus.skills:
        if skill.name not in seen:
            ordered.append(skill.name)
    selection.skills = ordered
    return selection


def _bullet_line(bullet: Bullet) -> str:
    text = bullet.claim.rstrip(". ")
    if bullet.mechanism:
        text = f"{text}, {bullet.mechanism.rstrip('. ')}"
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
    return f"- {text}."


def render(corpus: Corpus, jd: JobDescription, card: Scorecard, selection: Selection) -> Kit:
    p = corpus.person
    out: list[str] = []
    trace: list[tuple[str, str]] = []
    placeholders: list[tuple[str, str]] = []

    out.append(p.name.upper())
    contact = " | ".join(x for x in [p.location, p.email, p.phone] if x)
    if contact:
        out.append(contact)
    if p.links:
        out.append(" | ".join(p.links.values()))
    if p.languages:
        out.append("Languages: " + ", ".join(p.languages))
    out.append("")

    if jd.title:
        out.append(jd.title.upper())
        out.append("")

    out.append("CORE SKILLS")
    out.append(", ".join(selection.skills[:24]))
    out.append("")

    out.append("EXPERIENCE")
    out.append("")
    for role, bullets in selection.roles:
        head = f"{role.title.upper()} - {role.org}"
        if role.location:
            head += f", {role.location}"
        out.append(f"{head} | {role.rendered_dates()}")
        for bullet in bullets:
            out.append(_bullet_line(bullet))
            trace.append((bullet.id, bullet.claim))
            if bullet.metric is not None and not bullet.metric.verified:
                placeholders.append((bullet.id, bullet.metric.placeholder or ""))
        out.append("")

    if corpus.education:
        out.append("EDUCATION")
        for edu in corpus.education:
            end = edu.end.render() if edu.end else "TODO"
            spec = f", {edu.specialisation}" if edu.specialisation else ""
            out.append(f"{edu.qualification}{spec} - {edu.institution} | {end}")
        out.append("")

    held = [c.name for c in corpus.certifications if c.held]
    if held:
        out.append("CERTIFICATIONS")
        out.append(" | ".join(held))
        out.append("")

    markdown = "\n".join(out).rstrip() + "\n"

    _audit(markdown, corpus, selection)

    return Kit(
        markdown=markdown,
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

    for role, bullets in selection.roles:
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
