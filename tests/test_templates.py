"""The five layouts.

The rules here are about what a template may not do to the content, not about
how it looks. A new look must not be able to drop a section, reorder the reading
order, or quietly turn a submittable CV into one a portal will mangle.
"""

from __future__ import annotations

import re

import pytest

from cv_consultant_pro.document import CvDocument, RenderedRole
from cv_consultant_pro.templates import TEMPLATES, get_template, render_html
from cv_consultant_pro.templates.registry import DEFAULT_TEMPLATE_ID

DOC = CvDocument(
    name="Jordan Reyes",
    contact=["Singapore", "jordan@example.com"],
    links=["example.com"],
    languages=["English", "Malay"],
    target_title="Platform Engineering Lead",
    summary="Engineer who builds platforms and teaches teams to use them.",
    skills=["Technical enablement", "Python"],
    roles=[
        RenderedRole(
            title="Platform Lead",
            org="Northwind Systems",
            dates="04/2023 - Present",
            location="Singapore",
            bullets=["Cut deploy time from 40 minutes to under 4", "Reduced pages by [X]%"],
        )
    ],
    education=["BSc (Hons) Computer Science - Example University"],
    certifications=["Example Certified Practitioner"],
)


@pytest.mark.parametrize("template_id", sorted(TEMPLATES))
def test_every_template_renders_every_section(template_id: str) -> None:
    """A restyle must not be able to lose content."""
    out = render_html(DOC, TEMPLATES[template_id])

    assert "Jordan Reyes" in out
    assert "Platform Engineering Lead" in out
    assert "teaches teams to use them" in out
    assert "Technical enablement" in out
    assert "Northwind Systems" in out
    assert "04/2023 - Present" in out
    assert "Example University" in out
    assert "Example Certified Practitioner" in out


@pytest.mark.parametrize("template_id", sorted(TEMPLATES))
def test_every_template_preserves_a_placeholder_verbatim(template_id: str) -> None:
    """The hole must survive styling, or an unmeasured figure ships looking real."""
    assert "[X]%" in render_html(DOC, TEMPLATES[template_id])


@pytest.mark.parametrize("template_id", sorted(TEMPLATES))
def test_no_template_carries_a_photograph(template_id: str) -> None:
    """A photo invites discrimination screening and is stripped by many employers."""
    out = render_html(DOC, TEMPLATES[template_id])
    assert "<img" not in out
    assert "background-image" not in out


@pytest.mark.parametrize("template_id", sorted(TEMPLATES))
def test_every_template_escapes_its_content(template_id: str) -> None:
    hostile = CvDocument(name='Ann <script>alert("x")</script>', summary="a & b")
    out = render_html(hostile, TEMPLATES[template_id])
    assert "<script>" not in out
    assert "&lt;script&gt;" in out
    assert "a &amp; b" in out


def test_a_portal_safe_template_is_single_column() -> None:
    """The claim has to mean something structurally, not just be a label.

    A railed layout positions a sidebar, which is the commonest reason a parser
    reads a CV in the wrong order — so a template cannot be both railed and
    declared safe.
    """
    for tpl in TEMPLATES.values():
        if tpl.ats_safe:
            assert tpl.layout == "single", f"{tpl.id} claims portal-safe but is railed"


def test_at_least_one_template_of_each_channel_exists() -> None:
    assert any(t.ats_safe for t in TEMPLATES.values())
    assert any(not t.ats_safe for t in TEMPLATES.values())


def test_the_default_template_is_portal_safe() -> None:
    """The default is what someone gets by accident, so it must be the safe one."""
    assert TEMPLATES[DEFAULT_TEMPLATE_ID].ats_safe


def test_an_unknown_template_id_falls_back_rather_than_failing() -> None:
    """A typo should not cost you a generated kit."""
    assert get_template("no-such-layout").id == DEFAULT_TEMPLATE_ID
    assert get_template(None).id == DEFAULT_TEMPLATE_ID
    assert get_template("  RAIL  ").id == "rail"


@pytest.mark.parametrize("template_id", sorted(TEMPLATES))
def test_every_template_sets_a_print_page_size_and_keeps_roles_whole(template_id: str) -> None:
    """These are print documents. A role split across a page break is a bug."""
    out = render_html(DOC, TEMPLATES[template_id])
    assert "@page" in out
    assert "break-inside: avoid" in out


@pytest.mark.parametrize("template_id", sorted(TEMPLATES))
def test_every_template_declares_font_fallbacks(template_id: str) -> None:
    """These render offline and print locally; a webfont may simply not arrive."""
    css = TEMPLATES[template_id].css
    for decl in re.findall(r"font-family:([^;]+);", css):
        assert "," in decl, f"{template_id} has a font stack with no fallback: {decl.strip()}"
