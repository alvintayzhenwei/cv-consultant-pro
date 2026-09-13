"""Command line entry point.

    cv-consultant-pro validate [corpus]        check a career corpus
    cv-consultant-pro templates                list the CV layouts
    cv-consultant-pro tailor <jd> [--template] build an application kit
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from .corpus import CorpusError, load_corpus, resolve_corpus_path
from .docx import write_docx
from .jd import Tier, parse_jd
from .match import Verdict, score
from .render import AuditError, render, select
from .templates import TEMPLATES, get_template, render_html


def _use_utf8_output() -> None:
    """Make non-ASCII output survive a default Windows console.

    Error messages carry typographic characters, and a cp1252 console renders
    them as replacement junk — which is worst precisely where it matters, in the
    message explaining why a corpus was refused. Guarded, because a stream that
    cannot be reconfigured (a pipe, a captured buffer under pytest) must not
    take the command down.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError, OSError):
            pass


def _validate(path: str | None) -> int:
    resolved = resolve_corpus_path(path)
    try:
        corpus = load_corpus(resolved)
    except CorpusError as exc:
        print(f"{resolved}", file=sys.stderr)
        for problem in exc.problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    bullets = corpus.all_bullets()
    print(f"{resolved}")
    print(
        f"  valid: {len(corpus.roles)} roles, {len(bullets)} bullets, "
        f"{len(corpus.skills)} skills, {len(corpus.positions)} positions"
    )

    # Valid is not complete. Reporting the gaps is the difference between a
    # corpus that is finished and one that merely parses.
    todos = corpus.todos()
    if todos:
        print(f"\n  {len(todos)} thing(s) still to fill in:")
        for todo in todos:
            print(f"    - {todo.ref}: {todo.what}")
    else:
        print("\n  nothing outstanding.")

    return 0


_CHIP = {Verdict.STRONG: "STRONG ", Verdict.PARTIAL: "PARTIAL", Verdict.GAP: "GAP    "}


def _templates() -> int:
    print("Available layouts:")
    print()
    for tpl in TEMPLATES.values():
        flag = "portal-safe" if tpl.ats_safe else "HUMAN CHANNEL ONLY"
        print(f"  {tpl.id:<9} {tpl.name:<9} [{flag}]")
        print(f"  {'':<9} {tpl.blurb}")
        print()
    print("  A portal-safe layout is single column with no sidebar, icons or images:")
    print("  submit those. The others look better by doing what a parser mishandles,")
    print("  so send them to a person directly. No layout carries a photograph.")
    return 0


def _tailor(
    jd_path: str,
    corpus_path: str | None,
    out_dir: str,
    title: str | None,
    template_id: str | None,
) -> int:
    try:
        corpus = load_corpus(resolve_corpus_path(corpus_path))
    except CorpusError as exc:
        for problem in exc.problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    jd = parse_jd(Path(jd_path).read_text(encoding="utf-8"), title=title)
    if not jd.requirements:
        print(f"no requirements found in {jd_path}", file=sys.stderr)
        print(
            "  the parser reads a posting's own headings (Minimum qualifications, "
            "Preferred qualifications, Responsibilities). Check they survived the copy.",
            file=sys.stderr,
        )
        return 1

    card = score(jd, corpus)
    selection = select(corpus, card)

    try:
        kit = render(corpus, jd, card, selection)
    except AuditError as exc:
        print(f"audit refused to write output: {exc}", file=sys.stderr)
        return 1

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    template = get_template(template_id)

    (out / "cv.md").write_text(kit.markdown, encoding="utf-8")
    write_docx(kit.document, out / "cv.docx")
    (out / "cv.html").write_text(render_html(kit.document, template), encoding="utf-8")

    lines = ["# Match scorecard", ""]
    if card.hard_filters:
        lines += ["## Hard filters", "", "Failing one of these disqualifies regardless of the",
                  "rest of the match, so they are reported apart from the scored rows.", ""]
        for row in card.hard_filters:
            lines.append(f"- **{row.requirement.text}**")
            if row.requirement.years_required:
                span = row.evidenced_years
                lines.append(
                    f"  - threshold {row.requirement.years_required} years; corpus evidences "
                    + (f"{span} years across tagged roles (union of spans)" if span else "no tagged span")
                )
            if row.evidence_ids:
                lines.append(f"  - evidence: {', '.join(row.evidence_ids)}")
        lines.append("")

    for tier in (Tier.MINIMUM, Tier.PREFERRED, Tier.RESPONSIBILITY):
        rows = [r for r in card.rows if r.requirement.tier is tier]
        if not rows:
            continue
        lines += [f"## {tier.value.title()}", ""]
        for row in rows:
            lines.append(f"- `{_CHIP[row.verdict].strip()}` {row.requirement.text}")
            if row.evidence_ids:
                lines.append(f"  - evidence: {', '.join(row.evidence_ids)}")
            if row.note:
                lines.append(f"  - note: {row.note}")
        lines.append("")
    (out / "scorecard.md").write_text("\n".join(lines), encoding="utf-8")

    gaps = [r for r in card.rows if r.verdict is Verdict.GAP]
    gap_lines = ["# Gaps", ""]
    for row in card.hard_filters:
        gap_lines.append(f"- **HARD FILTER** {row.requirement.text}")
    for row in gaps:
        gap_lines.append(f"- ({row.requirement.tier.value}) {row.requirement.text}")
    (out / "gaps.md").write_text("\n".join(gap_lines) + "\n", encoding="utf-8")

    trace_lines = ["# Traceability", "", "Every rendered bullet, and the corpus entry it came from.", ""]
    trace_lines += [f"- `{bid}` -> {claim}" for bid, claim in kit.traceability]
    (out / "traceability.md").write_text("\n".join(trace_lines) + "\n", encoding="utf-8")

    ph_lines = ["# Placeholders to fill", ""]
    ph_lines += [f"- `{bid}`: {holder}" for bid, holder in kit.placeholders] or ["None."]
    (out / "placeholders.md").write_text("\n".join(ph_lines) + "\n", encoding="utf-8")

    strong = len(card.by_verdict(Verdict.STRONG))
    partial = len(card.by_verdict(Verdict.PARTIAL))
    gap = len(gaps)
    print(f"{out}")
    print(f"  {strong} strong, {partial} partial, {gap} gap, {len(card.hard_filters)} hard filter(s)")
    print(f"  CV: {len(selection.roles)} roles, {len(selection.bullet_ids())} bullets, "
          f"~{selection.estimated_lines} body lines")
    if selection.dropped_roles:
        print(f"  dropped: {', '.join(selection.dropped_roles)}")
    if kit.placeholders:
        print(f"  {len(kit.placeholders)} placeholder(s) still to fill")

    channel = "portal-safe" if template.ats_safe else "HUMAN CHANNEL ONLY"
    print(f"  layout: {template.name} ({channel})")
    if not template.ats_safe:
        print("    cv.html uses a layout a parser mishandles. Submit cv.docx through a")
        print("    portal; send cv.html, printed to PDF, to a person directly.")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    _use_utf8_output()
    parser = argparse.ArgumentParser(
        prog="cv-consultant-pro",
        description="Turn a job description into a tailored application kit.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="check a career corpus")
    validate.add_argument(
        "path",
        nargs="?",
        default=None,
        help="corpus file (default: $CV_TAILOR_CORPUS, else ./career-corpus.yaml)",
    )

    tailor = sub.add_parser("tailor", help="build an application kit from a job posting")
    tailor.add_argument("jd", help="a text file containing the job posting")
    tailor.add_argument("--corpus", default=None, help="corpus file (default: as for validate)")
    tailor.add_argument("--out", default="kits/latest", help="output directory")
    tailor.add_argument("--title", default=None, help="role title for the CV heading")
    tailor.add_argument(
        "--template",
        default=None,
        choices=sorted(TEMPLATES),
        help="HTML layout for cv.html (default: signal). See the templates command.",
    )

    sub.add_parser("templates", help="list the available CV layouts")

    args = parser.parse_args(argv)

    if args.command == "validate":
        return _validate(args.path)

    if args.command == "templates":
        return _templates()

    if args.command == "tailor":
        return _tailor(args.jd, args.corpus, args.out, args.title, args.template)

    parser.error(f"unknown command: {args.command}")  # pragma: no cover
    return 2  # pragma: no cover


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
