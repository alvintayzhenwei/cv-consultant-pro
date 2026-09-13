"""The career corpus: evidence in, validated structure out."""

from .dates import YearMonth, parse_date
from .loader import (
    ENV_VAR,
    CorpusError,
    load_corpus,
    load_corpus_text,
    resolve_corpus_path,
)
from .models import (
    Artifact,
    Bullet,
    Certification,
    Corpus,
    Education,
    Metric,
    Person,
    Position,
    Role,
    Skill,
    Summary,
    Todo,
)

__all__ = [
    "ENV_VAR",
    "Artifact",
    "Bullet",
    "Certification",
    "Corpus",
    "CorpusError",
    "Education",
    "Metric",
    "Person",
    "Position",
    "Role",
    "Skill",
    "Summary",
    "Todo",
    "YearMonth",
    "load_corpus",
    "load_corpus_text",
    "parse_date",
    "resolve_corpus_path",
]
