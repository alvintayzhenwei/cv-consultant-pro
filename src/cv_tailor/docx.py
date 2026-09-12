"""Write the CV as a .docx whose formatting cannot fail a parser.

Parsing is the only true hard gate on an application — nothing downstream
happens if the text cannot be extracted — and hand-reformatting in Word is
exactly where that gate gets failed. So the document is generated:

  - one column, no tables, text boxes, headers, footers or images
  - a standard font, present on every machine
  - plain section headings in the document's reading order
  - no list styles, whose numbering definitions some extractors drop

This is the SUBMIT format. The HTML templates are better looking and several of
them are better looking precisely because they do things a parser mishandles;
this one stays dull on purpose.

It renders from CvDocument, not from the markdown. The first version parsed the
markdown back out, inferring from a line's shape whether it was a heading, a
role or a bullet — which breaks the moment a role title contains " | ".
"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.shared import Pt, RGBColor

from .document import CvDocument

FONT = "Calibri"
BODY_PT = 10.5
NAME_PT = 18
HEADING_PT = 11
# One restrained accent. A parser ignores colour entirely, and a human reader
# gets the section structure a step faster.
ACCENT = RGBColor(0x1F, 0x3A, 0x5F)
MUTED = RGBColor(0x55, 0x5D, 0x66)


def _para(doc, text: str = "", *, size: float = BODY_PT, bold: bool = False,
          colour: RGBColor | None = None, before: float = 0, after: float = 2,
          indent: float = 0, italic: bool = False):
    para = doc.add_paragraph()
    para.paragraph_format.space_before = Pt(before)
    para.paragraph_format.space_after = Pt(after)
    if indent:
        para.paragraph_format.left_indent = Pt(indent)
    if text:
        run = para.add_run(text)
        run.bold = bold
        run.italic = italic
        run.font.size = Pt(size)
        if colour is not None:
            run.font.color.rgb = colour
    return para


def write_docx(doc_model: CvDocument, path: str | Path) -> Path:
    """Render the CV to a plain, parser-safe .docx."""
    docx = Document()

    style = docx.styles["Normal"]
    style.font.name = FONT
    style.font.size = Pt(BODY_PT)
    style.paragraph_format.space_after = Pt(2)
    style.paragraph_format.space_before = Pt(0)

    for section in docx.sections:
        section.left_margin = section.right_margin = Pt(54)
        section.top_margin = section.bottom_margin = Pt(46)

    _para(docx, doc_model.name.upper(), size=NAME_PT, bold=True, after=1)
    if doc_model.target_title:
        _para(docx, doc_model.target_title, size=11, bold=True, colour=ACCENT, after=3)
    if doc_model.contact:
        _para(docx, " | ".join(doc_model.contact), size=9, colour=MUTED, after=1)
    if doc_model.links:
        _para(docx, " | ".join(doc_model.links), size=9, colour=MUTED, after=1)
    if doc_model.languages:
        _para(docx, "Languages: " + ", ".join(doc_model.languages), size=9, colour=MUTED)

    def heading(text: str) -> None:
        _para(docx, text.upper(), size=HEADING_PT, bold=True, colour=ACCENT, before=10, after=3)

    if doc_model.summary:
        heading("Summary")
        _para(docx, doc_model.summary)

    if doc_model.skills:
        heading("Core skills")
        _para(docx, ", ".join(doc_model.skills))

    heading("Experience")
    for role in doc_model.roles:
        org = role.org + (f", {role.location}" if role.location else "")
        _para(docx, f"{role.title} — {org}", bold=True, before=7, after=0)
        if role.dates:
            _para(docx, role.dates, size=9, colour=MUTED, italic=True, after=2)
        for bullet in role.bullets:
            # A literal bullet character, not a list style: list styles depend on
            # numbering definitions that some extractors drop, taking the indent
            # and sometimes the reading order with them.
            _para(docx, "• " + bullet, indent=11, after=1.5)

    if doc_model.education:
        heading("Education")
        for line in doc_model.education:
            _para(docx, line)

    if doc_model.certifications:
        heading("Certifications")
        _para(docx, " | ".join(doc_model.certifications))

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    docx.save(str(target))
    return target


__all__ = ["write_docx"]
