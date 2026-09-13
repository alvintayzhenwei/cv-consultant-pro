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
