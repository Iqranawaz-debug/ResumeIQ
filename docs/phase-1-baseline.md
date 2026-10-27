# Phase 1 baseline — 19 October 2026

Branch: `feature/resumeiq-redesign`. Scope: tests, setup verification, documentation,
and ignore rules only. Application logic, UI, existing dependency manifests, and
the frontend lockfile are unchanged. No commits, pushes, or merges.

## Environment and installation

- Windows, Python 3.14.3, Node 24.21.0, npm 11.19.0.
- `npm ci` installed the existing frontend lockfile: 24 packages reported added.
- A new isolated `backend/.venv` contains the six existing requirements and their
  transitive dependencies: 29 packages. No global package upgrades.
- Backend had no lockfile. `backend/constraints-baseline.txt` captures resolved
  versions for this environment, not a hash-verified cross-platform lockfile.
- Pydantic is imported directly but supplied transitively. No missing runtime
  dependency was found after installation; `pip check` passed.
- Restricted execution initially prevented ensurepip/network installation. The
  authorized installs succeeded with elevated tool access; no secret files or
  application logic were changed to work around this.

## Verification

| Check | Result |
| --- | --- |
| Backend unittest discovery | 35 tests: 28 passed, 7 expected failures, no unexpected failures/errors |
| Backend dependency consistency | `pip check`: no broken requirements |
| Isolated app import / OpenAPI generation | Passed; six application paths |
| Frontend lint | Passed with one existing unused-variable warning |
| Frontend production build | Passed; 21 modules transformed, no build warnings |
| npm dependency audit | Three findings: two high, one moderate; no fixes applied |

App import/OpenAPI generation replaced account-file reads with an empty in-memory
JSON stream. Actual accounts were not read. This checks imports and route/schema
construction, not live authentication or HTTP behavior. No server was left running.

Tests cover date handling, completeness scores, matching, upload validation,
extraction, in-memory PDF/DOCX parsing, and mocked AI success/fallback behavior.
The baseline test module blocks outbound socket connections. Tests never import
`main` or `auth.auth`, whose import would otherwise read local account records.

No real resume, live AI call, browser interaction, full authentication test, load
test, or backend vulnerability scan was performed. Passing these checks does not
establish production readiness.

## Expected failures

| ID | Desired behavior | Current defect |
| --- | --- | --- |
| D01 | Exclude employment gaps | Two one-year roles in 2010–2011 and 2024–2025 report 15 years |
| D02 | Recognize React.js as React | React reported missing |
| D03 | Interpret `3-5 years` as minimum three | Extracts five |
| D04 | Preserve repeated Experience sections | Only first section extracted |
| D05 | Reject AI overall scores above 100 | Schema accepts 101 |
| D06 | Reject negative AI overall scores | Schema accepts -1 |
| D07 | Interpret degree negation | `No degree required` is treated as a requirement |

These desired-behavior assertions use `unittest.expectedFailure`. Unexpected
successes fail the suite. When an approved fix lands, remove its decorator and
retain the regression assertion. No production logic was changed to pass tests.

Passing characterization tests also record the current unknown-requirements score
(35) and weak-match cap (49), without endorsing these as reliable hiring policies.
Other audited issues remain: session expiry/retention, identity casing, multi-tab
resume selection, missing JD limits, blocking I/O, privacy disclosure, extraction
evidence, and keyboard accessibility.

## Frontend warnings and dependency findings

Oxlint reports unused `TOTAL_STEPS` at `src/App.jsx:15`. It remains unchanged to
keep production code outside this phase. Vite found no broken imports. Build
output was approximately 219.49 kB JavaScript (66.68 kB gzip) and 16.14 kB CSS
(3.89 kB gzip), plus HTML.

`npm audit` reported these transitive dependencies in the existing graph. This is
a registry report, not proof of an exploitable application path:

- High: nanoid, [GHSA-2v37-7h3g-55p8](https://github.com/advisories/GHSA-2v37-7h3g-55p8).
- Moderate: postcss, [GHSA-fxqj-rqcc-2cmp](https://github.com/advisories/GHSA-fxqj-rqcc-2cmp).
- High: source-map-js, [GHSA-68fv-2mgg-jv7q](https://github.com/advisories/GHSA-68fv-2mgg-jv7q).

No `npm audit fix`, framework upgrade, or frontend lockfile update was performed.
Review affected tooling paths and compatible fixes in a separately approved
dependency maintenance change.

## Safety and next step

The starting working tree/index were clean. Tracked filenames contained no
environment files, credential-named files, account records, resumes, or build
outputs. No secrets or private user data were opened. Ignore rules now cover
additional environment-file variants, PDF/DOCX documents, upload/resume folders,
and test outputs. Virtual environments, node_modules, dist, and local accounts
are ignored. Future synthetic document fixtures should be generated in memory;
do not force-add real resumes. Ignore rules do not replace staged-content review.

Recommended next phase: immediate input/session/privacy and request-consistency
fixes, followed by scoring/extraction repairs backed by these tests. UI redesign
and dependency remediation require separate approval.
