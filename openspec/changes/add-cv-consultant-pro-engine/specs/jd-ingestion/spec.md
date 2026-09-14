## ADDED Requirements

### Requirement: A job posting resolves to structured requirements
The engine SHALL accept a job posting as either a URL or pasted text and SHALL produce a
structured record containing the role title, organisation, location, posting date where
available, and the posting's requirements as discrete items.

#### Scenario: Pasted text is always accepted
- **WHEN** a posting is supplied as raw text
- **THEN** ingestion succeeds without any network access

#### Scenario: Unreachable URL degrades to a clear error
- **WHEN** a URL cannot be fetched or yields no recognisable posting content
- **THEN** the engine reports that it could not read the posting and names pasted text as the fallback
- **AND** it does not fabricate requirements

### Requirement: JS-rendered postings are resolved through a known data source
Where a posting page renders its content client-side, the engine SHALL use a registered
structured source for that host rather than scraping the rendered shell. Apple postings
SHALL resolve through `jobs.apple.com/api/v1/jobDetails/<id>`.

#### Scenario: Apple requisition resolves to full text
- **WHEN** the URL `https://jobs.apple.com/en-us/details/200661514/...` is ingested
- **THEN** the record contains the summary, description, minimum qualifications and preferred qualifications
- **AND** the requisition id `200661514` is captured as the record identifier

#### Scenario: Unknown host falls back rather than failing
- **WHEN** a posting URL belongs to a host with no registered structured source
- **THEN** the engine attempts a generic text extraction
- **AND** reports low confidence if the result is too short to contain qualifications

### Requirement: Minimum and preferred requirements are separated
Extracted requirements SHALL be classified as `minimum` or `preferred` where the posting
distinguishes them, and SHALL retain the posting's own wording verbatim alongside any
normalised form.

#### Scenario: Classification follows the posting's own headings
- **WHEN** a posting carries distinct "Minimum Qualifications" and "Preferred Qualifications" sections
- **THEN** each extracted requirement is tagged with the section it came from

#### Scenario: Exact vocabulary is preserved
- **WHEN** a posting says "robotic process automation tools such as n8n"
- **THEN** the stored requirement retains that exact phrasing for later reuse in rendering

### Requirement: Hard filters are flagged separately
The engine SHALL identify requirements that act as eligibility filters rather than
scored criteria — language fluency, work location, citizenship or clearance, and minimum
years of experience — and SHALL surface them distinctly.

#### Scenario: Language fluency is flagged
- **WHEN** a posting lists fluency in a language among its minimum qualifications
- **THEN** that requirement is marked as a hard filter
- **AND** the scorecard reports it separately from scored requirements

#### Scenario: Years of experience is flagged with its threshold
- **WHEN** a posting requires "Minimum 5 years of experience in technical program management"
- **THEN** the requirement is marked as a hard filter carrying the threshold `5`
