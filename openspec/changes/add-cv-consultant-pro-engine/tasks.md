> **Status — implementation landed 2026-09-13 in the separate engine repository**
> (`github.com/alvintayzhenwei/cv-consultant-pro`, branch `feat/mcp-plugin`). The boxes below
> are ticked from the code as it actually stands, checked against that repo rather than
> recalled — several items diverged from this plan and say so inline rather than being
> ticked as written. **Sections 8 (acceptance) and 9.4 are genuinely outstanding**: the
> engine has not yet been judged against the two hand-written CVs, which was the
> acceptance criterion, and these artifacts still have to move to the engine repo.
>
> **Update 2026-09-14 — renamed, published, and moved here.** The project was renamed
> from `cv-tailor` to `cv-consultant-pro` before its first release: `cv-tailor-mcp` is
> taken on PyPI by an unrelated author, and shipping an install line pointing at a
> stranger's package was the one mistake that could not be undone. Every reference in
> these documents was updated with it; the struck-through question in design.md keeps its
> original wording because it is a record of what was asked, not a claim about today.
>
> `cv-consultant-pro-mcp` is published — 0.1.0, 0.1.1, 0.1.2 — so task 9.4 is now done and
> these artifacts live beside the code they describe.
>
> **Task 8 needs rewriting before it can be judged.** Its acceptance criterion was "at
> least as good as the hand-written CVs". Those CVs were not hand-written by the owner:
> they were drafted by an assistant in an earlier session, so comparing the engine to them
> compares it to its own earlier output. The real criterion is the owner's judgement that a
> generated CV represents him — which he has since exercised directly, correcting five
> claims the corpus had wrong.
>
> **Found after these boxes were ticked**, by five independent testers driving the
> published 0.1.2: 111 defects, 11 critical. Two root causes account for most of them — a
> figure could be passed in and written as measured with nothing tying it to the user, and
> an unrecognised posting heading discarded every requirement beneath it. Both are fixed.
> Section 8.4's guarantee check was ticked and was not sufficient; it needs the
> outside-tester shape rather than a self-run fixture.
>
> The plan also under-described the finished thing. Built and not planned here: an MCP
> server with fourteen tools, a session state machine so the conversation is identical on
> every host, a loopback layout preview, corpus write-back that re-validates before saving,
> a ten-question pre-interview with an authenticity gate, and a five-profession test suite.

## 1. Repository scaffold

Target: `https://github.com/alvintayzhenwei/cv-consultant-pro` — public, empty, default branch `main`.
**The repository is public: no task in this plan may commit corpus data, a real CV, or a
generated kit.**

- [x] 1.1 Clone the repository and add `.gitignore` covering `career-corpus.yaml`, the kit output directory, `.venv/` and `__pycache__/` **as the first commit, before any other file exists**
- [x] 1.2 Enable `core.hooksPath` and a pre-push guard if one is wanted here, mirroring the site repo's own protection; branch from `main` with `--no-track` per `source-control.md`
- [x] 1.3 Create `pyproject.toml`, `src/cv_consultant_pro/`, `tests/`, README and a licence (the repo currently has none)
- [x] 1.4 Declare dependencies: `PyYAML`, `python-docx`, `httpx`; pin majors deliberately and record why in the README, following the `mcp<2` lesson from the sibling packages
- [x] 1.5 Add CI running `pytest` on push and PR — this repo owns its own CI, which is the reason it is not a sibling directory in the site repo
- [x] 1.6 Add a CI check asserting no file matching the corpus or kit patterns is tracked, so the disclosure boundary is enforced by the build rather than by care
- [x] 1.7 Verify `pytest` runs green on an empty suite before any feature work

## 2. Corpus schema and validator

- [x] 2.1 Write the failing validator test first: a fixture with `verified: false` carrying a concrete value must fail with a non-zero exit and name the offending bullet id
- [x] 2.2 Define the corpus dataclasses — roles, bullets, metrics, skills, education, certifications, artifacts — with `language` defaulting to `en`
- [ ] 2.3 Implement the loader with `MM/YYYY` date parsing, `present` handling, and retention of dateless roles carrying an explicit `TODO` marker
  *(Built, but dates are stored `YYYY-MM` and RENDERED `MM/YYYY`; confusing the two rejected every role once.)*
- [x] 2.4 Implement the validator: unique bullet ids, at least one tag per bullet, and the verified/placeholder rule
- [x] 2.5 Add `positions` to the schema as an entry kind distinct from `bullets`, each recording the source it was imported from
- [x] 2.6 Write `career-corpus.example.yaml` with wholly fictional data — invented organisations, never a redaction of the real corpus — exercising every field, including at least one unverified metric, one dateless `TODO` role and one position
- [x] 2.7 Add the test that validates the committed example, so CI exercises the schema without the real corpus
- [x] 2.8 Make the corpus path configurable by argument and environment variable, defaulting to the repository root

## 3. Seeding

Seed data is **copied** from the site repository as a one-time bootstrap. The engine must
not take a build dependency on the site.

- [ ] 3.1 Write tests against a fixture export covering a current role, a past role and a role with a missing end date
  *(Diverged: LinkedIn offers no export a person can obtain, so the fixture is a synthetic profile PDF.)*
- [ ] 3.2 Implement the reader for the export's positions, profile, education and skills files, tolerating absent optional files
  *(Diverged: reads the profile PDF's two columns, not the export's files.)*
- [ ] 3.3 Emit a corpus draft with real `MM/YYYY` dates, every generated metric marked `verified: false` with a placeholder
  *(Diverged and deliberately narrower: it emits NO bullets. A bullet needs a claim, a mechanism and tags; a profile carries only the claim, so the prose goes verbatim to a notes file the user works through instead.)*
- [x] 3.4 Assert the drafted corpus passes the validator unchanged
- [x] 3.5 Import the twenty-one first-person answers from the site's `src/data/interview.ts` as `positions`, preserving topic grouping and recording the source
- [x] 3.6 Seed roles, skills and artifacts from the site's `src/data/profile.ts` and `src/data/lab.ts` (published articles, PyPI packages)
- [x] 3.7 Carry over the bullets already drafted in the two hand-written CVs, each marked unverified with its placeholder intact
- [x] 3.8 Run seeding against the user's real LinkedIn export and produce the working `career-corpus.yaml` *(blocked until the export is supplied)*
- [x] 3.9 Hand the user the list of `TODO` markers and placeholders to fill — the missing team sizes, percentages and pre-2025 dates

## 4. JD ingestion

- [ ] 4.1 Write tests for pasted text, a registered structured host, and an unreachable URL
  *(Only pasted text is tested. There is no URL path — see 4.3.)*
- [x] 4.2 Implement pasted-text ingestion with no network path
- [ ] 4.3 Implement the host registry and the Apple source via `jobs.apple.com/api/v1/jobDetails/<id>`, capturing the requisition id as the record identifier
  *(NOT built. `httpx` is declared for this and currently has no consumer: either build the fetch or drop the dependency.)*
- [ ] 4.4 Implement generic text extraction for unregistered hosts, reporting low confidence when the result is too short to contain qualifications
  *(NOT built — follows 4.3.)*
- [x] 4.5 Implement requirement extraction: split minimum from preferred by the posting's own headings, retaining verbatim wording alongside a normalised form
- [x] 4.6 Implement hard-filter detection for language, location, clearance and minimum years, capturing the years threshold as a number
- [ ] 4.7 Add a recorded fixture for req 200661514 so ingestion is testable without network access
  *(NOT built — follows 4.3.)*

## 5. Matching and the scorecard

- [x] 5.1 Write tests asserting every extracted requirement yields exactly one verdict, and that `gap` verdicts cite no evidence
- [x] 5.2 Implement scoring of corpus bullets and skills against requirements, using tags and declared aliases
- [x] 5.3 Emit the scorecard with supporting bullet ids on every `strong` and `partial` row
- [x] 5.4 Report hard filters separately, excluded from any aggregate figure, with the evidenced years span computed from role dates
- [x] 5.5 Implement the ranked gap plan, ordering unmet hard filters above scored gaps and naming what evidence would close each
- [ ] 5.6 Implement suggested corpus entries written to a separate suggestions file, with a test proving the corpus is byte-identical after a run
  *(Diverged: suggestions are proposed in the interview loop and written only on confirmation, so there is no separate suggestions file.)*

## 6. Rendering and the audit gate

- [x] 6.1 Write tests for the select-only contract: declared aliases may be adopted, undeclared vocabulary never appears in output
- [x] 6.2 Implement one-page selection — drop or demote whole roles by relevance, never truncate a bullet mid-sentence — with a reported length estimate
- [x] 6.3 Implement Markdown rendering: summary, skills block, reverse-chronological experience, `MM/YYYY` dates, XYZ-form bullets
- [x] 6.4 Implement placeholder emission for every unverified metric, plus the collected placeholder list for the user
- [x] 6.5 Implement the audit gate: trace every rendered bullet to a corpus id, refuse to write on failure, and emit the traceability record on success
- [x] 6.6 Implement `.docx` rendering with `python-docx`: single column, no tables, text boxes, headers, footers or images, system font, standard headings
- [x] 6.7 Add the test that extracts text from the generated `.docx` and asserts reading order matches visual order and no forbidden element is present
- [x] 6.8 Implement interview-question generation weighted toward `gap` and `partial` verdicts, citing corpus evidence where a requirement scored `strong`
- [x] 6.9 Mark each generated question as prepared or unprepared by matching it against the corpus `positions`, so the set separates worked answers from ground the user has not covered

## 7. Skill wrapper

- [x] 7.1 Write `skills/cv-consultant-pro/SKILL.md` in the engine repo, orchestrating the packaged engine with no pipeline logic of its own, and document installing it at user level so it works from any project
- [ ] 7.2 Write `references/ats-rules.md` recording the research findings with sources: the debunked auto-rejection claim, parsing as the true gate, the two readers, detected stuffing, the skills-block weighting, and the XYZ bullet form
  *(NOT built as a reference file; the research lives in the engine README's *On ATS* section.)*
- [ ] 7.3 Write `references/jd-sources.md` documenting the Apple JSON endpoint and the paste fallback
  *(NOT built — follows 4.3.)*
- [x] 7.4 Implement the per-posting kit directory holding scorecard, gap plan, CV in both formats, interview questions, traceability record, placeholder list and suggestions
- [ ] 7.5 Ensure a repeat run preserves the earlier kit or tells the user it will be replaced
  *(Partial: `cv_seed` refuses to overwrite an existing corpus; `cv_render` overwrites its kit directory silently.)*
- [x] 7.6 Verify the package runs standalone from a terminal without Claude Code present

## 8. Acceptance and verification

- [ ] 8.1 Run the engine against Apple req 200661514 and compare the kit to the hand-written Engineering Product Manager CV
- [ ] 8.2 Run the engine against Apple req 200645480 and compare to the hand-written Generative AI & ML CV
- [ ] 8.3 Get the user's judgement on whether both are at least as good as the hand-written pair; record what differed
- [ ] 8.4 Confirm the anti-fabrication guarantees against a deliberately bad corpus — an unverified metric carrying a number, and a rendered claim with no corpus entry — so neither guard is vacuously green
- [x] 8.5 Confirm `git status` lists neither the real corpus nor any generated kit, and that no commit in the repo's history has ever contained either — this repo is public, so a leak is not undone by a later deletion
- [x] 8.6 Confirm the site repository is genuinely untouched: `git status` clean there apart from these planning artifacts
- [ ] 8.7 Run `/code-review` on the full diff and resolve findings
- [ ] 8.8 Run `/security-review` on the full diff, with attention to the LinkedIn export reader, JD URL fetching (SSRF on an arbitrary user-supplied posting URL), and path handling around the corpus

## 9. Documentation

- [x] 9.1 Write the engine `README.md`: setup, corpus seeding, running against a posting, and the privacy rules stated prominently given the repo is public
- [ ] 9.2 Write the engine's own `CLAUDE.md` covering the corpus, the select-only contract, the validator guarantee and the gitignore boundary
  *(NOT built — the engine has no CLAUDE.md.)*
- [x] 9.3 Record that publishing to PyPI is a deliberate, separate owner step, per the site repo's own lesson that merging does not release a package
- [x] 9.4 Move these planning artifacts into the engine repository and remove them from the site repo, so the change lives with the code it describes
