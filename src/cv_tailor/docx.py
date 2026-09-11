"""Write the CV as a .docx whose formatting cannot fail a parser.

Parsing is the only true hard gate on an application — nothing downstream
happens if the text cannot be extracted — and hand-reformatting markdown in
Word is exactly where that gate gets failed. So the document is generated:

  - one column, no tables, text boxes, headers, footers or images
  - a standard system font, present on every machine
  - plain section headings in the document's reading order
  - no styles whose absence changes the order text is extracted in

Everything here is deliberately dull. A résumé parser is not an audience to
impress; it is a machine that must not be confused.
"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

FONT = "Calibri"
BODY_PT = 10.5
NAME_PT = 16
HEADING_PT = 11

# Lines rendered in the markdown as bare uppercase words are section headings.
_SECTIONS = {
    "SUMMARY",
    "CORE SKILLS",
    "EXPERIENCE",
    "EDUCATION",
    "CERTIFICATIONS",
    "OPEN SOURCE AND PUBLICATIONS",
}


def write_docx(markdown: str, path: str | Path) -> Path:
    """Render the CV markdown to a plain, parser-safe .docx."""
    doc = Document()

    style = doc.styles["Normal"]
    style.font.name = FONT
    style.font.size = Pt(BODY_PT)
    style.paragraph_format.space_after = Pt(2)
    style.paragraph_format.space_before = Pt(0)

    for section in doc.sections:
        # Generous but not extravagant. Narrower than this and a long bullet
        # wraps into an unreadable column; wider and the page stops being a page.
        section.left_margin = section.right_margin = Pt(54)
        section.top_margin = section.bottom_margin = Pt(46)

    lines = markdown.splitlines()
    first_written = False

    for raw in lines:
        line = raw.rstrip()
        if not line:
            continue

        if not first_written:
            para = doc.add_paragraph()
            run = para.add_run(line)
            run.bold = True
            run.font.size = Pt(NAME_PT)
            para.alignment = WD_ALIGN_PARAGRAPH.LEFT
            first_written = True
            continue

        if line in _SECTIONS:
            para = doc.add_paragraph()
            para.paragraph_format.space_before = Pt(8)
            run = para.add_run(line)
            run.bold = True
            run.font.size = Pt(HEADING_PT)
            continue

        if line.startswith("- "):
            # A literal bullet character rather than a list style: list styles
            # depend on numbering definitions that some extractors drop, taking
            # the indent and sometimes the order with them.
            para = doc.add_paragraph()
            para.paragraph_format.left_indent = Pt(12)
            para.add_run("• " + line[2:])
            continue

        # A role heading — "TITLE - Org | 01/2020 - Present" — is the only other
        # structural line, and bolding it is the one visual cue that survives
        # plain-text extraction as a separate line anyway.
        if " | " in line and any(ch.isdigit() for ch in line.split("|")[-1]):
            para = doc.add_paragraph()
            para.paragraph_format.space_before = Pt(6)
            para.add_run(line).bold = True
            continue

        doc.add_paragraph(line)

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(target))
    return target


__all__ = ["write_docx"]
