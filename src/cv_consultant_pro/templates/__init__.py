"""Print-ready CV layouts.

Two channels, and the distinction is load-bearing rather than cosmetic.

An **ats_safe** template is what you submit through a portal. Single column, no
positioned sidebars, no icons, no images, reading order matching visual order —
because parsing is the only true hard gate on an application and a two-column
layout is the commonest way to fail it.

A template that is NOT ats_safe is for a human channel: emailed directly to a
recruiter, attached to an outreach message, printed for a meeting. They look
better, and they look better by doing exactly the things a parser mishandles.
The CLI says which is which, every time, rather than leaving you to remember.

No template includes a photograph. On a CV bound for the US, UK, Canada or
Singapore a photo invites discrimination screening and is routinely stripped or
penalised by the employers most likely to be reading this one.
"""

from __future__ import annotations

from .base import Template, render_html
from .registry import TEMPLATES, default_template, get_template

__all__ = ["TEMPLATES", "Template", "default_template", "get_template", "render_html"]
