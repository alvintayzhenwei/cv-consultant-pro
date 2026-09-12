"""The rendered CV as structure, before it becomes any particular format.

Added because the first cut rendered markdown and then the .docx writer PARSED
that markdown back out — guessing from a line's shape whether it was a heading,
a role or a bullet. That works until a role title contains " | ", and it makes a
second format (HTML, PDF, JSON) cost another parser.

Every renderer now reads this instead. Markdown, .docx and each HTML template
are siblings over one structure, so none of them can disagree about what the CV
says.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RenderedRole:
    title: str
    org: str
    dates: str
    location: str | None = None
    bullets: list[str] = field(default_factory=list)


@dataclass
class CvDocument:
    name: str
    #: Location, email, phone — whatever the corpus holds, already filtered.
    contact: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    #: The role title from the posting, used as the CV's own headline.
    target_title: str | None = None
    summary: str | None = None
    skills: list[str] = field(default_factory=list)
    roles: list[RenderedRole] = field(default_factory=list)
    education: list[str] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)


__all__ = ["CvDocument", "RenderedRole"]
