"""Month-precision dates.

A career is recorded to the month, never the day — nobody's CV says 14/03/2019 —
so a full `date` would be false precision that then has to be invented at parse
time. `YearMonth` is the whole model.

Two sentinel strings are accepted where a date would go:

  present   the role is ongoing
  TODO      the date is genuinely unknown and must be filled in

`TODO` exists because the alternative is worse. The corpus this package was
built for was seeded from data that recorded six years of highly relevant work
with no dates at all; refusing to load such a role would have thrown the history
away, and inventing a date would have been a lie. So it loads, and says so.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_YM = re.compile(r"\A(\d{4})-(\d{2})\Z")

PRESENT = "present"
TODO = "todo"


@dataclass(frozen=True, order=True)
class YearMonth:
    year: int
    month: int

    def __post_init__(self) -> None:
        if not 1 <= self.month <= 12:
            raise ValueError(f"month out of range: {self.month}")

    def render(self) -> str:
        """MM/YYYY — the form both résumé parsers and readers expect."""
        return f"{self.month:02d}/{self.year}"

    def as_yaml(self) -> str:
        """YYYY-MM - the form the corpus FILE uses, which is not the rendered one.

        Storage is ISO-ordered so dates sort and read unambiguously; display is
        MM/YYYY because that is what a CV prints. Writing a generated corpus with
        render() produced a file the validator rejected on every single role.
        """
        return f"{self.year}-{self.month:02d}"

    def __str__(self) -> str:  # pragma: no cover - convenience only
        return self.render()


@dataclass(frozen=True)
class ParsedDate:
    """The result of reading one date field: a value, or a reason there isn't one."""

    value: YearMonth | None
    is_present: bool = False
    is_todo: bool = False


def parse_date(raw: object, *, field: str) -> ParsedDate:
    """Parse a corpus date field.

    Raises ValueError with a message naming the field, so the caller can attach
    the entry id and produce an error a human can act on.
    """
    if raw is None:
        return ParsedDate(value=None, is_todo=True)

    text = str(raw).strip()
    lowered = text.lower()

    if lowered == PRESENT:
        return ParsedDate(value=None, is_present=True)
    if lowered == TODO:
        return ParsedDate(value=None, is_todo=True)

    match = _YM.match(text)
    if not match:
        raise ValueError(
            f"{field}: expected YYYY-MM (quoted, e.g. \"2019-06\"), 'present' or 'TODO', "
            f"got {text!r}"
        )

    year, month = int(match.group(1)), int(match.group(2))
    try:
        return ParsedDate(value=YearMonth(year, month))
    except ValueError as exc:
        raise ValueError(f"{field}: {exc}") from exc
