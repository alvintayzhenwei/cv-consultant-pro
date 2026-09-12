"""Corpora and postings from professions this tool was not written for.

Every earlier test used one career — an AI engineer's — and one style of job ad,
the kind a large technology company writes. That is the narrowest possible proof
for a package strangers are meant to install.

These five run the whole pipeline against nursing, construction, teaching,
hospitality and accountancy: different vocabulary, different credentials that act
as hard filters, and in three cases heading conventions a tech posting never uses
("Essential criteria", "Person specification", "Selection criteria").

They are entirely fictional.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Domain:
    """One profession: a corpus, a posting, and what the pipeline must find."""

    key: str
    corpus: str
    posting: str
    #: A phrase the scorecard must recognise as a hard filter — usually a
    #: licence or registration, which is how most regulated professions gate.
    hard_filter_phrase: str
    #: A skill the corpus holds that the posting asks for, under the posting's
    #: own wording. Proves the alias bridge works outside a technology vocabulary.
    expected_skill: str


# ── Healthcare ───────────────────────────────────────────────────────────────
# UK/AU public-sector convention: "Essential criteria" / "Desirable criteria".
NURSE = Domain(
    key="nurse",
    hard_filter_phrase="registration",
    expected_skill="Wound care",
    corpus="""
person:
  name: Priya Raman
  location: Manchester
summaries:
  - id: sum-ward
    tags: [ward, acute, nursing, patient]
    text: >-
      Registered nurse on an acute medical ward, with a standing role in
      preceptorship for newly qualified staff.
  - id: sum-community
    tags: [community, district, home]
    text: Community nurse managing a caseload across four GP practices.
roles:
  - id: royal-ward-sister
    org: Royal Infirmary
    title: Ward Sister, Acute Medical Unit
    start: "2021-03"
    end: present
    tags: [nursing, acute, ward, leadership, patient-care]
    bullets:
      - id: rw-preceptorship
        claim: Ran the preceptorship programme for newly qualified nurses joining the ward
        mechanism: paired shifts, a competency log and a six-month review
        tags: [preceptorship, mentoring, training, nursing, onboarding]
      - id: rw-pressure-ulcers
        claim: Cut hospital-acquired pressure ulcers on the ward by a third
        mechanism: two-hourly repositioning rounds and a skin-assessment checklist at handover
        tags: [wound-care, tissue-viability, patient-safety, audit]
        metric:
          verified: true
          value: down by a third
      - id: rw-staffing
        claim: Managed the off-duty rota for [N] registered nurses and healthcare assistants
        mechanism: balancing skill mix against acuity each shift
        tags: [rota, staffing, leadership, nursing]
        metric:
          verified: false
          placeholder: "[N]"
  - id: st-marys-staff-nurse
    org: St Mary's Hospital
    title: Staff Nurse
    start: "2017-09"
    end: "2021-02"
    tags: [nursing, medical, patient-care]
    bullets:
      - id: sm-cannulation
        claim: Qualified as a cannulation and venepuncture trainer for the directorate
        mechanism: assessing competence and signing off practice for other nurses
        tags: [cannulation, venepuncture, training, clinical-skills]
skills:
  - name: Wound care
    aliases: [tissue viability, pressure ulcer prevention, wound management]
    evidence_refs: [rw-pressure-ulcers]
  - name: Preceptorship
    aliases: [mentoring, supporting newly qualified nurses, clinical supervision]
    evidence_refs: [rw-preceptorship]
  - name: Clinical skills training
    aliases: [cannulation, venepuncture, competency assessment]
    evidence_refs: [sm-cannulation]
education:
  - institution: University of Salford
    qualification: BSc (Hons) Adult Nursing
    end: "2017-07"
certifications:
  - name: NMC Registration
    held: true
""",
    posting="""
Ward Sister — Acute Medical Unit
Band 6 · Full time

Essential criteria:
- Current NMC registration with no restrictions on practice.
- Post-registration experience in an acute medical setting.
- Evidence of supporting and assessing newly qualified nurses.
- Demonstrable involvement in tissue viability or pressure ulcer prevention.

Desirable criteria:
- Mentorship or practice assessor qualification.
- Experience of managing an off-duty rota.

Key responsibilities
- Lead the nursing team on shift and act as clinical decision maker.
- Support preceptees and contribute to competency assessment.
""",
)

# ── Construction ─────────────────────────────────────────────────────────────
CIVIL_ENGINEER = Domain(
    key="civil-engineer",
    hard_filter_phrase="chartered",
    expected_skill="Temporary works",
    corpus="""
person:
  name: Tomas Iversen
  location: Oslo
summaries:
  - id: sum-site
    tags: [site, construction, delivery, temporary-works]
    text: >-
      Site agent on highway and bridge schemes, running temporary works design
      co-ordination and the safety case that goes with it.
  - id: sum-design
    tags: [design, drainage, structures]
    text: Civil designer specialising in highway drainage and retaining structures.
roles:
  - id: nordvei-site-agent
    org: Nordvei Anlegg
    title: Site Agent
    start: "2020-05"
    end: present
    tags: [construction, site, delivery, safety, temporary-works]
    bullets:
      - id: nv-temporary-works
        claim: Co-ordinated temporary works design across a 14-span viaduct replacement
        mechanism: acting as temporary works co-ordinator between the designer and site teams
        tags: [temporary-works, structures, coordination, safety]
      - id: nv-programme
        claim: Brought a bridge deck pour back onto programme after a four-week weather delay
        mechanism: resequencing night pours and bringing a second pump on site
        tags: [programme, planning, delivery, concrete]
        metric:
          verified: true
          value: four weeks recovered
      - id: nv-rams
        claim: Wrote and reviewed risk assessments and method statements for [N] subcontractors
        mechanism: pre-start reviews against the temporary works register
        tags: [safety, rams, cdm, subcontractors]
        metric:
          verified: false
          placeholder: "[N]"
  - id: bergen-design
    org: Bergen Consult
    title: Graduate Civil Engineer
    start: "2016-08"
    end: "2020-04"
    tags: [design, drainage, civil]
    bullets:
      - id: bc-drainage
        claim: Designed highway drainage for three trunk road improvement schemes
        mechanism: catchment modelling and attenuation sizing to the national design standard
        tags: [drainage, design, highways, modelling]
skills:
  - name: Temporary works
    aliases: [temporary works co-ordination, TWC, falsework, formwork design]
    evidence_refs: [nv-temporary-works]
  - name: Site safety
    aliases: [CDM, risk assessments, method statements, RAMS]
    evidence_refs: [nv-rams]
  - name: Highway drainage design
    aliases: [drainage design, attenuation, catchment modelling]
    evidence_refs: [bc-drainage]
education:
  - institution: NTNU Trondheim
    qualification: MSc Civil Engineering
    end: "2016-06"
certifications:
  - name: CSCS Card
    held: true
""",
    posting="""
Senior Site Agent — Major Highways

Requirements:
- Chartered engineer status with a recognised institution, or working towards it.
- 5 years of experience delivering highway or structures schemes on site.
- Experience acting as temporary works co-ordinator.
- Strong working knowledge of CDM duties and RAMS review.

Desirable:
- Experience of drainage design as well as delivery.

Key responsibilities
- Own the temporary works register and the safety case on site.
- Hold the programme and resequence when weather or supply disrupts it.
""",
)

# ── Education ────────────────────────────────────────────────────────────────
# UK schools convention: a "Person specification" rather than qualifications.
TEACHER = Domain(
    key="teacher",
    hard_filter_phrase="qualified teacher status",
    expected_skill="Phonics",
    corpus="""
person:
  name: Aoife Byrne
  location: Bristol
summaries:
  - id: sum-primary
    tags: [primary, classroom, phonics, curriculum]
    text: >-
      Primary teacher and phonics lead, with four years of Key Stage 1 classroom
      practice and responsibility for early reading across the school.
  - id: sum-senco
    tags: [send, inclusion, support]
    text: Teacher with a specialism in supporting pupils with additional needs.
roles:
  - id: oakfield-phonics-lead
    org: Oakfield Primary School
    title: Class Teacher and Phonics Lead
    start: "2021-09"
    end: present
    tags: [teaching, primary, phonics, curriculum, leadership]
    bullets:
      - id: op-phonics
        claim: Led the move to a validated systematic synthetic phonics programme across Reception and Year 1
        mechanism: staff training, weekly practice drop-ins and a fortnightly assessment cycle
        tags: [phonics, early-reading, curriculum, training, leadership]
      - id: op-screening
        claim: Raised the Year 1 phonics screening pass rate from 68% to 89% over two years
        mechanism: targeted keep-up sessions the same day a gap appeared, rather than weekly catch-up
        tags: [phonics, assessment, intervention, outcomes]
        metric:
          verified: true
          value: 68% to 89%
      - id: op-parents
        claim: Ran termly reading workshops for parents of [N] families
        mechanism: modelling the sounds and sending home decodable books matched to the lesson
        tags: [parents, engagement, reading, community]
        metric:
          verified: false
          placeholder: "[N]"
  - id: st-bedes-teacher
    org: St Bede's Junior School
    title: Class Teacher
    start: "2019-09"
    end: "2021-07"
    tags: [teaching, primary, classroom]
    bullets:
      - id: sb-send
        claim: Adapted planning for a class with six pupils on SEND support plans
        mechanism: scaffolded tasks and a teaching assistant deployment plan per lesson
        tags: [send, inclusion, differentiation, planning]
skills:
  - name: Phonics
    aliases: [systematic synthetic phonics, SSP, early reading]
    evidence_refs: [op-phonics, op-screening]
  - name: Assessment and intervention
    aliases: [formative assessment, keep-up sessions, pupil progress]
    evidence_refs: [op-screening]
  - name: SEND support
    aliases: [SEND, inclusion, differentiation, additional needs]
    evidence_refs: [sb-send]
education:
  - institution: University of Bristol
    qualification: PGCE Primary Education
    end: "2019-07"
certifications:
  - name: Qualified Teacher Status
    held: true
""",
    posting="""
Class Teacher with responsibility for Early Reading

Person specification

Essential:
- Qualified teacher status.
- Experience teaching in Key Stage 1.
- Experience leading a systematic synthetic phonics programme.
- Commitment to safeguarding and promoting the welfare of children.

Desirable:
- Experience of running workshops for parents.
- Experience supporting pupils with SEND.

Main duties
- Lead early reading across Reception and Key Stage 1.
- Use assessment to identify and close gaps quickly.
""",
)

# ── Hospitality ──────────────────────────────────────────────────────────────
RESTAURANT_MANAGER = Domain(
    key="restaurant-manager",
    hard_filter_phrase="right to work",
    expected_skill="Food safety",
    corpus="""
person:
  name: Dario Mensah
  location: Singapore
summaries:
  - id: sum-ops
    tags: [operations, restaurant, service, cost]
    text: >-
      Restaurant general manager running a 120-cover site, accountable for
      service standards, food cost and a team across front and back of house.
  - id: sum-openings
    tags: [opening, new-site, launch]
    text: Operations manager specialising in new site openings and pre-launch training.
roles:
  - id: harbour-gm
    org: Harbour House
    title: General Manager
    start: "2022-02"
    end: present
    tags: [restaurant, operations, leadership, service, cost-control]
    bullets:
      - id: hh-food-cost
        claim: Brought food cost from 34% to 29% of revenue without changing the menu price
        mechanism: weekly stock counts, a waste log per section and renegotiated produce deliveries
        tags: [cost-control, gross-profit, stock, procurement]
        metric:
          verified: true
          value: 34% to 29%
      - id: hh-haccp
        claim: Held the top food hygiene rating across three consecutive unannounced inspections
        mechanism: daily HACCP checks signed at each section and a monthly internal audit
        tags: [food-safety, haccp, hygiene, compliance, audit]
      - id: hh-retention
        claim: Cut front-of-house turnover to [X]% by restructuring the rota around split shifts
        mechanism: fixed days off and a published rota four weeks ahead
        tags: [retention, rota, team, leadership]
        metric:
          verified: false
          placeholder: "[X]%"
  - id: lantern-supervisor
    org: The Lantern
    title: Restaurant Supervisor
    start: "2019-06"
    end: "2022-01"
    tags: [restaurant, service, supervision]
    bullets:
      - id: tl-training
        claim: Built the wine and service training used by every new starter
        mechanism: a tasting session per section head and a short sign-off on the floor
        tags: [training, service, wine, onboarding]
skills:
  - name: Food safety
    aliases: [HACCP, food hygiene, food safety management]
    evidence_refs: [hh-haccp]
  - name: Cost control
    aliases: [gross profit, food cost, stock control, GP management]
    evidence_refs: [hh-food-cost]
  - name: Team training
    aliases: [service training, onboarding, staff development]
    evidence_refs: [tl-training]
education:
  - institution: Temasek Polytechnic
    qualification: Diploma in Hospitality Management
    end: "2019-05"
certifications:
  - name: Food Hygiene Officer Certificate
    held: true
""",
    posting="""
Restaurant General Manager

Requirements:
- Right to work in Singapore without employer sponsorship.
- 3 years of experience managing a full-service restaurant.
- Proven track record of managing food cost and gross profit.
- Working knowledge of HACCP and food safety management.

Nice to have:
- Experience opening a new site.

What you'll do
- Own the P&L for the site and hold gross profit targets.
- Build and retain a team across front and back of house.
""",
)

# ── Finance ──────────────────────────────────────────────────────────────────
ACCOUNTANT = Domain(
    key="accountant",
    hard_filter_phrase="qualified accountant",
    expected_skill="Statutory reporting",
    corpus="""
person:
  name: Wei Ling Foo
  location: Kuala Lumpur
summaries:
  - id: sum-reporting
    tags: [reporting, statutory, audit, consolidation]
    text: >-
      Financial accountant owning statutory reporting and the year-end audit for
      a group of six entities.
  - id: sum-fpa
    tags: [forecasting, budget, analysis]
    text: Finance analyst focused on budgeting, forecasting and variance analysis.
roles:
  - id: meridian-financial-accountant
    org: Meridian Group
    title: Financial Accountant
    start: "2021-01"
    end: present
    tags: [accounting, reporting, statutory, audit, consolidation]
    bullets:
      - id: mg-yearend
        claim: Cut the group year-end close from 18 working days to 11
        mechanism: moving intercompany reconciliation into the month-end cycle instead of year-end
        tags: [close, reporting, consolidation, process]
        metric:
          verified: true
          value: 18 days to 11
      - id: mg-audit
        claim: Owned the statutory audit file for six entities with no prior-year adjustments
        mechanism: a standing evidence pack maintained monthly rather than assembled in Q1
        tags: [audit, statutory, compliance, reporting]
      - id: mg-ifrs16
        claim: Led the transition to the new lease accounting standard across [N] contracts
        mechanism: a lease register with remeasurement triggers reviewed quarterly
        tags: [ifrs, leases, technical-accounting, transition]
        metric:
          verified: false
          placeholder: "[N]"
  - id: tanjung-analyst
    org: Tanjung Industries
    title: Finance Analyst
    start: "2018-04"
    end: "2020-12"
    tags: [finance, analysis, budgeting]
    bullets:
      - id: ta-forecast
        claim: Rebuilt the rolling forecast so variances were explained by driver rather than by line
        mechanism: volume, price and mix split out separately for each business unit
        tags: [forecasting, budgeting, variance, analysis]
skills:
  - name: Statutory reporting
    aliases: [statutory accounts, financial reporting, year-end close, group consolidation]
    evidence_refs: [mg-yearend, mg-audit]
  - name: Audit management
    aliases: [external audit, audit file, audit liaison]
    evidence_refs: [mg-audit]
  - name: Forecasting
    aliases: [budgeting, rolling forecast, variance analysis]
    evidence_refs: [ta-forecast]
education:
  - institution: Universiti Malaya
    qualification: BAcc (Hons) Accounting
    end: "2018-02"
certifications:
  - name: ACCA
    held: true
""",
    posting="""
Financial Accountant — Group Reporting

Qualifications:
- Qualified accountant (ACCA, CPA or equivalent).
- 4 years of experience in statutory reporting and group consolidation.
- Experience owning an external audit file.

Preferred qualifications:
- Experience of a lease accounting standard transition.
- Budgeting and forecasting exposure.

Responsibilities
- Own the group year-end close and the statutory audit.
- Improve the close timetable without losing control quality.
""",
)


ALL_DOMAINS = [NURSE, CIVIL_ENGINEER, TEACHER, RESTAURANT_MANAGER, ACCOUNTANT]

__all__ = [
    "ACCOUNTANT",
    "ALL_DOMAINS",
    "CIVIL_ENGINEER",
    "NURSE",
    "RESTAURANT_MANAGER",
    "TEACHER",
    "Domain",
]
