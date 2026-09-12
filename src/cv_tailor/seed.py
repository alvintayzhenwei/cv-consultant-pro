"""Seed a corpus from a LinkedIn profile PDF.

LinkedIn offers no data export a person can actually get at — "Save to PDF" on
your own profile is the only route out — so the PDF is the input here, not a
convenience.

**What this reads, and what it refuses to.** It takes the things a PDF states
plainly and a person cannot recall: employment dates, the order of roles, which
titles sat under which employer, the certifications, the education. Those are
facts printed on the page.

It does NOT write bullets. A corpus bullet is a claim, plus the mechanism behind
it, plus the tags that make it findable — and only the first of those three is
on a LinkedIn profile. Splitting a sentence into claim and mechanism is
authoring, and authoring is the one thing this engine does not do. So the
profile's own prose is written out VERBATIM to a separate notes file, clearly
not a corpus, for the user to turn into evidence a line at a time. A seeded CV
that looked finished but rested on text nobody had confirmed would be worse than
no seed at all.

**The parse is a draft and says so.** LinkedIn's PDF carries no structure beyond
position on a page, so employer boundaries are inferred and are occasionally
inferred wrongly. Every inference that could be wrong is listed in `notes` for
the user to check, rather than presented as settled.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .corpus.dates import YearMonth

#: LinkedIn's own sidebar headings. Anything under one of these is metadata
#: about the profile rather than part of the career history.
SIDEBAR_SECTIONS = (
    "Contact",
    "Top Skills",
    "Languages",
    "Certifications",
    "Honors-Awards",
    "Publications",
    "Patents",
)

_MONTH_NAMES = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
_MONTHS = {name: number for number, name in enumerate(_MONTH_NAMES, start=1)}

_DATE_RANGE = re.compile(
    r"^(?P<start>[A-Z][a-z]+\s+\d{4})\s*[-\u2013\u2014]\s*"
    r"(?P<end>Present|[A-Z][a-z]+\s+\d{4})(?:\s*\(.*\))?$"
)
#: "5 years", "11 months", "2 years 4 months" — LinkedIn's total-tenure line,
#: printed under an employer that holds more than one role.
_TENURE = re.compile(r"^\d+\s+years?(\s+\d+\s+months?)?$|^\d+\s+months?$", re.IGNORECASE)
_PAGE_FOOTER = re.compile(r"^Page \d+ of \d+$")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"^[+]?\d[\d\s()-]{6,}")
#: A contact line that begins with a domain starts a new link rather than
#: continuing the one above, even though it begins lowercase.
_URL_START = re.compile(r"^(https?://|www\.)|^[\w-]+(\.[\w-]+)+(/|\s|$)")
_LIST_GLYPHS = ("-", "*", "\u2022", "\u25b8", "\u2013")
#: A line ending this way is continued by the line below it. That is the only
#: reliable signal separating a wrapped sentence from a new employer's name,
#: because both arrive as short unpunctuated lines and nothing else tells them
#: apart. Without it the parse read "story lifecycle, one verify gate" - the
#: tail of a wrapped bullet - as the employer of the role beneath it.
_WRAP_OPEN = ("-", ",", ":", "&", "+", "/", "\u2013", "\u2014")
_WRAP_OPEN_WORDS = ("and", "or", "with", "for", "the", "of", "to", "in")


class SeedError(Exception):
    """The PDF could not be read as a LinkedIn profile."""


@dataclass
class SeededRole:
    org: str
    title: str
    start: YearMonth | None = None
    end: YearMonth | None = None
    is_current: bool = False
    location: str | None = None
    #: The profile's own prose for this role, verbatim. Never a corpus bullet.
    prose: list[str] = field(default_factory=list)
    #: True when the employer was carried over from the role above rather than
    #: printed beside this one. Usually right; always worth a glance.
    org_inferred: bool = False

    @property
    def slug(self) -> str:
        raw = f"{self.org}-{self.title}".lower()
        slug = re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", raw))
        # Strip AFTER truncating, or a cut that lands on a separator leaves
        # an id trailing a hyphen.
        return slug[:48].strip("-")


@dataclass
class SeededEducation:
    institution: str
    qualification: str


@dataclass
class SeededProfile:
    name: str | None = None
    headline: str | None = None
    location: str | None = None
    email: str | None = None
    phone: str | None = None
    links: list[str] = field(default_factory=list)
    top_skills: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)
    roles: list[SeededRole] = field(default_factory=list)
    education: list[SeededEducation] = field(default_factory=list)
    #: What the parse had to guess at. Shown to the user, never swallowed.
    notes: list[str] = field(default_factory=list)

    def person_block(self) -> list[tuple[str, str]]:
        """The person fields that were actually found, in CV order."""
        fields = [
            ("name", self.name),
            ("email", self.email),
            ("phone", self.phone),
            ("location", self.location),
        ]
        return [(key, value) for key, value in fields if value]


# ── reading the file ────────────────────────────────────────────────────────
def read_pdf(path: str | Path) -> list[list[str]]:
    """One list of lines per page, in layout mode so the sidebar stays separable.

    Layout mode preserves horizontal position as leading spaces, which is the
    only thing distinguishing LinkedIn's left sidebar from the career history
    beside it. Plain extraction interleaves the two and makes page one
    unparseable — the name ends up in the middle of a list of certifications.
    """
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - a declared dependency
        raise SeedError("pypdf is required to read a LinkedIn PDF") from exc

    source = Path(path)
    if not source.is_file():
        raise SeedError(f"no such file: {source}")
    try:
        reader = PdfReader(str(source))
        pages = [
            page.extract_text(extraction_mode="layout").splitlines() for page in reader.pages
        ]
    except Exception as exc:
        raise SeedError(
            f"could not read {source.name} as a PDF. If it came from a scanner it holds "
            "images rather than text, and no amount of parsing will find words in it."
        ) from exc
    if not any(any(line.strip() for line in page) for page in pages):
        raise SeedError(
            f"{source.name} has pages but no extractable text, which usually means it is "
            "a scan. Re-export it from LinkedIn with Save to PDF."
        )
    return pages


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def _normalise(text: str) -> str:
    """Undo two things LinkedIn's PDF writer does to otherwise plain text.

    It sets non-breaking spaces inside phrases, which then fail every ordinary
    word match downstream, and it leaves HTML entities unescaped, so a summary
    arrives reading "Agentic AI &amp; Multi-Agent Systems".
    """
    return text.replace("\u00a0", " ").replace("&amp;", "&").strip()


def _clean(lines: list[str]) -> list[str]:
    kept = []
    for line in lines:
        text = _normalise(line)
        if not text or _PAGE_FOOTER.match(text):
            continue
        kept.append(text)
    return kept


def _continues_below(line: str) -> bool:
    """True when this line's sentence runs on into the next one."""
    if not line:
        return False
    if line.endswith(_WRAP_OPEN):
        return True
    return line.rsplit(" ", 1)[-1].lower() in _WRAP_OPEN_WORDS


# ── page one: identity and the sidebar ──────────────────────────────────────
def _column_boundary(page: list[str]) -> int:
    """The character column where page one's main column starts.

    Layout extraction keeps both columns on the SAME line, padded apart with
    spaces — "    Contact                    Alvin Tay Zhenwei" is one line, not
    two. So the split is by character position, not by leading indent; reading
    it as an indent put the whole sidebar and the person's name into one stream
    and made the first main-column line come out as the word "Summary".

    "Summary" is a main-column heading in every profile that has one, so where
    it begins is where the column begins. Without a summary, fall back to the
    widest gap in use, which lands in the same place by another route.
    """
    for line in page:
        stripped = line.strip()
        if stripped == "Summary" and _indent(line) > 8:
            return _indent(line)
    indents = [_indent(line) for line in page if line.strip()]
    return max(indents, default=0) or 1


def _parse_header(page: list[str], profile: SeededProfile) -> None:
    """Split page one into its two columns, then read both."""
    boundary = _column_boundary(page)
    sidebar = _clean([line[:boundary] for line in page])
    main = _clean([line[boundary:] for line in page])

    _parse_sidebar(sidebar, profile)

    if not main:
        profile.notes.append(
            "Could not find the name block on page one — set the name by hand."
        )
        return

    profile.name = main[0]
    # Between the name and "Summary" sit the headline, which wraps freely, and
    # then the location as the last line of the block.
    tail = main[1:]
    if "Summary" in tail:
        tail = tail[: tail.index("Summary")]
    if tail:
        profile.location = tail[-1]
        headline = " ".join(tail[:-1]).strip()
        profile.headline = headline or None


def _parse_sidebar(lines: list[str], profile: SeededProfile) -> None:
    section: str | None = None
    for line in lines:
        if line in SIDEBAR_SECTIONS:
            section = line
            continue
        if section == "Contact":
            match = _EMAIL.search(line)
            if match:
                profile.email = profile.email or match.group(0)
            elif _PHONE.match(line):
                profile.phone = profile.phone or line
            else:
                profile.links.append(line)
        elif section == "Top Skills":
            profile.top_skills.append(line)
        elif section == "Languages":
            profile.languages.append(line)
        elif section == "Certifications":
            profile.certifications.append(line)

    # The sidebar is narrow, so a long certification or URL arrives wrapped over
    # two lines. Rejoin the continuations before anything else reads them.
    profile.certifications = _rejoin_wrapped(profile.certifications)
    profile.links = _rejoin_wrapped(profile.links, urls=True)
    if profile.certifications:
        profile.notes.append(
            "Certification names are rebuilt from a wrapped column, so a long one can "
            "still arrive split in two. Read the list before accepting it."
        )


def _rejoin_wrapped(lines: list[str], *, urls: bool = False) -> list[str]:
    """Undo the sidebar's line wrapping, which splits names mid-phrase.

    The sidebar column is narrow, so "AWS Educate Getting Started with Cloud
    Ops" arrives as two lines and reads as two certifications. Three signals say
    a line continues the one above it, and all three are needed because each
    misses cases the others catch:

      * the line above ends mid-phrase — a hyphen, a comma, or a word like
        "with" that cannot end a name;
      * this line starts lowercase or with an opening bracket, which no entry
        in its own right does;
      * the line above is as wide as the widest line in the block, which is
        what being wrapped at the column edge looks like.

    The third is the only thing that catches a continuation beginning with a
    capital after a word that could plausibly end a name, and it is why the
    caller is asked to check the list afterwards rather than trust it.
    """
    if not lines:
        return []
    widest = max(len(line) for line in lines)
    joined: list[str] = []
    #: The width of the RAW line most recently seen, which is what says whether
    #: the column wrapped it. Measuring the accumulated entry instead makes every
    #: line after the first look full-width, and the whole list collapses into
    #: one string — which is exactly what the first version of this did.
    last_raw = 0
    for line in lines:
        previous = joined[-1] if joined else ""
        starts_a_url = urls and _URL_START.match(line)
        continues = bool(joined) and not starts_a_url and (
            _continues_below(previous)
            or line[:1].islower()
            or line.startswith("(")
            or (len(lines) >= 3 and last_raw >= widest - 5)
        )
        last_raw = len(line)
        if not continues:
            joined.append(line)
            continue
        joined.pop()
        # A URL wraps AT a hyphen that belongs to it, so dropping the hyphen
        # would quietly corrupt the address. Prose wrapping hyphenates instead.
        if previous.endswith("-"):
            joined.append(previous + line if urls else previous[:-1] + line)
        else:
            joined.append(f"{previous} {line}")
    return joined


# ── the career history ──────────────────────────────────────────────────────
def _parse_date(text: str) -> YearMonth | None:
    parts = text.split()
    if len(parts) != 2 or parts[0] not in _MONTHS:
        return None
    return YearMonth(year=int(parts[1]), month=_MONTHS[parts[0]])


def _looks_like_an_employer(line: str) -> bool:
    """Tell an employer name from the last line of the role above it.

    Employers are short, unpunctuated noun phrases; description text is long, or
    led by a bullet glyph, or ends in a full stop. This is a heuristic, and it
    is reported as one — a role whose employer was carried over is flagged.
    """
    if not line or len(line) > 64 or line.endswith((".", ",", ";", ":")):
        return False
    return line[:1] not in _LIST_GLYPHS


def _looks_like_a_place(line: str) -> bool:
    """LinkedIn prints a role's location on the line directly under its dates."""
    if not line or len(line) > 48 or line.endswith("."):
        return False
    return line[:1] not in _LIST_GLYPHS


def _parse_experience(lines: list[str], profile: SeededProfile) -> None:
    dated = [index for index, line in enumerate(lines) if _DATE_RANGE.match(line)]
    if not dated:
        profile.notes.append(
            "No date ranges were found under Experience, so no roles were seeded. "
            "Check this is a profile PDF rather than a CV uploaded to LinkedIn."
        )
        return

    current_org: str | None = None
    for position, index in enumerate(dated):
        if index == 0:
            continue
        title = lines[index - 1]

        # Walk back from the title: first over any part of the title that broke
        # across lines, then over the employer's total-tenure line, and only
        # then decide whether what remains names an employer or is prose
        # belonging to the role above.
        floor = dated[position - 1] if position else -1
        cursor = index - 2
        while cursor > floor and _continues_below(lines[cursor]):
            title = f"{lines[cursor]} {title}"
            cursor -= 1

        org_inferred = True
        if cursor > floor and _TENURE.match(lines[cursor]):
            cursor -= 1

        # An employer's name and the tail of a wrapped sentence look identical:
        # both are short and unpunctuated. What separates them is the line ABOVE
        # — prose leaves its predecessor hanging mid-sentence, an employer does
        # not. This is the check that stopped "C#, Java, Geocoding, ASP.net"
        # being recorded as somebody's employer.
        runs_on = cursor - 1 > floor and _continues_below(lines[cursor - 1])
        if cursor > floor and not runs_on and _looks_like_an_employer(lines[cursor]):
            current_org = lines[cursor]
            org_inferred = False

        if current_org is None:
            current_org = "TODO"
            org_inferred = False
            profile.notes.append(
                f"Could not tell who employed you as {title!r} — fill in the employer."
            )

        match = _DATE_RANGE.match(lines[index])
        assert match is not None
        is_current = match.group("end") == "Present"

        # Everything up to the header lines of the next role.
        body_end = dated[position + 1] - 1 if position + 1 < len(dated) else len(lines)
        body = lines[index + 1 : max(index + 1, body_end)]
        location = body[0] if body and _looks_like_a_place(body[0]) else None
        prose = body[1:] if location else body

        profile.roles.append(
            SeededRole(
                org=current_org,
                title=title,
                start=_parse_date(match.group("start")),
                end=None if is_current else _parse_date(match.group("end")),
                is_current=is_current,
                location=location,
                prose=[line for line in prose if line],
                org_inferred=org_inferred,
            )
        )


def _parse_education(lines: list[str], profile: SeededProfile) -> None:
    """Entries read institution, then qualification — the latter often wrapped."""
    entry: list[str] = []
    for line in lines:
        ends_entry = len(entry) >= 1 and ("·" in line or line.endswith(")"))
        entry.append(line)
        if ends_entry:
            profile.education.append(
                SeededEducation(institution=entry[0], qualification=" ".join(entry[1:]))
            )
            entry = []
    if len(entry) >= 2:
        profile.education.append(
            SeededEducation(institution=entry[0], qualification=" ".join(entry[1:]))
        )


def parse_profile(pages: list[list[str]]) -> SeededProfile:
    """Read a LinkedIn profile PDF's pages into a draft, with its guesses named."""
    if not pages:
        raise SeedError("the PDF has no pages")

    profile = SeededProfile()
    _parse_header(pages[0], profile)

    body = _clean([line for page in pages for line in page])
    if "Experience" not in body:
        profile.notes.append(
            "No Experience section found — the roles will have to be typed in."
        )
        return profile

    start = body.index("Experience")
    end = len(body)
    for marker in ("Education", "Licenses & Certifications", "Volunteer Experience"):
        if marker in body[start:]:
            end = min(end, body.index(marker, start))
    _parse_experience(body[start + 1 : end], profile)

    if "Education" in body:
        _parse_education(body[body.index("Education") + 1 :], profile)

    if any(role.org_inferred for role in profile.roles):
        profile.notes.append(
            "Some roles took their employer from the role above, which is how LinkedIn "
            "groups several titles at one company. The ones marked 'carried over' in "
            "the notes file are the ones to check."
        )
    return profile


def seed_from_pdf(path: str | Path) -> SeededProfile:
    """Read a LinkedIn profile PDF into a draft profile."""
    return parse_profile(read_pdf(path))




# ── writing the draft out ───────────────────────────────────────────────────
def _yaml_str(value: str) -> str:
    """Quote a scalar so YAML cannot reinterpret it.

    Employer and role names carry colons, quotes and leading digits ("365
    solutions Sdn Bhd"), every one of which changes a YAML scalar's meaning.
    """
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _role_id(role: SeededRole, taken: set[str]) -> str:
    base = role.slug or "role"
    candidate, suffix = base, 2
    while candidate in taken:
        candidate, suffix = f"{base}-{suffix}", suffix + 1
    taken.add(candidate)
    return candidate


def to_corpus_yaml(profile: SeededProfile) -> str:
    """The draft corpus: everything the PDF stated, and nothing it implied.

    Roles come out with dates and no bullets. That is not an oversight — it is
    the contract. Evidence arrives through `cv_corpus_add` one line at a time,
    in the user's own words, from the notes file beside this one.
    """
    person = profile.person_block()
    lines = [
        "# Drafted from a LinkedIn profile PDF by cv-tailor. Nothing here is final.",
        "#",
        "# What was read off the page: employers, titles, dates, certifications,",
        "# education. What was NOT: a single bullet. A bullet needs a claim, the",
        "# mechanism behind it and its tags, and a profile carries only prose - so",
        "# the prose is in the notes file beside this one, in your own words, for you",
        "# to turn into evidence a line at a time.",
        "",
        "person:",
    ]
    for key, value in person:
        lines.append(f"  {key}: {_yaml_str(value)}")
    lines += ["", "language: en", "", "roles:"]

    taken: set[str] = set()
    for role in profile.roles:
        role_id = _role_id(role, taken)
        lines.append(f"  - id: {role_id}")
        lines.append(f"    org: {_yaml_str(role.org)}")
        lines.append(f"    title: {_yaml_str(role.title)}")
        lines.append(f"    start: {_yaml_str(role.start.as_yaml()) if role.start else 'TODO'}")
        if role.is_current:
            lines.append("    end: present")
        elif role.end is not None:
            lines.append(f"    end: {_yaml_str(role.end.as_yaml())}")
        else:
            lines.append("    end: TODO")
        if role.location:
            lines.append(f"    location: {_yaml_str(role.location)}")
        if role.org_inferred:
            lines.append("    # Employer carried over from the role above. Check it.")
        lines.append("    tags: []          # what this role was about, in your words")
        lines.append("    bullets: []       # add with cv_corpus_add, from the notes file")

    if profile.top_skills:
        lines += ["", "skills:"]
        for skill in profile.top_skills:
            lines.append(f"  - name: {_yaml_str(skill)}")
            lines.append("    aliases: []       # how a posting might word this")
            lines.append("    evidence_refs: [] # the bullet ids that prove it")

    if profile.education:
        lines += ["", "education:"]
        for entry in profile.education:
            lines.append(f"  - institution: {_yaml_str(entry.institution)}")
            lines.append(f"    qualification: {_yaml_str(entry.qualification)}")

    if profile.certifications:
        lines += ["", "certifications:"]
        for cert in profile.certifications:
            lines.append(f"  - name: {_yaml_str(cert)}")
            lines.append("    held: true")

    return "\n".join(lines) + "\n"


def to_notes_markdown(profile: SeededProfile) -> str:
    """Your LinkedIn prose, verbatim, per role — the raw material for bullets.

    Deliberately a separate file with a separate extension. Nothing here is
    loaded by anything; it exists so that turning a profile into evidence is
    reading your own sentences back, not typing a decade out from memory.
    """
    out = [
        f"# {profile.name or 'Your'} profile — raw notes",
        "",
        "These are your own words, copied out of your LinkedIn profile without a",
        "single change. They are **not** corpus entries and nothing reads them.",
        "",
        "Work down the list with your assistant. For each line worth keeping it will",
        "ask you two things a profile never states: the **mechanism** (how you",
        "actually did it) and whether any figure in it was **measured or estimated**.",
        "An estimate is fine — it renders as a visible placeholder rather than a",
        "number you would have to defend in an interview.",
        "",
    ]
    if profile.notes:
        out += ["## Check these first", ""]
        out += [f"- {note}" for note in profile.notes]
        out.append("")

    for role in profile.roles:
        dates = ""
        if role.start:
            if role.is_current:
                finish = "Present"
            else:
                finish = role.end.render() if role.end else "?"
            dates = f" | {role.start.render()} - {finish}"
        carried = "  _(employer carried over - check)_" if role.org_inferred else ""
        out += [f"## {role.title} - {role.org}{dates}{carried}", ""]
        if role.prose:
            out += [f"- {line}" for line in role.prose]
        else:
            out.append("_The profile said nothing about this role._")
        out.append("")
    return "\n".join(out)


__all__ = [
    "SIDEBAR_SECTIONS",
    "SeedError",
    "SeededEducation",
    "SeededProfile",
    "SeededRole",
    "parse_profile",
    "read_pdf",
    "seed_from_pdf",
    "to_corpus_yaml",
    "to_notes_markdown",
]
