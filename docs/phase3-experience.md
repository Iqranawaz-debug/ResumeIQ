# Phase 3: employment extraction

## Root cause (recorded before implementation)

The old parser removed blank lines and used a two-line date lookahead to
promote text into a title. This could promote a previous role's description.
It did not recognize seasons, numeric months or Current. Only the first
experience section was read. Heading detection rejected more than four words,
so Earlier Projects & Open Source remained inside employment. DOCX tables
were appended after all paragraphs, losing document section order.

Consumers use title, duration and details: scoring, recommendations, matching,
the review UI and the provider privacy allowlist. Upload returns the candidate
dictionary directly; history stores analysis rather than a typed employment
schema. Preserve those keys; organization and projects are additive. Keep the
provider allowlist unchanged (projects/organizations are not sent).

## Implementation and compatibility

- `backend/extractor/extractor.py`: exact known headings with punctuation and
  up to three wrapped lines; all employment/project sections; numeric date
  spans excluded from phone extraction. Contact and education rules otherwise
  unchanged. Removed obsolete date/lookahead/wrapping helpers.
- `backend/extractor/employment.py` (new): deterministic role/organization
  cues, explicit date anchors, bullet-aware descriptions, duplicate record
  removal through the caller, separate project records. Ambiguous employer
  text stays in `header_lines`, rather than receiving a guessed label.
- `backend/utils/employment_dates.py` (new): written range recognition,
  month/year precision, seasons, Current/Present, invalid/uncertain status.
- `backend/evaluator/scorer.py`: union of dated intervals instead of the span
  between the earliest and latest years.
- `backend/parser/docx_parser.py`: paragraphs and nested tables in document
  order, retaining blank boundaries and avoiding repeated merged cells.
- `frontend/src/App.jsx`: Professional Experience and Projects & Open Source
  using existing classes; optional organization, ambiguous header lines and
  invalid-range notice; missing/legacy fields handled safely.
- `backend/tests/test_experience.py` (new): 29 synthetic tests, including an
  in-memory PDF, DOCX, and upload/analysis/history endpoint data flow.
- `backend/tests/test_known_defects.py`: D01 (gaps) and D04 (repeated sections)
  promoted from expected failures to normal regression tests.
- `backend/tests/test_skills.py`: expected candidate keys include additive
  `projects`; all existing skill assertions preserved.
- This report records scope, causes, verification and limitations.

The existing `experience` array and its `title`, `duration`, `details` keys
remain. New fields are `organization`, optional `header_lines`, `date_status`,
and candidate-level `projects`. Missing titles/organizations are null. Upload
and analysis routes and their envelopes remain unchanged. History continues
to hold summary records; old candidates without projects render safely.
No authentication, upload validation, provider behavior or dependency changes.

## Before and after (synthetic)

Previously, a seasonal Teaching Assistant entry followed by a description,
IT Intern, an employer and a recognized range could become a title containing
the preceding description and the next role. Project headings could then
appear among its details. The regression now produces:

| Title | Organization | Duration | Details |
|---|---|---|---|
| Development Intern | Example Services | July 2026 – August 2026 | Built an agent. |
| Teaching Assistant (Computing) | Example University | Fall 2025 | Mentored students; supported grading. |
| IT Intern | Example Authority | Jun 2025 - Aug 2025 | Supported operations. |

The subsequent Analysis Dashboard and “Built charts with Python.” belong to
`projects`, not employment. No user resumes were used in tests.

## Explicit tenure semantics

Scoring weights, thresholds and matching formulas are unchanged. Their inputs
can legitimately change when projects stop receiving employment points or
employment is correctly separated. Tenure now excludes gaps and counts
overlaps once. For example 2010–2011 plus 2024–2025 changes from 15 to 2 years.
Month ranges use elapsed endpoint months (June–August = 2 months, not three
inclusive months), returned as years rounded to two decimals. Year-only
ranges retain coarse year-difference arithmetic; they are estimates, not
assertions about actual January start/end dates. Mixed year/month precision,
seasons, single dates and missing dates contribute zero rather than fabricated
time. Invalid reversed ranges remain visible, flagged, and excluded. Current
and Present use today's month or year at the start endpoint's precision.
These corrected values can change experience level and job-fit scores.

## Verification

- New experience tests: **29 passed**.
- Targeted experience, skills, baseline and known-defect pytest run:
  **83 passed, 3 xfailed**, with **119 passing subtests**.
- Full backend unittest discovery: **103 tests: 86 passed, 14 failed,
  3 expected failures**. All 14 failures remain in existing async security
  tests: the socket connect mock raises `External effects forbidden` during
  Windows asyncio socketpair initialization, before the test body. Those
  tests were not edited. This does not establish that their behaviors pass.
- Remaining expected failures: D02 legacy raw React.js alias matching,
  D03 hyphenated JD experience minimum, D07 negated degree requirements.
- Frontend `npm run lint`: passed. `npm run build`: passed, no build warnings.
- `git diff --check`: passed (Git separately reports existing LF/CRLF notices).
- Endpoint compatibility test exercises real parsing, extraction, upload,
  resume ID, analysis and history in memory, with thread-pool calls inline.
  It is not an HTTP transport or browser interaction test. An initial asyncio
  version stalled in Windows socketpair setup and was stopped; only this new
  test's execution harness was changed to avoid requiring a socket.

Commands from `backend`:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_experience.py -q
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

Targeted pytest used the existing pytest installation at
`C:/Users/iqran/AppData/Roaming/Python/Python314/site-packages`, appended to the
venv interpreter's import path; no packages were installed. Selected files:
`tests/test_experience.py`, `tests/test_skills.py`, `tests/test_baseline.py`,
`tests/test_known_defects.py`.

## Remaining limitations

This is conservative English text parsing, not layout understanding. Unusual
undated job titles, prose resembling short role headings, and unlabelled
employers can remain ambiguous. Shared employers are not inferred for later
roles. Project names versus short unpunctuated descriptions can be ambiguous;
their text is retained in the projects section. Technologies are preserved
in descriptions, not inferred into a new project technology list. Multicolumn
PDF reading order, text boxes, scanned PDFs/OCR, and complex table layouts
remain unsupported or dependent on the underlying parser. Year-only tenure
is inherently approximate, especially alongside month-precise intervals.
No visual browser QA was performed; frontend validation was lint and build.

Stayed on `feature/resumeiq-redesign`; prior uncommitted work was preserved.
No accounts, secrets or user resumes were read or deleted. Nothing staged,
committed, pushed, merged or published.
