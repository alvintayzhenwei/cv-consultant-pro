## ADDED Requirements

### Requirement: Every requirement is scored against corpus evidence
The engine SHALL score each extracted requirement against the corpus and SHALL assign
exactly one verdict from `strong`, `partial` or `gap`. Every `strong` or `partial`
verdict MUST name the corpus entry ids that support it. A `gap` verdict MUST name no
supporting evidence.

#### Scenario: Supported requirement cites its evidence
- **WHEN** a requirement asks for hands-on React experience and the corpus holds a bullet tagged `react`
- **THEN** the verdict is `strong` or `partial`
- **AND** the scorecard row names the supporting bullet ids

#### Scenario: Unsupported requirement is an honest gap
- **WHEN** a requirement asks for experience the corpus holds no evidence for
- **THEN** the verdict is `gap`
- **AND** no corpus entry is cited for it

#### Scenario: Every requirement appears exactly once
- **WHEN** the scorecard is produced for a posting with N extracted requirements
- **THEN** the scorecard contains exactly N scored rows plus any hard-filter rows

### Requirement: Hard filters are reported, not scored away
A requirement flagged as a hard filter SHALL be reported with its own status and SHALL
NOT be averaged into any overall match figure, because failing one is disqualifying
rather than merely lowering a score.

#### Scenario: Unmet hard filter is stated plainly
- **WHEN** a posting requires a language fluency the corpus does not evidence
- **THEN** the scorecard reports it as an unmet hard filter
- **AND** the report states that it may disqualify the application regardless of other matches

#### Scenario: Years threshold is compared against corpus dates
- **WHEN** a posting requires a minimum number of years in a discipline
- **THEN** the engine computes the evidenced span from role dates and tags
- **AND** reports the computed figure alongside the threshold rather than asserting a pass

### Requirement: A ranked gap plan accompanies the scorecard
The engine SHALL produce a gap plan ordering unmet requirements by how much closing each
would improve the application, and SHALL state for each what evidence would close it.

#### Scenario: Gaps are ordered, not merely listed
- **WHEN** a posting yields several `gap` verdicts including one unmet hard filter
- **THEN** the unmet hard filter is ranked above scored gaps

#### Scenario: Each gap names its closing evidence
- **WHEN** the plan lists a gap
- **THEN** it states the concrete artifact or experience that would turn it into evidence

### Requirement: Missing evidence produces suggested corpus entries
Where a requirement scores `gap` or `partial`, the engine SHALL write a suggested corpus
entry to a separate suggestions file for the user to verify and accept. Suggestions
SHALL NOT be readable by the rendering stage.

#### Scenario: Suggestions are written outside the corpus
- **WHEN** a run produces suggestions
- **THEN** they are written to a suggestions file, not merged into the corpus
- **AND** the corpus file is unchanged by the run

#### Scenario: A suggestion can never reach a CV
- **WHEN** a suggestions file exists alongside a corpus
- **THEN** rendering draws only on the corpus
- **AND** no suggested claim appears in any rendered output
