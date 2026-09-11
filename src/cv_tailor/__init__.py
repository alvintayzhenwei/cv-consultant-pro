"""cv-tailor — a job description in, a tailored application kit out.

The package is deliberately split into three layers that never merge:

  engine   this package. Generic. Knows nothing about any particular person.
  corpus   a private YAML file of one person's career evidence. Never committed.
  surface  a Claude Code skill, or any other caller, that points the engine at a corpus.

The separation is what lets the engine be published while the corpus stays on
one machine. Fusing them would produce a tool nobody else can use, holding data
that cannot be shared.

The contract the whole package exists to keep: it SELECTS from the corpus. It
never authors a claim the corpus does not contain, and never invents a figure —
an unverified metric renders as its literal placeholder, and the audit stage
refuses to write output carrying anything untraceable.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
