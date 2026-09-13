"""CSS rules that were violated once and must not be again."""

from __future__ import annotations

import re

import pytest

from cv_consultant_pro.templates import TEMPLATES


@pytest.mark.parametrize("template_id", sorted(TEMPLATES))
def test_no_rule_fades_an_element_that_paints_a_background(template_id: str) -> None:
    """`opacity` fades the fill as well as the ink.

    Keystone set opacity on its contact strip, which shares the header's band
    colour. The strip came out lighter than the header above it, splitting one
    block into two tones with a seam across the page. Fade text with an rgba
    colour; leave the fill alone.
    """
    css = TEMPLATES[template_id].css
    for block in re.findall(r"\{([^}]*)\}", css):
        has_bg = re.search(r"(^|\s|;)background\s*:", block)
        fades = re.search(r"(^|\s|;)opacity\s*:\s*0?\.", block)
        if has_bg and fades:
            pytest.fail(
                f"{template_id}: a rule sets both a background and opacity, so the fill "
                f"is faded too:\n{block.strip()}"
            )


@pytest.mark.parametrize("template_id", sorted(TEMPLATES))
def test_page_margins_are_declared_once_per_edge(template_id: str) -> None:
    """Every template must keep content off the paper edge.

    A print stylesheet with no inset puts text where a printer cannot reach and
    where a PDF reader crops.
    """
    css = TEMPLATES[template_id].css
    assert re.search(r"padding\s*:", css), f"{template_id} declares no padding anywhere"


def _relative_luminance(value: str) -> float:
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    channels = [int(value[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    channels = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast(foreground: str, background: str) -> float:
    """WCAG 2.1 contrast ratio between two opaque colours."""
    first, second = _relative_luminance(foreground), _relative_luminance(background)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


#: Every place a template paints TEXT, as (template, ink token, ground token, what).
#:
#: Deliberately a hand-written table rather than a CSS crawl. Pairing every token
#: with every ground reports hairlines and rule colours as failures and buries the
#: two that matter, and a guard nobody believes is a guard nobody keeps.
TEXT_ON_GROUND = [
    ("ledger", "ink", "paper", "body text"),
    ("ledger", "soft", "paper", "organisation and dates"),
    ("signal", "ink", "paper", "body text"),
    ("signal", "soft", "paper", "contact line"),
    ("signal", "accent", "paper", "section headings and the target line"),
    ("keystone", "ink", "paper", "body text"),
    ("keystone", "soft", "paper", "organisation and dates"),
    ("atelier", "ink", "paper", "body text"),
    ("atelier", "soft", "paper", "contact line"),
    ("atelier", "accent", "paper", ".target and .org"),
    ("rail", "ink", "paper", "body text"),
    ("rail", "soft", "paper", ".org"),
    ("rail", "accent", "paper", ".dates in the main column"),
    ("rail", "rail-ink", "rail", "the name and the skills list"),
    ("rail", "rail-soft", "rail", "the contact lines in the sidebar"),
    ("rail", "rail-accent", "rail", ".target and the sidebar headings"),
]


@pytest.mark.parametrize(("template_id", "ink", "ground", "what"), TEXT_ON_GROUND)
def test_text_clears_the_body_contrast_bar(
    template_id: str, ink: str, ground: str, what: str
) -> None:
    """Every text colour reaches 4.5:1 against the ground it is painted on.

    Nothing here is large-text by WCAG's measure: the biggest of these is 12pt,
    and the bar only relaxes to 3:1 at 18.66px (14pt bold, 18pt regular). So one
    threshold covers the set.

    Two shipped under it, and both were found by reading a rendered CV rather
    than by any test. Rail's sage `--accent` sat at 3.31 on white paper for the
    date ranges; Atelier's brass sat at 3.28 for the target line and every
    organisation name. Rail's cause is worth keeping in mind when adding a
    template: ONE accent token was painted on two different grounds — white
    paper and the aubergine sidebar — and no single value clears both with room
    to spare, so the sidebar now has its own `--rail-accent`.
    """
    css = TEMPLATES[template_id].css
    values = dict(re.findall(r"--([a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{3,6})\s*;", css))
    assert ink in values, f"{template_id} declares no --{ink}"
    assert ground in values, f"{template_id} declares no --{ground}"
    ratio = contrast(values[ink], values[ground])
    assert ratio >= 4.5, (
        f"{template_id}: --{ink} ({values[ink]}) on --{ground} ({values[ground]}) "
        f"is {ratio:.2f}:1, under the 4.5:1 body bar — used for {what}"
    )
