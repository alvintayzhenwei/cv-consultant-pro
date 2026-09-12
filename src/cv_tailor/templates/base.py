"""The shared HTML skeleton every template fills.

One structure, five stylesheets. A template supplies CSS and declares whether it
is single-column or railed; it never rewrites the document, so a new look cannot
silently drop a section or reorder the reading order.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Literal

from ..document import CvDocument

Layout = Literal["single", "rail"]


@dataclass(frozen=True)
class Template:
    id: str
    name: str
    #: One line on the direction, shown by `cv-tailor templates`.
    blurb: str
    #: False means: do not submit this through an application portal.
    ats_safe: bool
    layout: Layout
    css: str
    #: Google Fonts family spec, or None for system faces only.
    fonts: str | None = None


def _e(text: str) -> str:
    return html.escape(text, quote=True)


def _section(title: str, body: str, *, cls: str = "") -> str:
    klass = f" class=\"{cls}\"" if cls else ""
    return f"<section{klass}>\n<h2>{_e(title)}</h2>\n{body}\n</section>"


def _roles_html(doc: CvDocument) -> str:
    parts: list[str] = []
    for role in doc.roles:
        org = _e(role.org)
        if role.location:
            org += f"<span class=\"loc\">{_e(role.location)}</span>"
        bullets = "\n".join(f"<li>{_e(b)}</li>" for b in role.bullets)
        parts.append(
            "<article class=\"role\">\n"
            f"<h3>{_e(role.title)}</h3>\n"
            f"<p class=\"org\">{org}</p>\n"
            f"<p class=\"dates\">{_e(role.dates)}</p>\n"
            f"<ul>\n{bullets}\n</ul>\n"
            "</article>"
        )
    return "\n".join(parts)


def _list_html(items: list[str], cls: str) -> str:
    rows = "\n".join(f"<li>{_e(i)}</li>" for i in items)
    return f"<ul class=\"{cls}\">\n{rows}\n</ul>"


def render_html(doc: CvDocument, template: Template) -> str:
    """Render one CV to a self-contained, print-ready HTML page."""
    font_link = (
        f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?{template.fonts}'
        '&display=swap">'
        if template.fonts
        else ""
    )

    contact = _list_html(doc.contact + doc.links, "contact") if (doc.contact or doc.links) else ""
    languages = (
        _section("Languages", _list_html(doc.languages, "plain")) if doc.languages else ""
    )
    skills = _section("Core skills", _list_html(doc.skills, "skills")) if doc.skills else ""
    summary = (
        _section("Summary", f"<p class=\"summary\">{_e(doc.summary)}</p>") if doc.summary else ""
    )
    education = _section("Education", _list_html(doc.education, "plain")) if doc.education else ""
    certs = (
        _section("Certifications", _list_html(doc.certifications, "plain"))
        if doc.certifications
        else ""
    )
    experience = _section("Experience", _roles_html(doc), cls="experience")

    header = (
        "<header>\n"
        f"<h1>{_e(doc.name)}</h1>\n"
        + (f"<p class=\"target\">{_e(doc.target_title)}</p>\n" if doc.target_title else "")
        + "</header>"
    )

    if template.layout == "rail":
        # The rail carries the scannable, non-narrative material. Experience
        # stays in the main column so a reader's eye follows one thread.
        body = (
            f"<aside class=\"rail\">\n{header}\n{contact}\n{skills}\n{languages}\n"
            f"{certs}\n{education}\n</aside>\n"
            f"<main>\n{summary}\n{experience}\n</main>"
        )
    else:
        body = (
            f"{header}\n{contact}\n{summary}\n{skills}\n{experience}\n"
            f"{education}\n{certs}"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{_e(doc.name)} — {_e(doc.target_title or "CV")}</title>
{font_link}
<style>
{_RESET}
{template.css}
</style>
</head>
<body class="cv cv--{template.id} layout--{template.layout}">
{body}
</body>
</html>
"""


# Shared reset. Deliberately small: each template owns its own type and colour,
# and anything set here it would only have to undo.
_RESET = """
*, *::before, *::after { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
h1, h2, h3, p, ul, li { margin: 0; padding: 0; }
ul { list-style: none; }

@page { size: A4; margin: 0; }

@media print {
  /* Without this, a coloured rail or name band prints as white and the layout
     falls apart on the one medium these templates are actually for. */
  body { print-color-adjust: exact; -webkit-print-color-adjust: exact; }
  a { text-decoration: none; }
}

/* On screen the page sits on a grey ground so its edges are visible; in print
   the ground does not exist. */
@media screen {
  html { background: #e6e6e4; padding: 24px 0; }
  body { margin: 0 auto; box-shadow: 0 2px 14px rgba(0,0,0,.18); }
}

body { width: 210mm; min-height: 297mm; }

/* A role must not break across a page. Splitting a heading from its bullets is
   the one layout failure a reader notices immediately. */
.role { break-inside: avoid; }
section { break-inside: avoid-page; }
"""

__all__ = ["Layout", "Template", "render_html"]
