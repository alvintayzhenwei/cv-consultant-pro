## ADDED Requirements

### Requirement: The skill is a thin wrapper over the package
The Claude Code skill SHALL orchestrate the packaged engine and SHALL NOT reimplement
ingestion, matching, rendering or auditing. Any logic usable outside Claude Code SHALL
live in the `cv-consultant-pro` package.

#### Scenario: Engine is usable without the skill
- **WHEN** the package is invoked directly from a terminal with a posting and a corpus path
- **THEN** it produces the full kit without Claude Code present

#### Scenario: Skill contains no engine logic
- **WHEN** the skill files are inspected
- **THEN** they contain instructions and reference material, not a second implementation of any pipeline stage

### Requirement: A run produces a self-contained kit directory
Each run SHALL write its outputs to a directory named for the posting, containing the
scorecard, the gap plan, the CV in Markdown and `.docx`, the interview questions, the
traceability record, the placeholder list, and any suggested corpus entries.

#### Scenario: Outputs are grouped per posting
- **WHEN** the engine is run against Apple requisition 200661514
- **THEN** all outputs for that run land in one directory identified by that requisition

#### Scenario: A second run does not overwrite the first silently
- **WHEN** the engine is run twice against the same posting
- **THEN** the earlier kit is preserved or the user is told it will be replaced

### Requirement: Kit output is never committed
Generated kits SHALL be written to a gitignored location by default, because a kit
contains rendered CVs built from private corpus data and the engine repository is public.

#### Scenario: Generated kits are ignored by git
- **WHEN** a kit directory exists in the working tree
- **THEN** `git status` does not list it as untracked

### Requirement: The skill installs at user level
The skill SHALL be installable outside any single project, so the engine is usable from
whatever repository the user is working in rather than only from the engine's own
checkout.

#### Scenario: Skill is available from an unrelated project
- **WHEN** the skill is installed and the user is working in a different repository
- **THEN** the skill is invocable there
- **AND** it resolves the corpus from the configured path, not from the current project

### Requirement: Research context is encoded, not re-derived
The skill SHALL carry reference material stating the ATS findings the engine depends on,
so that they are applied consistently rather than re-researched per run. It SHALL record
that automatic rejection by applicant tracking systems is largely a myth, that document
parsing is the real hard gate, that both a literal keyword index and a language-model
reader evaluate the document, that keyword stuffing and hidden text are detected and
penalised, that a dedicated skills section is the highest-weighted keyword zone, and that
bullets follow the accomplished-X-as-measured-by-Y-by-doing-Z form.

#### Scenario: Reference material is present and cited
- **WHEN** the skill is loaded
- **THEN** its reference files state these findings with their sources

#### Scenario: Guidance is not silently re-derived
- **WHEN** a run renders a CV
- **THEN** it applies the recorded formatting rules without performing new research

### Requirement: The skill never writes to the corpus
The skill SHALL treat the corpus as read-only. Accepting a suggested entry SHALL be an
explicit, separate user action.

#### Scenario: A run leaves the corpus byte-identical
- **WHEN** the skill completes a run
- **THEN** the corpus file is unchanged
