## ADDED Requirements

### Requirement: Corpus holds evidence as addressable entries
The corpus SHALL store career history as individually addressable entries rather than
prose. Each role SHALL carry a stable `id`, `org`, `title`, optional `title_framings`,
and `start`/`end` dates in `MM/YYYY` form (`end` MAY be `present`). Each accomplishment
SHALL be a `bullet` carrying a stable `id`, a `claim`, a `mechanism`, and at least one
`tag`. Skills SHALL carry a `name`, optional `aliases`, and `evidence_refs` naming the
bullet ids that substantiate them.

#### Scenario: Every bullet is addressable
- **WHEN** the corpus is loaded
- **THEN** every bullet has a non-empty `id` unique within the corpus
- **AND** every bullet has at least one tag

#### Scenario: Dates are machine-comparable
- **WHEN** a role declares `start: 2026-01` and `end: present`
- **THEN** the loader resolves it to a comparable range without ambiguity
- **AND** a role whose dates are unknown is retained with an explicit `TODO` marker rather than being silently omitted

### Requirement: Metrics are explicitly verified or explicitly placeholder
Every `metric` on a bullet SHALL declare `verified` as a boolean. A metric with
`verified: true` MUST carry a concrete `value`. A metric with `verified: false` MUST
carry a `placeholder` string and MUST NOT carry a concrete numeric value.

#### Scenario: Unverified metric carrying a number is rejected
- **WHEN** the corpus declares a metric with `verified: false` and a `value` of `"37%"`
- **THEN** the validator fails with an error naming the offending bullet id
- **AND** the failure is a non-zero exit code so it breaks a build

#### Scenario: Verified metric without a value is rejected
- **WHEN** the corpus declares a metric with `verified: true` and no `value`
- **THEN** the validator fails with an error naming the offending bullet id

#### Scenario: Well-formed metrics pass
- **WHEN** every metric is either verified-with-a-value or unverified-with-a-placeholder
- **THEN** the validator exits zero

### Requirement: The real corpus is never committed
The engine SHALL read the corpus from a configurable path defaulting to
`career-corpus.yaml` at the repository root. That path SHALL be gitignored. A
`career-corpus.example.yaml` containing the full schema and fictional data only SHALL be
committed and SHALL be the file continuous integration validates. The engine repository
is **public**, so this separation is a disclosure boundary rather than a matter of
tidiness: the corpus carries team sizes, client names, internal project names and
unverified figures.

#### Scenario: Example file is schema-complete
- **WHEN** the validator runs against `career-corpus.example.yaml`
- **THEN** it exits zero
- **AND** the example exercises every schema field, including at least one unverified metric

#### Scenario: Real corpus is ignored by git
- **WHEN** `career-corpus.yaml` exists in the working tree
- **THEN** `git status` does not list it as untracked or modified

#### Scenario: Corpus path is configurable
- **WHEN** a corpus path is supplied explicitly by argument or environment variable
- **THEN** the engine reads that file instead of the default location

### Requirement: Corpus is seeded from a LinkedIn data export
The engine SHALL provide a one-time seeding path that reads a LinkedIn data export and
produces a corpus draft with employment dates, organisations and titles populated.
Generated bullets SHALL default to `verified: false` with placeholders, because an
export carries descriptions rather than verified outcomes.

#### Scenario: Export supplies missing dates
- **WHEN** seeding runs against an export containing a position at Hogarth Worldwide
- **THEN** the drafted role carries that position's real `start` and `end` in `MM/YYYY` form

#### Scenario: Seeded metrics are never presumed verified
- **WHEN** seeding produces a bullet from an export description containing a number
- **THEN** that bullet's metric is marked `verified: false` with a placeholder
- **AND** the drafted corpus passes the validator unchanged

### Requirement: Interview positions are a distinct entry kind
The corpus SHALL hold the user's worked answers to interview questions as `positions`,
separate from `bullets`. A position is a stated view on a topic; a bullet is a dated,
attributable accomplishment. The corpus SHALL NOT flatten one into the other.

#### Scenario: A position is not treated as evidence of an accomplishment
- **WHEN** the corpus holds a position on controlling LLM cost but no bullet evidencing it
- **THEN** matching may cite the position as a prepared answer
- **AND** it does not count as evidence for a requirement asking for delivered work

#### Scenario: Positions import without duplicating an existing source
- **WHEN** positions are seeded from an existing first-person answer set
- **THEN** each imported position records the source it came from
- **AND** re-running the import does not create duplicate positions

### Requirement: The example corpus contains no real personal data
The committed example SHALL contain fictional organisations, names, dates and figures
only, and SHALL NOT be derived by redacting the real corpus.

#### Scenario: Example carries no real employer
- **WHEN** the committed example is inspected
- **THEN** it names no organisation the user has actually worked for

### Requirement: Corpus carries a language field
Every renderable text field SHALL be addressable by language, with `en` as the default,
so that additional languages are a data addition rather than a schema change.

#### Scenario: Default language resolves without annotation
- **WHEN** a bullet declares no language
- **THEN** it is treated as `en`
