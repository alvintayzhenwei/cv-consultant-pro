"""`cv-tailor validate` — the command CI and a pre-commit hook would call.

The exit code is the contract. A validator that prints a complaint and exits 0
is decoration: it goes green in CI while the corpus is broken, which is the
failure mode this whole guard exists to prevent.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cv_tailor.cli import main

EXAMPLE = Path(__file__).resolve().parents[1] / "career-corpus.example.yaml"

BAD = """
person:
  name: Test Person
roles:
  - id: r1
    org: Acme
    title: Engineer
    start: "2020-01"
    end: present
    bullets:
      - id: fabricated
        claim: Cut cost by 37%
        mechanism: somehow
        tags: [cost]
        metric: {verified: false, value: "37%"}
"""


def test_a_valid_corpus_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["validate", str(EXAMPLE)]) == 0
    assert "valid" in capsys.readouterr().out.lower()


def test_an_invalid_corpus_exits_non_zero_and_names_the_problem(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(BAD, encoding="utf-8")

    assert main(["validate", str(bad)]) == 1

    err = capsys.readouterr().err
    assert "fabricated" in err, "the failure must name the offending bullet"


def test_validation_reports_what_is_still_missing(capsys: pytest.CaptureFixture[str]) -> None:
    """Valid is not the same as complete.

    The example deliberately contains an undated role and two placeholders. A
    validator that stayed silent about those would let an incomplete corpus feel
    finished, which is how a CV ships with a hole in it.
    """
    main(["validate", str(EXAMPLE)])

    out = capsys.readouterr().out
    assert "earlier-agency-work" in out, "an undated role must be reported"
    assert "[X]%" in out or "[N]" in out, "outstanding placeholders must be reported"


def test_a_missing_file_is_an_error_not_a_crash(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["validate", str(tmp_path / "absent.yaml")]) == 1
    assert "example" in capsys.readouterr().err.lower()
