"""The five layouts.

Each is a deliberate direction rather than a palette swap: its own hue family,
its own type pairing, its own idea about what structure means. Three are
submittable through a portal; two are for a human channel and say so.
"""

from __future__ import annotations

from .base import Template

# ── 1. Ledger ────────────────────────────────────────────────────────────────
# An engineering notebook. Rules carry data rather than decorate: every
# horizontal line in this layout separates a record from the next one, and dates
# sit in their own right-hand column the way a ledger keeps its figures. Oxblood
# is the only colour, used once per section and never for emphasis inside prose.
_LEDGER = Template(
    id="ledger",
    name="Ledger",
    blurb="Engineering notebook. Ruled records, dates in their own column, oxblood on warm paper.",
    ats_safe=True,
    layout="single",
    fonts="family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=Source+Sans+3:wght@400;600",
    css="""
:root {
  --ink: #1b1d1e;
  --soft: #55585a;
  --paper: #fbfaf7;
  --rule: #d8d4cb;
  --accent: #7a2e2e;
}
body {
  background: var(--paper);
  color: var(--ink);
  font-family: "Source Sans 3", "Segoe UI", system-ui, sans-serif;
  font-size: 10.2pt;
  line-height: 1.5;
  padding: 17mm 18mm;
}
header { border-bottom: 2px solid var(--ink); padding-bottom: 7px; margin-bottom: 4px; }
h1 {
  font-family: "Source Serif 4", Georgia, serif;
  font-size: 23pt; font-weight: 600; line-height: 1.05;
  letter-spacing: -0.01em;
}
.target { color: var(--accent); font-size: 10.5pt; font-weight: 600; margin-top: 3px; }

.contact {
  display: flex; flex-wrap: wrap; gap: 3px 14px;
  font-size: 8.8pt; color: var(--soft);
  padding: 6px 0 0; border-bottom: 1px solid var(--rule); padding-bottom: 9px;
}

section { margin-top: 13px; }
h2 {
  font-family: "Source Serif 4", Georgia, serif;
  font-size: 11.4pt; font-weight: 600; color: var(--accent);
  border-bottom: 1px solid var(--rule); padding-bottom: 3px; margin-bottom: 7px;
}
.summary { max-width: 74ch; }

.skills { display: flex; flex-wrap: wrap; gap: 2px 0; }
.skills li { font-size: 9.4pt; }
.skills li:not(:last-child)::after { content: " · "; color: var(--rule); }

/* Dates in their own column is the whole conceit — a record and its date, not a
   heading with a date appended. */
.role { display: grid; grid-template-columns: 1fr 26mm; gap: 0 8px; margin-bottom: 11px; }
.role h3 { font-size: 10.6pt; font-weight: 600; }
.org { grid-column: 1; color: var(--soft); font-size: 9.6pt; }
.org .loc::before { content: " — "; }
.dates {
  grid-column: 2; grid-row: 1 / span 2;
  text-align: right; font-size: 9pt; color: var(--soft);
  font-variant-numeric: tabular-nums; white-space: nowrap;
}
.role ul { grid-column: 1 / -1; margin-top: 4px; }
.role li { position: relative; padding-left: 11px; margin-bottom: 2.5px; max-width: 80ch; }
.role li::before { content: "—"; position: absolute; left: 0; color: var(--accent); }

.plain li { margin-bottom: 2px; }
""",
)

# ── 2. Signal ────────────────────────────────────────────────────────────────
# One family, weights doing all the work, everything tight. A short accent bar
# replaces a rule so a section reads as a marker rather than a boundary. Built
# for a technical reader who is scanning for facts, not being courted.
_SIGNAL = Template(
    id="signal",
    name="Signal",
    blurb="Dense and engineered. One typeface, weight contrast, teal markers, no ornament.",
    ats_safe=True,
    layout="single",
    fonts="family=IBM+Plex+Sans:wght@400;500;600;700",
    css="""
:root {
  --ink: #15171a;
  --soft: #5d666d;
  --paper: #ffffff;
  --accent: #0f6e6e;
  --hair: #e3e7e9;
}
body {
  background: var(--paper);
  color: var(--ink);
  font-family: "IBM Plex Sans", "Segoe UI", system-ui, sans-serif;
  font-size: 9.9pt;
  line-height: 1.46;
  padding: 15mm 17mm;
}
header { margin-bottom: 9px; }
h1 { font-size: 20pt; font-weight: 700; letter-spacing: -0.02em; }
.target { font-size: 10pt; font-weight: 500; color: var(--accent); margin-top: 1px; }

.contact { display: flex; flex-wrap: wrap; gap: 2px 12px; font-size: 8.5pt; color: var(--soft); }

section { margin-top: 12px; }
h2 {
  font-size: 8.4pt; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.1em; color: var(--accent); margin-bottom: 6px;
  display: flex; align-items: center; gap: 7px;
}
h2::after { content: ""; flex: 1; height: 2px; background: var(--accent); opacity: .22; }
.summary { max-width: 76ch; }

.skills { display: flex; flex-wrap: wrap; gap: 3px 4px; }
.skills li {
  font-size: 8.6pt; font-weight: 500;
  border: 1px solid var(--hair); border-radius: 2px;
  padding: 1px 6px; color: var(--soft);
}

.role { margin-bottom: 9px; }
.role h3 { font-size: 10.2pt; font-weight: 600; display: inline; }
.org { display: inline; color: var(--accent); font-weight: 500; font-size: 10.2pt; }
.org::before { content: " · "; color: var(--soft); font-weight: 400; }
.org .loc { display: none; }
.dates {
  font-size: 8.4pt; color: var(--soft); font-weight: 500;
  font-variant-numeric: tabular-nums; margin-top: 1px;
}
.role ul { margin-top: 3px; }
.role li { position: relative; padding-left: 10px; margin-bottom: 2px; max-width: 82ch; }
.role li::before {
  content: ""; position: absolute; left: 0; top: 6px;
  width: 4px; height: 4px; background: var(--accent); opacity: .55;
}

.plain li { margin-bottom: 2px; }
""",
)

# ── 3. Keystone ──────────────────────────────────────────────────────────────
# A solid band holds the name, and the slab face gives the headings weight
# without caps or letterspacing. Deliberately the most conventional of the
# three safe layouts: the one to send somewhere conservative.
_KEYSTONE = Template(
    id="keystone",
    name="Keystone",
    blurb="Solid name band, slab headings, sentence case throughout. Deep blue, conventional.",
    ats_safe=True,
    layout="single",
    fonts="family=Zilla+Slab:wght@500;600;700&family=Public+Sans:wght@400;600",
    css="""
:root {
  --ink: #1a1d21;
  --soft: #565d66;
  --paper: #ffffff;
  --band: #1f3a5f;
  --accent: #1f3a5f;
  --hair: #dfe3e8;
}
body {
  background: var(--paper);
  color: var(--ink);
  font-family: "Public Sans", "Segoe UI", system-ui, sans-serif;
  font-size: 10pt;
  line-height: 1.48;
}
header { background: var(--band); color: #fff; padding: 13mm 17mm 9mm; }
h1 {
  font-family: "Zilla Slab", Georgia, serif;
  font-size: 25pt; font-weight: 700; line-height: 1.02;
}
.target { font-size: 10.5pt; margin-top: 4px; opacity: .85; }

.contact {
  display: flex; flex-wrap: wrap; gap: 3px 16px;
  background: var(--band); color: #fff;
  font-size: 8.7pt; padding: 0 17mm 10mm; opacity: .82;
}

section { margin: 12px 17mm 0; }
section:last-of-type { margin-bottom: 14mm; }
h2 {
  font-family: "Zilla Slab", Georgia, serif;
  font-size: 12.6pt; font-weight: 600; color: var(--accent);
  margin-bottom: 6px;
}
.summary { max-width: 74ch; }

.skills { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1px 12px; }
.skills li { font-size: 9.2pt; color: var(--soft); }

.role { margin-bottom: 11px; padding-bottom: 9px; border-bottom: 1px solid var(--hair); }
.experience .role:last-child { border-bottom: 0; padding-bottom: 0; }
.role h3 { font-family: "Zilla Slab", Georgia, serif; font-size: 11.2pt; font-weight: 600; }
.org { color: var(--soft); font-size: 9.6pt; }
.org .loc::before { content: ", "; }
.dates {
  font-size: 8.8pt; color: var(--soft); font-variant-numeric: tabular-nums;
  margin-top: 1px;
}
.role ul { margin-top: 4px; }
.role li { position: relative; padding-left: 12px; margin-bottom: 2.5px; max-width: 80ch; }
.role li::before { content: "▪"; position: absolute; left: 0; color: var(--accent); font-size: 7pt; top: 2px; }

.plain li { margin-bottom: 2px; }
""",
)

# ── 4. Atelier ───────────────────────────────────────────────────────────────
# Editorial. Asymmetric margins, a serif display at a size that earns its space,
# and brass used once. NOT portal-safe: the wide outer margin and the display
# scale are the point, and they cost extraction fidelity.
_ATELIER = Template(
    id="atelier",
    name="Atelier",
    blurb="Editorial. Asymmetric margins, large serif display, brass on blush. Human channel.",
    ats_safe=False,
    layout="single",
    fonts="family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,600&family=Karla:wght@400;600",
    css="""
:root {
  --ink: #221c26;
  --soft: #5f5566;
  --paper: #f7f2f4;
  --plum: #2e2038;
  --accent: #a8802c;
  --hair: #ddd2d8;
}
body {
  background: var(--paper);
  color: var(--ink);
  font-family: "Karla", "Segoe UI", system-ui, sans-serif;
  font-size: 10pt;
  line-height: 1.55;
  padding: 20mm 30mm 18mm 20mm;
}
header { margin-bottom: 14px; }
h1 {
  font-family: "Newsreader", Georgia, serif;
  font-size: 34pt; font-weight: 400; line-height: 0.98;
  color: var(--plum); letter-spacing: -0.02em;
}
.target {
  font-family: "Newsreader", Georgia, serif;
  font-size: 12pt; font-style: italic; color: var(--accent); margin-top: 6px;
}
.contact {
  display: flex; flex-wrap: wrap; gap: 2px 14px;
  font-size: 8.6pt; color: var(--soft);
  border-top: 1px solid var(--hair); padding-top: 8px; margin-top: 12px;
}

section { margin-top: 15px; }
h2 {
  font-family: "Newsreader", Georgia, serif;
  font-size: 13pt; font-weight: 600; color: var(--plum); margin-bottom: 7px;
}
.summary {
  font-family: "Newsreader", Georgia, serif;
  font-size: 11.4pt; line-height: 1.5; max-width: 66ch; color: var(--plum);
}

.skills { display: flex; flex-wrap: wrap; gap: 2px 0; max-width: 72ch; }
.skills li { font-size: 9.2pt; color: var(--soft); }
.skills li:not(:last-child)::after { content: " / "; color: var(--accent); }

.role { margin-bottom: 13px; }
.role h3 {
  font-family: "Newsreader", Georgia, serif;
  font-size: 12pt; font-weight: 600; color: var(--plum);
}
.org { color: var(--accent); font-size: 9.6pt; font-weight: 600; }
.org .loc { color: var(--soft); font-weight: 400; }
.org .loc::before { content: " · "; }
.dates { font-size: 8.8pt; color: var(--soft); font-variant-numeric: tabular-nums; }
.role ul { margin-top: 5px; }
.role li { position: relative; padding-left: 14px; margin-bottom: 3px; max-width: 72ch; }
.role li::before { content: ""; position: absolute; left: 0; top: 7px; width: 7px; height: 1px; background: var(--accent); }

.plain li { margin-bottom: 2px; font-size: 9.4pt; }
""",
)

# ── 5. Rail ──────────────────────────────────────────────────────────────────
# The two-column sidebar layout, done without a photo or skill bars. The rail
# holds everything scannable so the main column carries one unbroken narrative.
# NOT portal-safe, and that is inherent: a positioned sidebar is the single most
# common cause of a parser reading a CV in the wrong order.
_RAIL = Template(
    id="rail",
    name="Rail",
    blurb="Sidebar layout. Aubergine rail, sage accent, no photo. Human channel only.",
    ats_safe=False,
    layout="rail",
    fonts="family=Work+Sans:wght@400;500;600;700&family=Lora:wght@400;600",
    css="""
:root {
  --ink: #23202a;
  --soft: #5d5866;
  --paper: #ffffff;
  --rail: #2b1f2e;
  --rail-ink: #efe9ee;
  --rail-soft: #b3a5b5;
  --accent: #7d9471;
  --hair: #e4e0e6;
}
body {
  display: grid;
  grid-template-columns: 62mm 1fr;
  background: var(--paper);
  color: var(--ink);
  font-family: "Work Sans", "Segoe UI", system-ui, sans-serif;
  font-size: 9.8pt;
  line-height: 1.5;
}

.rail {
  background: var(--rail); color: var(--rail-ink);
  padding: 15mm 9mm 12mm;
}
.rail header { margin-bottom: 14px; }
.rail h1 {
  font-family: "Lora", Georgia, serif;
  font-size: 20pt; font-weight: 600; line-height: 1.05;
}
.rail .target { font-size: 9.4pt; color: var(--accent); margin-top: 5px; font-weight: 500; }
.rail section { margin-top: 14px; }
.rail h2 {
  font-size: 8.2pt; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.11em; color: var(--accent); margin-bottom: 6px;
  padding-bottom: 4px; border-bottom: 1px solid rgba(255,255,255,.16);
}
.rail li { font-size: 8.8pt; color: var(--rail-soft); margin-bottom: 3px; word-break: break-word; }
.rail .skills { display: block; }
.rail .skills li { color: var(--rail-ink); }

main { padding: 15mm 14mm 12mm 12mm; }
main section { margin-bottom: 13px; }
main h2 {
  font-family: "Lora", Georgia, serif;
  font-size: 12.4pt; font-weight: 600; color: var(--rail);
  margin-bottom: 7px; padding-left: 11px; position: relative;
}
main h2::before {
  content: ""; position: absolute; left: 0; top: 3px; bottom: 3px;
  width: 3px; background: var(--accent);
}
.summary { max-width: 66ch; }

.role { margin-bottom: 11px; padding-left: 11px; position: relative; }
.role::before {
  content: ""; position: absolute; left: 0; top: 5px;
  width: 5px; height: 5px; border-radius: 50%; background: var(--accent);
}
.role h3 { font-size: 10.4pt; font-weight: 600; }
.org { color: var(--soft); font-size: 9.2pt; font-style: italic; }
.org .loc::before { content: " · "; font-style: normal; }
.dates { font-size: 8.4pt; color: var(--accent); font-weight: 500; font-variant-numeric: tabular-nums; }
.role ul { margin-top: 4px; }
.role li { position: relative; padding-left: 11px; margin-bottom: 2.5px; max-width: 70ch; }
.role li::before { content: "▸"; position: absolute; left: 0; color: var(--accent); font-size: 7.5pt; top: 1.5px; }
""",
)


TEMPLATES: dict[str, Template] = {
    t.id: t for t in (_LEDGER, _SIGNAL, _KEYSTONE, _ATELIER, _RAIL)
}

#: The safe default. A portal submission is the common case, and a template that
#: looks better but parses worse is the wrong thing to hand someone by accident.
DEFAULT_TEMPLATE_ID = "signal"


def default_template() -> Template:
    return TEMPLATES[DEFAULT_TEMPLATE_ID]


def get_template(template_id: str | None) -> Template:
    """Resolve a template id, falling back to the safe default for an unknown one.

    Falls back rather than raising, mirroring how the rest of the engine treats
    an unrecognised input: a typo should not lose you a generated kit.
    """
    if not template_id:
        return default_template()
    return TEMPLATES.get(template_id.strip().lower(), default_template())


__all__ = ["DEFAULT_TEMPLATE_ID", "TEMPLATES", "default_template", "get_template"]
