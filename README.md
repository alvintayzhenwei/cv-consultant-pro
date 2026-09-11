# cv-tailor

Turn a job description into a tailored, ATS-safe application kit — a match scorecard, a
one-page CV in Markdown and `.docx`, a ranked gap plan, and the interview questions that
posting is likely to produce.

It does this by **selecting from a corpus of your own career evidence**. It never writes a
claim you did not write, and never invents a number.

> **This repository is public. Your corpus is not.**
> `career-corpus.yaml` is gitignored, and `.gitignore` is deliberately the first commit in
> this repository's history so there was never a window without it. A generated kit embeds
> corpus content in a rendered CV, so kits are ignored too. Neither is un-leaked by a later
> deletion — git keeps history. Only `career-corpus.example.yaml`, which contains wholly
> fictional data, is committed.

## Why it exists

Tailoring a CV by hand takes an evening per posting: read the JD, map it against a career
history that lives in several places and nowhere completely, decide what to cut, rewrite
bullets, then check that nothing overstates the truth.

Doing that twice by hand produced the insight this tool is built on: **the CV is the cheap
part; the corpus is the asset.** What makes tailoring possible is having every role,
accomplishment, metric and skill available as separate, addressable evidence. What makes it
slow is that no such store exists — a LinkedIn profile is prose, and a previous CV is one
frozen selection from a store that was never written down.

## The contract

The engine may **select, compress, re-order and re-word** corpus entries, and may adopt a
posting's exact vocabulary where the corpus already declares that wording as an alias of a
skill you hold. That last clause resolves a real tension: a literal keyword index wants the
posting's words, while a language-model screener — and the interviewer afterwards — want true
sentences.

It may **not**:

- author a claim absent from the corpus,
- introduce a skill the corpus does not hold,
- or replace an unverified metric with an estimated, rounded or inferred figure.

An unverified metric renders as its literal placeholder (`[X]`, `[N]`), and the kit lists
every placeholder so you know what to fill in. Before anything is written, an audit stage
verifies that every claim traces to a corpus entry id and refuses to write output that does
not.

This is enforced mechanically rather than by instruction. Every metric in the corpus declares
`verified: true` with a concrete value, or `verified: false` with a placeholder and no number.
The validator fails with a non-zero exit on any violation, so the rule is a build failure
rather than a prompt a renderer might drift from.

**The honest limit:** the validator enforces the *shape* of a metric, not its truth. Nothing
here stops you marking a fabricated figure `verified: true`. The traceability record is the
only real mitigation — every rendered claim stays attributable to something you wrote
deliberately.

## What it produces

Per posting, in one directory:

| File | What it is |
|---|---|
| `scorecard.md` | Every requirement scored `strong` / `partial` / `gap`, citing the corpus entries behind each |
| `cv.md`, `cv.docx` | The tailored one-page CV. `.docx` formatting is generated in code, not hand-applied |
| `gaps.md` | Unmet requirements ranked by impact, each naming the evidence that would close it |
| `interview.md` | Likely questions, marked prepared or unprepared against your recorded positions |
| `traceability.md` | Every rendered bullet mapped back to its corpus entry id |
| `placeholders.md` | Every `[X]` in the CV and which bullet it belongs to |
| `suggestions.yaml` | Drafted corpus entries for evidence the posting wanted and the corpus lacked — for you to verify and accept. Never rendered into a CV |

## On ATS, briefly

The widely-quoted claim that applicant tracking systems auto-reject 75% of résumés traces to
a 2012 sales pitch by a company that folded in 2013, with no published methodology. Recruiter
surveys put it differently: rejection is overwhelmingly manual, or triggered by eligibility
knock-out questions — not by formatting or a missing keyword.

So this tool does not try to beat a robot. It optimises for what actually gates an
application:

1. **Parsing.** The only true hard gate. Nothing downstream happens if the text cannot be
   extracted, which is why the `.docx` is generated in code — single column, no tables, text
   boxes, headers, footers or images, standard headings, `MM/YYYY` dates. Hand-reformatting
   in Word is exactly where this gets broken.
2. **Keyword search**, which a recruiter uses like Ctrl+F — hence the dedicated skills
   section, which carries more weight than the same skill buried in a bullet.
3. **A language-model reader**, which rewards specificity and recency, and whose vendors now
   actively detect stuffing and hidden text.

Bullets follow the XYZ form — accomplished X, as measured by Y, by doing Z.

## Repository security

This repository is public and the corpus is not, so the boundary is enforced in four
places rather than trusted once: `.gitignore` as the first commit, a pre-push hook that
inspects the tip being pushed, a CI job that fails if anything corpus-shaped is tracked,
and a test asserting the ignore rules still say what they should.

Beyond that: Dependabot version updates for the `uv` project and for the workflows
themselves, weekly CodeQL on `python` and `actions`, `pip-audit` against the resolved
lockfile on every PR and weekly, and dependency review on PRs. Every action is pinned to
a full commit SHA, because a tag is a mutable pointer the upstream owner can repoint.

Three of these are repository **settings** rather than files, and this repo cannot turn
them on for itself — enable them under *Settings → Code security*:

- **Dependabot alerts** and **Dependabot security updates** — `dependabot.yml` configures
  version updates only; the advisory-driven ones are a separate switch.
- **Secret scanning** and **push protection** — push protection is the one that matters:
  it blocks a credential at push time rather than alerting after it is public.

### Why there is no CODEOWNERS file

Deliberate, and worth stating because adding one looks like an obvious improvement.

GitHub never allows a pull request's author to approve their own PR — that is a platform
rule no setting overrides. With branch protection set to **Require review from Code
Owners** and a single maintainer, a CODEOWNERS file naming that maintainer would make
every pull request permanently unmergeable, short of an admin bypass on each one.

With no CODEOWNERS file, no path has an owner, so the rule has nothing to require and the
branch stays protected in every other respect. If a second maintainer ever joins, add the
file then.

### Required status checks

Branch protection has *Require status checks to pass* enabled but no checks selected yet;
GitHub can only offer a check it has already seen. After the first pull request runs,
add these by name under *Settings → Branches*:

- `Lint and test`
- `No corpus or kit is tracked`
- `pip-audit`

`CodeQL (python)` and `CodeQL (actions)` are worth adding once you have seen them pass;
CodeQL on a scheduled run can lag a fast-moving PR, so add them knowing that.

## Status

Early. The corpus schema and validator come first, because a structured, validated career
history is useful on its own even if nothing else ships.

## Licence

MIT.
