"""Writing back into the corpus file, without flattening what the user wrote.

The corpus is a file a person hand-edits: it carries their comments, their
ordering, their blank lines. Loading it into Python and dumping it back would
lose all three — PyYAML has no round-trip mode — and a tool that quietly
reformats your file every time it touches it is a tool you stop pointing at your
file. So edits here are made as **text**, against the block they belong to, and
everything around them is left exactly as it was.

Two rules hold for every operation in this module:

  * **Nothing is written unless the result still loads.** Every edit is applied
    in memory, re-validated, and only then saved. A corpus is the one artefact
    the user cannot reconstruct, and half an edit is worse than none.
  * **Nothing is written that the user did not say.** These functions take
    values; they do not compose them. `mechanism` is not inferred from `claim`,
    a figure is never promoted to verified, and a tag is never guessed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .corpus import CorpusError, load_corpus_text, resolve_corpus_path
from .corpus.dates import YearMonth


class EditError(Exception):
    """The edit was refused. The file on disk is unchanged."""


@dataclass
class NewBullet:
    """One piece of evidence, in the user's own words.

    `claim` and `mechanism` are separate fields because they answer different
    questions — what happened, and how you brought it about — and a CV bullet
    that only answers the first is an assertion. `metric_value` is filled only
    when the user said a figure AND said it was measured; otherwise
    `placeholder` renders as a visible hole, which is the whole anti-fabrication
    contract in one field.
    """

    id: str
    claim: str
    mechanism: str
    tags: list[str]
    metric_value: str | None = None
    placeholder: str | None = None

    def __post_init__(self) -> None:
        if self.metric_value and self.placeholder:
            raise EditError(
                "a figure is either measured or it is not — give a value or a "
                "placeholder, never both"
            )
        if not self.tags:
            raise EditError("a bullet with no tags can never be matched to a posting")
        if self.placeholder and self.placeholder not in f"{self.claim} {self.mechanism}":
            raise EditError(
                f"the placeholder {self.placeholder!r} has to appear in the claim or the "
                "mechanism, or it renders nowhere and the hole is invisible. Write the "
                "sentence with the placeholder in it, the way it should read on the CV."
            )


def _quote(value: str) -> str:
    """Quote a scalar so YAML cannot reinterpret what the user typed.

    Claims contain colons ("Migrated: phase one"), begin with digits, and end in
    question marks. Every one of those changes an unquoted scalar's meaning.
    """
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _role_span(lines: list[str], role_id: str) -> tuple[int, int, str]:
    """Where a role's block starts and ends, and the indent its keys sit at."""
    start = None
    indent = ""
    for number, line in enumerate(lines):
        match = re.match(r"^(\s*)-\s+id:\s*(.+?)\s*(#.*)?$", line)
        if match and match.group(2).strip().strip("\"'") == role_id:
            start = number
            indent = match.group(1) + "  "
            break
    if start is None:
        raise EditError(f"no role with id {role_id!r} in the corpus")

    for number in range(start + 1, len(lines)):
        line = lines[number]
        if line.strip() and not line.startswith(indent):
            return start, number, indent
        if re.match(rf"^{re.escape(indent)}-\s", line):
            return start, number, indent
    return start, len(lines), indent


def set_role_dates(
    text: str, role_id: str, *, start: str, end: str | None, is_current: bool
) -> str:
    """Fill in the dates of a role whose history the corpus did not know.

    This is the one outstanding item that blocks everything downstream: every CV
    format prints a date range, so there is no honest way to render around it.
    """
    _validate_month(start, "start")
    if end and not is_current:
        _validate_month(end, "end")

    lines = text.splitlines()
    first, last, indent = _role_span(lines, role_id)
    block = lines[first:last]

    end_value = "present" if is_current else (f'"{end}"' if end else "TODO")
    replaced = {"start": False, "end": False}
    for offset, line in enumerate(block):
        for key, value in (("start", f'"{start}"'), ("end", end_value)):
            if re.match(rf"^{re.escape(indent)}{key}:", line):
                block[offset] = f"{indent}{key}: {value}"
                replaced[key] = True
    # A role can legitimately arrive with no date keys at all, in which case
    # they are added rather than the edit silently doing nothing.
    additions = [
        f"{indent}{key}: {value}"
        for key, value in (("start", f'"{start}"'), ("end", end_value))
        if not replaced[key]
    ]
    lines[first:last] = block[:1] + additions + block[1:]
    return "\n".join(lines) + "\n"


def _validate_month(value: str, field: str) -> None:
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", value):
        raise EditError(f"{field} must be YYYY-MM, such as 2019-06 — got {value!r}")
    YearMonth(year=int(value[:4]), month=int(value[5:]))


def add_bullet(text: str, role_id: str, bullet: NewBullet) -> str:
    """Append one piece of evidence to a role, in the user's own words."""
    lines = text.splitlines()
    _first, last, indent = _role_span(lines, role_id)
    item = indent + "  "
    field = item + "  "

    rendered = [
        f"{item}- id: {bullet.id}",
        f"{field}claim: {_quote(bullet.claim)}",
        f"{field}mechanism: {_quote(bullet.mechanism)}",
        f"{field}tags: [{', '.join(_quote(tag) for tag in bullet.tags)}]",
    ]
    if bullet.metric_value:
        rendered += [
            f"{field}metric:",
            f"{field}  verified: true",
            f"{field}  value: {_quote(bullet.metric_value)}",
        ]
    elif bullet.placeholder:
        rendered += [
            f"{field}metric:",
            f"{field}  verified: false",
            f"{field}  placeholder: {_quote(bullet.placeholder)}",
        ]

    empty_list = re.compile(rf"^{re.escape(indent)}bullets:\s*\[\s*\]\s*(#.*)?$")
    for offset in range(_first, last):
        if empty_list.match(lines[offset]):
            lines[offset : offset + 1] = [f"{indent}bullets:", *rendered]
            return "\n".join(lines) + "\n"

    for offset in range(last - 1, _first, -1):
        if re.match(rf"^{re.escape(indent)}bullets:\s*(#.*)?$", lines[offset]):
            insert_at = last
            while insert_at > offset and not lines[insert_at - 1].strip():
                insert_at -= 1
            lines[insert_at:insert_at] = rendered
            return "\n".join(lines) + "\n"

    lines[last:last] = [f"{indent}bullets:", *rendered]
    return "\n".join(lines) + "\n"


def add_tags(text: str, role_id: str, tags: list[str]) -> str:
    """Say what a role was about, so its bullets can be found by a posting."""
    if not tags:
        raise EditError("no tags given")
    lines = text.splitlines()
    first, last, indent = _role_span(lines, role_id)
    rendered = f"{indent}tags: [{', '.join(_quote(tag) for tag in tags)}]"
    for offset in range(first, last):
        if re.match(rf"^{re.escape(indent)}tags:", lines[offset]):
            existing = re.search(r"\[(.*)\]", lines[offset])
            if existing and existing.group(1).strip():
                held = [item.strip().strip("\"'") for item in existing.group(1).split(",")]
                merged = held + [tag for tag in tags if tag not in held]
                rendered = f"{indent}tags: [{', '.join(_quote(tag) for tag in merged)}]"
            lines[offset] = rendered
            return "\n".join(lines) + "\n"
    lines[first + 1 : first + 1] = [rendered]
    return "\n".join(lines) + "\n"


def apply(path: str | Path | None, change) -> str:
    """Run one edit against the corpus file, refusing to save a broken result.

    `change` takes the file's text and returns the new text. It is applied in
    memory and the result is loaded before anything is written, so a rejected
    edit leaves the file exactly as it was rather than half-applied.
    """
    target = resolve_corpus_path(str(path) if path else None)
    if not Path(target).is_file():
        raise EditError(f"no corpus at {target}")
    original = Path(target).read_text(encoding="utf-8")

    updated = change(original)
    try:
        load_corpus_text(updated)
    except CorpusError as exc:
        problems = "; ".join(exc.problems[:3])
        raise EditError(
            f"that change would leave the corpus invalid, so nothing was written: {problems}"
        ) from exc

    Path(target).write_text(updated, encoding="utf-8", newline="\n")
    return updated


def _entry_span(lines: list[str], entry_id: str) -> tuple[int, int, str]:
    """Where any `- id: <entry_id>` block starts and ends, and its key indent."""
    start = None
    indent = ""
    for number, line in enumerate(lines):
        match = re.match(r"^(\s*)-\s+id:\s*(.+?)\s*(#.*)?$", line)
        if match and match.group(2).strip().strip("\"'") == entry_id:
            start, indent = number, match.group(1) + "  "
            break
    if start is None:
        raise EditError(f"no entry with id {entry_id!r} in the corpus")

    for number in range(start + 1, len(lines)):
        line = lines[number]
        if line.strip() and not line.startswith(indent):
            return start, number, indent
        if re.match(rf"^{re.escape(indent)}-\s", line):
            return start, number, indent
    return start, len(lines), indent


def set_metric(text: str, bullet_id: str, value: str) -> str:
    """Promote a bullet's placeholder to a figure the user actually measured.

    The token is replaced INSIDE the claim and mechanism as well as in the
    metric block. The hole is written into the sentence — "cut release prep to
    [N] minutes" — so changing only the metric would leave the CV still printing
    "[N]" while the corpus claimed a number. That divergence is the worst of
    both: an unfilled CV and a corpus that says it is filled.
    """
    if not value.strip():
        raise EditError(
            "a measured figure cannot be blank. If there is no number, keep the "
            "placeholder instead — a visible gap is honest, a blank is not."
        )

    lines = text.splitlines()
    start, end, _indent = _entry_span(lines, bullet_id)
    block = lines[start:end]

    token = None
    for line in block:
        found = re.search(r"placeholder:\s*[\"']?([^\"'\n]+?)[\"']?\s*$", line)
        if found:
            token = found.group(1).strip()
            break
    if token is None:
        raise EditError(f"bullet {bullet_id!r} carries no placeholder to fill")

    rewritten = []
    for line in block:
        if re.match(r"^\s*verified:", line):
            rewritten.append(line.replace("false", "true"))
        elif re.match(r"^\s*placeholder:", line):
            pad = line[: len(line) - len(line.lstrip())]
            rewritten.append(f"{pad}value: {_quote(value)}")
        else:
            rewritten.append(line.replace(token, value))
    lines[start:end] = rewritten
    return "\n".join(lines) + "\n"


__all__ = [
    "EditError",
    "NewBullet",
    "add_bullet",
    "add_tags",
    "apply",
    "set_metric",
    "set_role_dates",
]
