## ADDED Requirements

### Requirement: Rendering is select-only
The renderer SHALL select, compress, re-order and re-word corpus entries, and MAY
substitute a posting's exact vocabulary where the corpus declares that wording as a skill
alias. It SHALL NOT author any claim absent from the corpus, and SHALL NOT introduce a
skill the corpus does not hold.

#### Scenario: Vocabulary substitution requires a declared alias
- **WHEN** a posting says "ML engineer" and the corpus declares that phrasing as an alias of a held skill
- **THEN** the rendered CV may use the posting's phrasing

#### Scenario: Undeclared vocabulary is not adopted
- **WHEN** a posting names a technology the corpus does not hold under any alias
- **THEN** that technology does not appear anywhere in the rendered CV

### Requirement: Unverified metrics render as placeholders
The renderer SHALL emit a metric's literal placeholder wherever the underlying metric is
unverified, and SHALL NOT substitute an estimated, rounded or inferred figure.

#### Scenario: Placeholder survives to the output
- **WHEN** a selected bullet carries an unverified metric with placeholder `[X]%`
- **THEN** the rendered CV contains `[X]%` at that position

#### Scenario: Placeholders are collected for the user
- **WHEN** a CV is rendered containing placeholders
- **THEN** the kit lists every placeholder and the bullet it belongs to, so the user knows what to fill

### Requirement: The audit gate blocks untraceable output
Before any output is written, the engine SHALL verify that every claim in the rendered
CV traces to a corpus entry id, and SHALL refuse to write output that fails this check.

#### Scenario: Untraceable sentence blocks the write
- **WHEN** a rendered CV contains a claim that traces to no corpus entry
- **THEN** the engine writes no CV file
- **AND** reports the offending sentence

#### Scenario: Clean render produces a traceability record
- **WHEN** a CV passes the audit
- **THEN** the kit includes a mapping from each rendered bullet to its corpus entry id

### Requirement: Output is ATS-safe by construction
The engine SHALL emit the CV as Markdown and as a `.docx` whose formatting is produced in
code: a single column with no tables, text boxes, headers, footers, images or icons; a
standard system font; standard section headings; and `MM/YYYY` dates. The `.docx` text
SHALL be extractable as a plain reading order matching the visual order.

#### Scenario: Generated document has no multi-column or table structures
- **WHEN** a `.docx` is generated
- **THEN** it contains no table, text box, header, footer or image elements

#### Scenario: Extracted text order matches visual order
- **WHEN** text is extracted from the generated `.docx`
- **THEN** the sequence of sections matches the order a reader sees

#### Scenario: Dates render in the required form
- **WHEN** a role spans January 2025 to the present
- **THEN** the rendered CV shows `01/2025 - Present`

### Requirement: The CV fits one page
Selection SHALL fit the CV to a single page, demoting or dropping whole roles and bullets
by relevance to the posting rather than truncating text mid-entry.

#### Scenario: Least relevant roles are dropped whole
- **WHEN** the corpus holds more roles than fit one page
- **THEN** the least relevant roles are omitted or reduced to a single summary line
- **AND** no retained bullet is cut mid-sentence

#### Scenario: The skills section reflects the posting
- **WHEN** a CV is rendered for a posting
- **THEN** the skills section leads with corpus skills matching that posting's requirements

### Requirement: The kit includes interview questions anchored to evidence
The engine SHALL produce approximately twenty likely interview questions derived from the
posting's requirements and the scorecard, weighted toward `gap` and `partial` verdicts,
each annotated with what it probes and, where one exists, the corpus evidence to answer
from.

#### Scenario: Questions concentrate on weaknesses
- **WHEN** a scorecard contains both `strong` and `gap` verdicts
- **THEN** the question set includes at least one question per `gap`

#### Scenario: Questions cite the user's own evidence where it exists
- **WHEN** a question maps to a requirement scored `strong`
- **THEN** it names the corpus entry the user should answer from

#### Scenario: Prepared ground is distinguished from unprepared ground
- **WHEN** a generated question matches a topic the corpus holds a `position` on
- **THEN** the question is marked as one the user already has a worked answer for
- **AND** questions with no matching position are marked as needing preparation
