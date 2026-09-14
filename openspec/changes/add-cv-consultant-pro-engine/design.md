## Context

Two CVs were hand-written in one session against two Apple requisitions. The exercise
produced the architecture rather than the other way round: tailoring worked because every
accomplishment could be treated as separate, selectable evidence, and it was slow because
no such store existed. `src/data/profile.ts` holds finished positioning prose — the wrong
shape to select from — and employment dates before 2025 are recorded nowhere in the repo.

Nine requirements were settled with the user before this design. The two that shape
everything: the engine must be generic and the corpus private, because the same pipeline
is intended to become a Digital Twin capability later; and the engine must never author a
claim or invent a figure, because a CV that overstates survives the screen and then
collapses in the interview.

Two facts about the current tree were discovered only after syncing this branch with
`origin/main`, which it was 87 commits behind. Both changed decisions that had already been
made:

1. **`src/data/interview.ts` exists** — twenty-one first-person answers to senior
   AI-engineering interview questions, grouped by topic, injected into the Digital Twin's
   chat system prompt on every request, with a test that fails the build on a third-person
   reference. The corpus is not being built into a vacuum.
2. **The sibling-package precedent is being retired.** `.github/workflows/ci.yml` states
   that `a2a-mcp-connector` and `a2a-raid-mcp` "are on their way OUT of this repo" and that
   "their CI belongs in their own repositories". An earlier draft of this design cited those
   packages as the precedent for adding a third. That precedent no longer holds.

## Goals / Non-Goals

**Goals:**
- Three separable layers — generic **engine**, private **corpus**, and a **skill** surface —
  such that publishing the engine later requires no restructuring.
- Make the anti-fabrication rule mechanical: a build failure, not a prompt instruction.
- Produce a complete application kit per posting: scorecard, CV (Markdown and `.docx`),
  ranked gap plan, and interview questions.
- Enforce ATS-safe document formatting in code, removing the manual reformat step where
  parsing problems are actually introduced.
- Recover accurate employment history from the user's LinkedIn export.

**Non-Goals:**
- Publishing to PyPI. The package is structured to be publishable; publishing is a separate,
  owner-only step.
- Any change to `src/`, `worker/`, the live site or the deploy pipeline.
- Replacing or generating `src/data/profile.ts`.
- Non-English rendering. The schema admits it; no renderer is built for it here.
- Cover letters and outreach messages. Different writing problem, separate renderer.
- A hosted or public surface. That is the later Digital Twin work this design keeps possible.

## Decisions

### Corpus as structured evidence, not prose
Each accomplishment is a `bullet` with a stable `id`, a `claim`, a `mechanism`, `tags`, and a
`metric` object. Selection, matching, traceability and auditing all address bullets by id.

*Alternative considered:* generate the corpus from `profile.ts`. Rejected — prose cannot be
selected from, has no per-claim provenance, and carries no verified/unverified distinction.

*Alternative considered:* make the corpus the single source of truth and generate
`profile.ts` from it. Rejected — the corpus is gitignored, so a generated `profile.ts` would
break the build for any public clone, and it couples private data to the public site.

### `verified` is a required field, and the validator is the enforcement
A metric is `verified: true` with a concrete `value`, or `verified: false` with a
`placeholder` and no numeric value. The validator fails non-zero on any violation.

This is the load-bearing decision. Prompt instructions not to invent numbers are advisory;
a failing build is not. It also makes the rule survive a future change of model or surface.

*Alternative considered:* trust the rendering prompt. Rejected — the single failure mode that
matters most cannot be left to an instruction the renderer may drift from.

### Select-only rendering, with aliases as the vocabulary bridge
The renderer may re-word, compress and re-order, and may adopt a posting's exact phrasing
only where the corpus already declares it as an alias of a held skill. This resolves the
tension the research surfaced — a literal keyword index wants the posting's words, while a
language-model reader and any interviewer want true sentences.

*Alternative considered:* allow inference of adjacent claims (from "built a gateway with
bearer auth" infer "API security experience"). Rejected by the user — maximum keyword
coverage at the cost of sentences that must then be defended in a room.

### Suggestions are written outside the corpus and are invisible to rendering
Where a posting wants evidence the corpus lacks, the engine drafts a suggested entry to a
separate file. The rendering stage reads only the corpus. This gives a learning loop — the
corpus improves with each application — without creating a path by which an unverified
suggestion could reach a CV.

### `.docx` generated in code, not hand-formatted
`python-docx` emits a single-column document with no tables, text boxes, headers, footers or
images, standard headings, a system font, and `MM/YYYY` dates. Research put parsing as the
only true hard gate, and a manual reformat into Word is precisely where that gate gets
failed. `.docx` is chosen over PDF as the primary artifact because it parses more reliably.

*Alternative considered:* Markdown only, with an export checklist. Rejected — it reintroduces
the manual step whose elimination is the point.

*Alternative considered:* also emit PDF. Deferred — meaningfully more dependency weight for a
format that parses slightly less reliably. Revisit if a portal demands it.

### A standalone repository, not a sibling directory
The engine gets its own repository with its own CI. This follows where the site repository is
actually going rather than where it has been: it is already moving standalone published
packages out, on the stated grounds that gating the site's CI on code that is leaving creates
churn. Adding a fourth sibling would mean writing something already scheduled for extraction.

The consequence is that this change has **no code footprint in the site repository at all**.
The skill ships with the engine and installs at user level, so the tool is available from any
project rather than only from the site.

*Alternative considered:* a sibling directory inside the site repo, extracted later. Rejected once the
CI comment surfaced — the extraction cost is the same whenever it is paid, and paying it later
means paying it after the corpus and kit paths have grown site-repo-shaped assumptions.

### Python, because `python-docx` decides it
`python-docx` is the reason the engine is Python rather than TypeScript, despite the site being
a TypeScript codebase. Tests run under `pytest`, as the existing Python packages do.

### The corpus reconciles with `interview.ts` rather than duplicating it
`src/data/interview.ts` already holds first-person positions across Foundations, RAG, Agents,
Evaluation, Production and Safety. Those are *positions*, not *evidence*: an answer explaining
how the user controls LLM cost is not the same artifact as a dated, attributable accomplishment
with a metric. The corpus therefore imports them as a distinct entry kind rather than flattening
them into bullets, and the interview-question generator uses them to distinguish a question the
user already has a worked answer to from one they do not.

That distinction is the whole value: a question set that cannot tell prepared ground from
unprepared ground is just a list of questions.

*Alternative considered:* generate the corpus's interview material from scratch and ignore
`interview.ts`. Rejected — it would produce a second, drifting set of answers to the same
questions, in a repository where one set is already load-bearing for the live chatbot.

### Structured JD sources per host, with text as the universal fallback
Apple posting pages render client-side; `jobs.apple.com/api/v1/jobDetails/<id>` returns
clean JSON. A small registry maps hosts to structured sources, and unknown hosts fall back
to generic text extraction. Pasted text always works and needs no network.

*Alternative considered:* a headless browser for JS-rendered pages. Rejected — a heavy
dependency for something a documented JSON endpoint and a paste box already solve.

### Hard filters are reported, never averaged
Language fluency, location, clearance and minimum years are eligibility filters. Folding
them into a match percentage would let a disqualifying miss hide behind a high score, so
they are surfaced separately. Years thresholds are computed from role dates and reported
alongside the requirement rather than asserted as a pass.

## Risks / Trade-offs

- **The corpus is only as honest as its author.** The validator enforces the shape of a
  metric, not its truth; a user can mark a fabricated figure `verified: true`. → Mitigated
  only by the traceability record, which makes every rendered claim attributable to an entry
  the user wrote deliberately. Accepted limitation, stated rather than papered over.

- **Private data in a public repository.** The corpus holds client names, team sizes and
  internal project names. → Gitignored path plus a committed fictional example; generated
  kits are gitignored too, since a kit embeds corpus content. A committed example that CI
  validates means the schema stays exercised without the real file.

- **The audit gate can be over-strict and block legitimate output.** A re-worded bullet may
  not trace cleanly by naive string matching. → Traceability is by bullet id carried through
  selection, not by matching rendered text back to source text.

- **One-page fitting is heuristic.** Rendered length in `.docx` depends on the font metrics
  and cannot be known exactly before rendering. → Fit by estimated line count with a margin,
  and report the estimate so the user can check rather than trusting silently.

- **LinkedIn export format is not a stable contract.** Column names and archive layout change
  without notice. → Seeding is a one-time bootstrap, not a runtime dependency; if the format
  shifts, the fallback is manual corpus entry, which loses nothing already captured.

- **Acceptance is judged by a human.** "At least as good as the hand-written pair" cannot be
  asserted by a test. → The two hand-written CVs are kept as the reference target and the
  user is the judge; the automated tests cover the mechanical guarantees only.

- **Scope is large for one change.** Five capabilities, a new package, a new skill. → Task
  ordering builds the corpus and validator first, so the highest-value piece (a structured,
  validated career history) exists and is useful even if later stages slip.

## Migration Plan

Nothing to migrate — this is additive, and it lands entirely in a new repository. No existing
capability changes, no data moves, and no deployed surface is touched. Rollback is deleting
that repository.

Seed data is *read* from the site repository (`src/data/profile.ts`, `src/data/interview.ts`,
`src/data/lab.ts`) as a one-time bootstrap. It is copied, not linked: the engine must not take
a build dependency on the site.

Sequencing is deliberate: repository and CI, then schema and validator, then seeding, then
ingestion, then matching, then rendering, then the skill wrapper. Each stage is independently
useful, and the corpus — the asset — exists first.

## Open Questions

- ~~**The `cv-tailor` repository does not exist yet.**~~ **Answered.** It exists at
  `github.com/alvintayzhenwei/cv-consultant-pro`, and the engine is built there.
- **Where these planning artifacts should live.** They are currently in the site repository's
  `openspec/changes/`, but the change now has no code footprint here, and OpenSpec scopes a
  repo-local change's edits to its own project. They should probably move to the engine
  repository once it exists. Left in place for now because moving them before the destination
  exists would only lose them.
- ~~**The LinkedIn export has not been supplied.**~~ **Answered, and the premise was wrong.**
  There is no export a person can obtain — "Save to PDF" on your own profile is the only
  route out — so the seeder reads the PDF. It takes what the page states and cannot be
  recalled (employers, titles, dates, certifications, education) and deliberately emits **no
  bullets**: a bullet needs a claim, its mechanism and its tags, and a profile carries only
  the first. The profile's own prose goes verbatim to a notes file the user works through a
  line at a time.
- **Whether the engine is eventually published to PyPI, and under what name.** Deferred until
  it has been used against real postings and the shareable surface is known.
- **Whether the Digital Twin eventually calls the engine.** Out of scope here, but it is the
  reason the engine/corpus separation is enforced from day one. `src/data/interview.ts` is the
  seam where that integration would land.
