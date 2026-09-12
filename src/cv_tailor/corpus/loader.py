"""Read a corpus file, validate it, or refuse it.

Loading and validating are one operation on purpose. A corpus that violates the
metric rule is not a corpus with a warning attached — it is not loadable, because
every downstream stage assumes the rule already holds.

Errors accumulate. A first run against a hand-written corpus typically surfaces
several problems at once, and reporting them one per run turns a ten-minute fix
into ten runs.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

from .dates import ParsedDate, YearMonth, parse_date
from .models import (
    Artifact,
    Bullet,
    Certification,
    Corpus,
    Education,
    Metric,
    Person,
    Position,
    Role,
    Skill,
    Summary,
)

ENV_VAR = "CV_TAILOR_CORPUS"
DEFAULT_FILENAME = "career-corpus.yaml"

# A bracketed hole such as [X] or [N engineers]. The brackets are the point: they
# survive into the rendered CV as a visible gap, which is what makes an unverified
# figure impossible to mistake for a real one.
_BRACKET_GROUP = re.compile(r"\[[^\]]*\]")
_DIGIT = re.compile(r"\d")


class CorpusError(Exception):
    """One or more corpus rules were violated."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        joined = "\n  - ".join(problems)
        super().__init__(f"corpus is not valid:\n  - {joined}")


class _Collector:
    def __init__(self) -> None:
        self.problems: list[str] = []

    def add(self, ref: str, message: str) -> None:
        self.problems.append(f"{ref}: {message}")

    def raise_if_any(self) -> None:
        if self.problems:
            raise CorpusError(self.problems)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _date(raw: Any, *, ref: str, field: str, errors: _Collector) -> ParsedDate:
    try:
        return parse_date(raw, field=field)
    except ValueError as exc:
        errors.add(ref, str(exc))
        return ParsedDate(value=None, is_todo=True)


def _metric(raw: Any, *, bullet_id: str, text: str, errors: _Collector) -> Metric | None:
    """Parse and police one metric. This is the anti-fabrication guard."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        errors.add(bullet_id, "metric must be a mapping with a 'verified' key")
        return None
    if "verified" not in raw:
        errors.add(bullet_id, "metric must declare 'verified' as true or false")
        return None

    verified = raw.get("verified")
    if not isinstance(verified, bool):
        errors.add(bullet_id, f"metric 'verified' must be true or false, got {verified!r}")
        return None

    value = raw.get("value")
    placeholder = raw.get("placeholder")

    if verified:
        if value is None or not str(value).strip():
            errors.add(bullet_id, "a verified metric must carry a concrete 'value'")
        if placeholder:
            errors.add(
                bullet_id,
                "a verified metric must not also carry a 'placeholder' — "
                "one figure, one state",
            )
    else:
        if value is not None and str(value).strip():
            errors.add(
                bullet_id,
                f"metric is marked verified: false but carries a value of {value!r}. "
                "An unmeasured figure must be a placeholder, never a number",
            )
        if placeholder is None or not str(placeholder).strip():
            errors.add(bullet_id, "an unverified metric must carry a 'placeholder'")
        else:
            _check_placeholder(str(placeholder), bullet_id=bullet_id, text=text, errors=errors)

    return Metric(
        verified=verified,
        value=str(value) if value is not None else None,
        placeholder=str(placeholder) if placeholder is not None else None,
    )


def _check_placeholder(placeholder: str, *, bullet_id: str, text: str, errors: _Collector) -> None:
    groups = _BRACKET_GROUP.findall(placeholder)

    if not groups:
        errors.add(
            bullet_id,
            f"placeholder {placeholder!r} contains no bracketed hole. A placeholder must "
            "look like '[X]%' or '[N] engineers' — a bare figure here is a fabricated "
            "number wearing a placeholder's label",
        )
        return

    # A digit outside the brackets is a real number smuggled alongside the hole.
    outside = _BRACKET_GROUP.sub("", placeholder)
    if _DIGIT.search(outside):
        errors.add(
            bullet_id,
            f"placeholder {placeholder!r} contains a digit outside its brackets, so part "
            "of it reads as a real measurement",
        )

    # ...and [5] is a number that merely looks like a hole.
    for group in groups:
        inner = group[1:-1].strip()
        if inner and _DIGIT.fullmatch(inner.replace(".", "").replace(",", "") or "x"):
            errors.add(
                bullet_id,
                f"placeholder {placeholder!r} brackets a number. Brackets mark a value "
                "you do not have, not one you do",
            )

    if placeholder not in text:
        errors.add(
            bullet_id,
            f"placeholder {placeholder!r} does not appear in the claim or mechanism, so it "
            "would never render. Either use it in the text or drop the metric",
        )


def _bullet(raw: Any, *, role_id: str, language: str, errors: _Collector) -> Bullet | None:
    if not isinstance(raw, dict):
        errors.add(role_id, "each bullet must be a mapping")
        return None

    bullet_id = str(raw.get("id") or "").strip()
    if not bullet_id:
        errors.add(role_id, "a bullet is missing its 'id'; ids are how claims stay traceable")
        return None

    claim = str(raw.get("claim") or "").strip()
    mechanism = str(raw.get("mechanism") or "").strip()
    if not claim:
        errors.add(bullet_id, "bullet must carry a 'claim'")

    tags = [str(t) for t in _as_list(raw.get("tags"))]
    if not tags:
        errors.add(
            bullet_id,
            "bullet has no tags. Matching finds evidence by tag, so an untagged bullet can "
            "never be selected for any posting",
        )

    metric = _metric(
        raw.get("metric"),
        bullet_id=bullet_id,
        text=f"{claim}\n{mechanism}",
        errors=errors,
    )

    return Bullet(
        id=bullet_id,
        claim=claim,
        mechanism=mechanism,
        tags=tags,
        metric=metric,
        language=str(raw.get("language") or language),
    )


def _role(raw: Any, *, language: str, errors: _Collector) -> Role | None:
    if not isinstance(raw, dict):
        errors.add("roles", "each role must be a mapping")
        return None

    role_id = str(raw.get("id") or "").strip()
    if not role_id:
        errors.add("roles", "a role is missing its 'id'")
        return None

    start = _date(raw.get("start"), ref=role_id, field="start", errors=errors)
    end = _date(raw.get("end"), ref=role_id, field="end", errors=errors)

    if start.value and end.value and end.value < start.value:
        errors.add(
            role_id,
            f"end {end.value.render()} is before start {start.value.render()}",
        )

    bullets: list[Bullet] = []
    for raw_bullet in _as_list(raw.get("bullets")):
        parsed = _bullet(raw_bullet, role_id=role_id, language=language, errors=errors)
        if parsed is not None:
            bullets.append(parsed)

    return Role(
        id=role_id,
        org=str(raw.get("org") or "").strip(),
        title=str(raw.get("title") or "").strip(),
        start=start.value,
        end=end.value,
        is_current=end.is_present,
        needs_dates=start.is_todo or end.is_todo,
        location=raw.get("location"),
        title_framings=[str(t) for t in _as_list(raw.get("title_framings"))],
        tags=[str(t) for t in _as_list(raw.get("tags"))],
        bullets=bullets,
    )


def _position(raw: Any, *, language: str, errors: _Collector) -> Position | None:
    if not isinstance(raw, dict):
        errors.add("positions", "each position must be a mapping")
        return None
    position_id = str(raw.get("id") or "").strip()
    if not position_id:
        errors.add("positions", "a position is missing its 'id'")
        return None
    return Position(
        id=position_id,
        topic=str(raw.get("topic") or "").strip(),
        question=str(raw.get("question") or "").strip(),
        answer=str(raw.get("answer") or "").strip(),
        source=raw.get("source"),
        language=str(raw.get("language") or language),
    )


def _person(raw: Any, errors: _Collector) -> Person:
    if not isinstance(raw, dict):
        errors.add("person", "the corpus must declare a 'person' mapping with a 'name'")
        return Person(name="")
    name = str(raw.get("name") or "").strip()
    if not name:
        errors.add("person", "'person.name' is required")
    return Person(
        name=name,
        email=raw.get("email"),
        phone=raw.get("phone"),
        location=raw.get("location"),
        links={str(k): str(v) for k, v in (raw.get("links") or {}).items()},
        languages=[str(x) for x in _as_list(raw.get("languages"))],
    )


def load_corpus_text(text: str) -> Corpus:
    """Parse and validate a corpus from YAML text. Raises CorpusError if invalid."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise CorpusError([f"file is not valid YAML: {exc}"]) from exc

    if not isinstance(data, dict):
        raise CorpusError(["the corpus must be a YAML mapping at the top level"])

    errors = _Collector()
    language = str(data.get("language") or "en")
    person = _person(data.get("person"), errors)

    roles: list[Role] = []
    for raw_role in _as_list(data.get("roles")):
        parsed = _role(raw_role, language=language, errors=errors)
        if parsed is not None:
            roles.append(parsed)

    seen: set[str] = set()
    for role in roles:
        for bullet in role.bullets:
            if bullet.id in seen:
                errors.add(
                    bullet.id,
                    "duplicate bullet id. Selection and the audit trail address bullets by "
                    "id, so a duplicate makes a rendered claim untraceable",
                )
            seen.add(bullet.id)

    skills: list[Skill] = []
    for raw_skill in _as_list(data.get("skills")):
        if not isinstance(raw_skill, dict):
            errors.add("skills", "each skill must be a mapping")
            continue
        skill = Skill(
            name=str(raw_skill.get("name") or "").strip(),
            aliases=[str(a) for a in _as_list(raw_skill.get("aliases"))],
            tags=[str(t) for t in _as_list(raw_skill.get("tags"))],
            evidence_refs=[str(r) for r in _as_list(raw_skill.get("evidence_refs"))],
        )
        if not skill.name:
            errors.add("skills", "a skill is missing its 'name'")
        for ref in skill.evidence_refs:
            if ref not in seen:
                errors.add(
                    skill.name or "skills",
                    f"evidence_ref {ref!r} names no bullet in the corpus",
                )
        skills.append(skill)

    summaries: list[Summary] = []
    for raw_summary in _as_list(data.get("summaries")):
        if not isinstance(raw_summary, dict):
            errors.add("summaries", "each summary must be a mapping")
            continue
        summary_id = str(raw_summary.get("id") or "").strip()
        text = str(raw_summary.get("text") or "").strip()
        if not summary_id:
            errors.add("summaries", "a summary is missing its 'id'")
            continue
        if not text:
            errors.add(summary_id, "summary must carry 'text'")
        summaries.append(
            Summary(
                id=summary_id,
                text=text,
                tags=[str(t) for t in _as_list(raw_summary.get("tags"))],
                language=str(raw_summary.get("language") or language),
            )
        )

    positions: list[Position] = []
    for raw_position in _as_list(data.get("positions")):
        parsed_position = _position(raw_position, language=language, errors=errors)
        if parsed_position is not None:
            positions.append(parsed_position)

    education = [
        Education(
            institution=str(e.get("institution") or ""),
            qualification=str(e.get("qualification") or ""),
            start=_date(e.get("start"), ref="education", field="start", errors=errors).value,
            end=_date(e.get("end"), ref="education", field="end", errors=errors).value,
            specialisation=e.get("specialisation"),
        )
        for e in _as_list(data.get("education"))
        if isinstance(e, dict)
    ]

    certifications = [
        Certification(
            name=str(c.get("name") or ""),
            held=bool(c.get("held", True)),
            issuer=c.get("issuer"),
        )
        for c in _as_list(data.get("certifications"))
        if isinstance(c, dict)
    ]

    artifacts = [
        Artifact(
            name=str(a.get("name") or ""),
            kind=str(a.get("kind") or ""),
            url=a.get("url"),
            blurb=a.get("blurb"),
        )
        for a in _as_list(data.get("artifacts"))
        if isinstance(a, dict)
    ]

    errors.raise_if_any()

    return Corpus(
        person=person,
        language=language,
        roles=roles,
        skills=skills,
        summaries=summaries,
        positions=positions,
        education=education,
        certifications=certifications,
        artifacts=artifacts,
    )


def resolve_corpus_path(explicit: str | os.PathLike[str] | None = None) -> Path:
    """Explicit argument, then CV_TAILOR_CORPUS, then ./career-corpus.yaml.

    An empty or whitespace-only environment value counts as unset, because a
    container or CI runner that injects "" for an absent variable should not
    thereby point the engine at a file named "".
    """
    if explicit:
        return Path(explicit)
    from_env = os.environ.get(ENV_VAR, "").strip()
    if from_env:
        return Path(from_env)
    return Path.cwd() / DEFAULT_FILENAME


def load_corpus(path: str | os.PathLike[str] | None = None) -> Corpus:
    resolved = resolve_corpus_path(path)
    if not resolved.is_file():
        raise CorpusError(
            [
                f"no corpus at {resolved}. Copy career-corpus.example.yaml to "
                f"{DEFAULT_FILENAME} and fill it in, or set {ENV_VAR}"
            ]
        )
    return load_corpus_text(resolved.read_text(encoding="utf-8"))


__all__ = [
    "ENV_VAR",
    "CorpusError",
    "YearMonth",
    "load_corpus",
    "load_corpus_text",
    "resolve_corpus_path",
]
