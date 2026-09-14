## Why

Tailoring a CV to a single job description currently takes a full working session: read the
posting, map it against a career history that lives in several places and nowhere completely,
decide what to cut, rewrite bullets, and hand-check that nothing overstates the truth. That
work was done twice by hand for two Apple requisitions and produced a reusable insight — the
CV is the cheap part, the **corpus** is the asset. What made tailoring possible was having
every role, accomplishment, metric and skill available as separate, selectable evidence;
what made it slow was that no such store exists. `src/data/profile.ts` holds finished
positioning prose, not evidence, and the pre-2025 employment history has no dates recorded
anywhere in the repo.

A second, larger reason: the same pipeline is the first real capability of the Digital Twin.
If the engine is generic and the corpus is private from day one, the engine can later be
published for anyone to use and the twin is simply the engine pointed at one person's corpus.
Fusing them produces neither.

**One existing store is already in play.** `src/data/interview.ts` holds twenty-one
first-person answers to senior AI-engineering interview questions, grouped by topic and
injected into the Digital Twin's chat system prompt on every request. It is evidence-shaped
and already wired into the twin, so the corpus must reconcile with it rather than duplicate
or contradict it.

## What Changes

- **New standalone `cv-consultant-pro` repository** — a self-contained, later-publishable Python
  engine with its own `pyproject.toml`, `src/` layout, `tests/` and CI. It is **not**
  published to PyPI by this change. It deliberately does **not** live as a sibling directory
  in this repository: `.github/workflows/ci.yml` records that the existing standalone
  packages (`a2a-mcp-connector`, `a2a-raid-mcp`) are on their way *out* of this repo and that
  their CI belongs in their own repositories. Adding a fourth would add to a pile being
  cleared.
- **New private career corpus** — a YAML evidence store (roles, bullets with stable ids and
  verified/unverified metrics, skills with aliases, education, certifications, artifacts),
  seeded from the user's LinkedIn data export for accurate employment dates. The real file is
  gitignored at a configurable path; a committed `career-corpus.example.yaml` carries the
  schema with fictional data and is what CI validates.
- **New corpus validator** — asserts every bullet has an id and tags, and that every metric is
  either `verified: true` with a value or `verified: false` with a placeholder. Critically, it
  fails the build if an unverified metric carries a concrete number, turning the
  anti-fabrication rule into a build failure rather than a prompt instruction.
- **New six-stage pipeline** — `fetch_jd` → `extract_requirements` → `match` → `select` →
  `render` → `audit`. JD URLs resolve to structured requirements (Apple's posting pages are
  JS-rendered; `jobs.apple.com/api/v1/jobDetails/<id>` returns clean JSON), with pasted text
  as the fallback for any other source.
- **New application kit output** — per JD: a match scorecard (strong / partial / gap per
  requirement, with the corpus evidence backing each), a tailored one-page CV in Markdown
  **and** as a generated `.docx` with ATS-safe formatting enforced in code, a ranked gap and
  improvement plan, and approximately twenty likely interview questions anchored to corpus
  evidence.
- **New select-only rendering contract** — the engine may select, compress, re-order and
  substitute a JD's exact vocabulary via skill aliases already declared in the corpus. It may
  never author a claim absent from the corpus and never invent a figure; an unverified metric
  renders as its literal placeholder (`[X]`, `[N]`). Where a JD asks for evidence the corpus
  lacks, the engine writes **suggested** corpus entries to a separate file for the user to
  verify and accept — suggestions never render into a CV.
- **New Claude Code skill** — a thin orchestration wrapper over the package, plus reference
  files encoding the ATS research so it is not re-derived on every run. It ships **in the
  engine repository** and is installed at user level, so the tool works from any project
  rather than only from this one.
- **English rendering only**, with a `language` field in the corpus schema so other languages
  are a later data addition rather than a refactor.
- **Documentation sync** — `README.md` and `.claude/CLAUDE.md` gain the package and the skill.

## Capabilities

### New Capabilities
- `career-corpus`: the private, structured evidence store — schema, the gitignored/example
  file split, LinkedIn-export seeding, reconciliation with the existing first-person
  positions in `src/data/interview.ts`, and the validator that enforces the
  verified/placeholder metric rule.
- `jd-ingestion`: resolving a job posting (URL or pasted text) into structured requirements,
  separating minimum from preferred, capturing the posting's exact vocabulary, and flagging
  hard filters such as language, location and years of experience.
- `jd-corpus-matching`: scoring corpus evidence against extracted requirements and emitting
  the match scorecard and the ranked gap plan.
- `application-kit-rendering`: one-page selection, ATS-safe Markdown and `.docx` rendering,
  interview-question generation, and the audit gate that refuses any untraceable claim.
- `cv-consultant-pro-skill`: the Claude Code invocation surface — inputs accepted, output directory
  layout, and the encoded ATS reference material.

### Modified Capabilities
None. No existing spec's requirements change. `src/data/profile.ts` is explicitly **not**
replaced or generated by the corpus; positioning copy and evidence remain separate concerns.

## Impact

**New code — all of it in the new `cv-consultant-pro` repository**
- `pyproject.toml`, `src/cv_consultant_pro/`, `tests/`, CI. Dependencies: `PyYAML`, `python-docx`,
  `httpx`.
- `skills/cv-consultant-pro/` — `SKILL.md` plus reference files, installed at user level.
- `career-corpus.example.yaml` (committed, fictional data); `career-corpus.yaml`
  (gitignored).

**This repository**
- **No code changes.** Nothing in `src/`, `worker/`, `migrations/`, `wrangler.toml`,
  `.github/` or `.claude/skills/`. The live site, the Worker routes and the deploy pipeline
  are untouched.
- This repository's only role is as the origin of the corpus seed data
  (`src/data/profile.ts`, `src/data/interview.ts`, `src/data/lab.ts`) and as the home of
  these planning artifacts. Once the engine repository exists, these artifacts should move
  there — see *Open Questions* in `design.md`.

**Owner action required**
- Creating the `cv-consultant-pro` repository is an owner step. Implementation cannot begin in it
  until it exists.

**Data and privacy**
- The real corpus holds team sizes, client names, internal project names and unverified
  metrics. It must never be committed to this public repository. The committed example
  contains fictional data only.

**Verification**
- `tests/` in the engine repository run under `pytest`, on that repository's own CI. The
  corpus validator is the load-bearing test.
- Acceptance: pointed at Apple requisitions 200645480 (Software Engineer, Generative AI & ML)
  and 200661514 (Engineering Product Manager, Singapore), the engine must produce scorecards
  and CVs at least as good as the two hand-written CVs produced during the originating
  session, judged by the user.

**Blocking input**
- The user's LinkedIn data export is required to seed accurate employment dates for Hogarth
  Worldwide, Patroids Creative Works and 365 Solutions. The schema, validator, pipeline and
  skill can all be built before it arrives; only corpus population is blocked.
