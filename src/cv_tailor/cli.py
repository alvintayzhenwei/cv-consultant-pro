"""Command line entry point.

Only `validate` for now. It is the command CI runs and the one worth having
before anything else: a corpus that has not been validated is not a corpus the
rest of the pipeline may assume anything about.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from .corpus import CorpusError, load_corpus, resolve_corpus_path


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


def main(argv: Sequence[str] | None = None) -> int:
    _use_utf8_output()
    parser = argparse.ArgumentParser(
        prog="cv-tailor",
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

    args = parser.parse_args(argv)

    if args.command == "validate":
        return _validate(args.path)

    parser.error(f"unknown command: {args.command}")  # pragma: no cover
    return 2  # pragma: no cover


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
