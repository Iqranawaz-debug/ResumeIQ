# Phase 5.1 — Browser QA and stabilization

Completed verification: 23 October 2026 (Asia/Karachi).

## Result and scope

Actual browser automation exercised the running React/Vite application and FastAPI
backend. The final run passed **44 scenarios, zero failed, zero skipped**, with
zero JavaScript runtime errors and zero unexpected third-party request origins.
This is distinct from the **175 backend** and **26 frontend Node** tests, which
also passed. This phase adds focused fixes rather than a redesign or new product
features. It does not establish production readiness or full accessibility compliance.

## Environment and isolation

- Windows; existing Python 3.14 virtual environment; Node 24.21.0; Vite 8.1.5.
- Installed Google Chrome **140.0.7339.128**, headless, driven by the existing bundled
  Playwright package. No packages or browser binaries installed or upgraded.
- Frontend: `http://127.0.0.1:5175`; API: `http://127.0.0.1:8003`.
- Vite receives `VITE_API_BASE_URL` in its test process. The isolated API receives
  exactly that frontend origin through `ALLOWED_ORIGINS`; production CORS is unchanged.
- `backend/tests/browser_server.py` imports the real app under an account-file read
  interceptor returning an empty account dictionary, suppresses account persistence,
  and mocks provider client construction to raise an unavailable error. It removes
  the provider key from its own environment only. Real account data is never loaded
  or overwritten. Authentication, hashing, sessions and ownership checks remain real.
- Fresh Playwright browser contexts use random disposable synthetic account
  credentials held in memory. No real browser profile or storage was cleared.
- Browser routing permits the two local origins and local blob/data resources only.
  Tests record request paths/errors, never Authorization headers or tokens.
- Synthetic PDF/DOCX fixtures use existing python-docx/pypdf. The fictional resume
  contains two jobs, repeated Experience headings, two projects, a project date,
  punctuation-heavy skills and aliases, education, and conservative rewrite examples.
- QA artifacts are under ignored `test-results/phase51/`: screenshots, downloaded
  TXT reports, browser-generated PDF and JSON results. They are not staged.

The actual frontend default at the start of this phase was `localhost:8000`.
Both READMEs still specified 8001. Documentation now matches the existing 8000
default; the production default itself was not changed.

## Git baseline

Branch was and remains `feature/resumeiq-redesign`. Initial status showed 23 tracked
modified files plus untracked prior-phase modules/tests/docs and `reviewer/`.
The staged diff was empty. Initial branch, status, diff stat and staged stat were
inspected before edits. Previous changes were preserved in place; no stash, reset,
clean, branch operation, commit, push, merge or PR was performed. The overall Git
diff contains earlier phases and must not be interpreted as this phase's file list.

## Executed verification matrix

| Area | Automated result | Real browser result | Scope/notes |
| --- | --- | --- | --- |
| Signup/login | Existing security regressions pass | Pass | Signup, required fields, malformed email, wrong/unknown credentials, login/logout, refresh/back, history |
| Upload | Existing parser/limit tests plus new extraction regressions pass | Pass | PDF/DOCX, empty/corrupt/misleading/oversized files, unexpected MIME, rejected replacement recovery |
| Candidate extraction | Three new regressions pass | Pass | Two jobs and two projects, source ownership, aliases, visible name/orgs, month precision/gap behavior |
| Job matching | Existing skill, experience and Phase 4 suites pass | Pass | Resume-only, alias JD, missing Docker, TXT JD upload; score comes from API |
| Explainable scoring | Existing tests plus print regression pass | Pass | Backend requirements rendered, older analysis fallback, source score displayed |
| Improvement workspace | Existing 28 backend Phase 5 tests pass | Pass | Local generation, AI unavailable, edit/accept/reject/restore, checklist states/counts, session reset |
| Downloads/print | Existing export helpers plus print regression pass | Pass | Both TXT downloads inspected; actual Chromium print PDF rendered and reviewed |
| Responsive layout | Existing CSS/component checks pass | Pass within scope | Authentication and full results at five widths; no document horizontal overflow |
| Security/privacy | 17 security + 9 network-guard tests pass | Pass within scope | Second account denied first account's improvements; no history leakage; 401 removes private UI state |
| Errors/recovery | Existing transport tests pass | Pass | Simulated 503, refused connection, invalid JSON, empty analysis; successful retry |

The 17 security and 9 network-guard tests are subsets of the 175 backend total,
not extra tests. The original 172-test baseline and 25-test frontend baseline were
independently rerun before changes and passed.

## Confirmed defects and minimal fixes

| Defect / severity | Reproduction and root cause | Fix and verification |
| --- | --- | --- |
| Keyboard-inaccessible upload controls / medium | Tab could not focus the clickable resume dropzone; JD picker had the same div-only pattern. | Add button semantics, tab stop, Enter/Space handlers, focus outline and JD text label. Real filechooser events pass for resume Enter and JD Space. |
| Employment description becomes employer / medium | Upload “I maintained FastAPI services.” under a job. The organization keyword `services` matched because action detection did not recognize the first-person prefix. | Check existing action vocabulary after removing initial `I` for header classification only. Original description stays verbatim. Browser and two unit regressions verify activity ownership and real Services Ltd. headers. |
| Project date becomes separate project / medium | Upload a project title followed by a standalone date range. The date qualified as a new heading. | Preserve date as a description of the current project; no new schema or employment duration logic. Browser and unit regression verify two distinct projects. |
| Rejected replacement erases valid UI candidate / medium | Upload valid resume, return to upload, select unsupported file. Candidate and resume ID were cleared before validation. | Keep existing candidate/source until replacement succeeds; disable Continue while uploading. Browser verifies rejected upload permits continuing with the original candidate. |
| Printed limitations omitted / medium | Generate report while limitations disclosure remains closed. CSS display:block did not open native details. | Optional `expandLimitations` prop used only by print report. Actual print and Node regression confirm the content is included. |
| Dark-theme print contrast / medium | Print from dark theme. White report inherited pale headings/list text, with dark surrounding background. | Print-only text variables, light color scheme and white backgrounds. Computed-color browser assertions and visual review pass. Screen themes unchanged. |
| Empty analysis crashes results / medium | Intercept analyze with HTTP 200 and `{"analysis":{}}`. UI advanced and accessed absent fields, causing a runtime error. | Reject missing/non-finite overall score before updating results; show retry error on analysis step. Browser repeats the failure then successfully retries the real API. |
| Setup documentation port mismatch / low | Follow README's 8001 startup with frontend default 8000. | Correct both READMEs to the already configured 8000 default; QA used explicit separate ports. |

Print page-break rules also keep headings with following content and let the long
draft section continue naturally, reducing the observed large blank area. All fixes
are covered by the executed browser scenarios or focused unit regressions.

Two test assumptions were corrected, not application rules: requirement keys are
canonical lowercase, and Jan 2020–Dec 2021 plus Jan 2023–Dec 2023 is **2.83 years**
under the existing month-endpoint policy (34 months), not 3 inclusive years.
No score/date policy was altered to satisfy these tests.

## Files changed in this phase only

| File | Purpose |
| --- | --- |
| `backend/extractor/employment.py` | Correct first-person activity and standalone project-date boundaries. |
| `backend/tests/browser_server.py` | New disposable real-API server with isolated accounts and disabled providers. |
| `backend/tests/browser_fixtures.py` | New reproducible synthetic PDF/DOCX fixture generator. |
| `backend/tests/test_browser_regressions.py` | Three extraction regressions. |
| `frontend/src/App.jsx` | Keyboard upload access, JD label, rejected-upload preservation, empty-analysis recovery. |
| `frontend/src/App.css` | Upload focus visibility and print-only contrast/page breaks. |
| `frontend/src/ExplainableResults.jsx` | Optional expansion of printed limitations. |
| `frontend/src/PrintableReport.jsx` | Enable limitations in print output. |
| `frontend/tests/browser-qa.mjs` | New real-browser suite, isolated contexts, assertions, downloads and evidence output. |
| `frontend/tests/explanation.test.js` | Regression for expanded print limitations. |
| `README.md` | Correct existing default API port and link this report. |
| `frontend/README.md` | Correct existing default API port. |
| `docs/phase5-1-browser-qa.md` | This report. |

## Reproduction commands

From `backend/`, generate fixtures, then start the isolated server in a separate terminal:

```powershell
.venv/Scripts/python.exe tests/browser_fixtures.py
.venv/Scripts/python.exe tests/browser_server.py
```

From `frontend/`, start Vite in another terminal:

```powershell
$env:VITE_API_BASE_URL='http://127.0.0.1:8003'
npm run dev -- --host 127.0.0.1 --port 5175 --strictPort
```

From `frontend/`, point the runner at an existing Playwright package directory and
installed Chrome executable (paths intentionally environment-specific, not embedded):

```powershell
$env:QA_PLAYWRIGHT='<existing playwright package directory>'
$env:QA_BROWSER='<installed Chrome executable>'
node tests/browser-qa.mjs
node --test tests/*.test.js
npm run lint
npm run build
```

Backend verification:

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -q
.venv/Scripts/python.exe -m unittest discover -s tests -p test_security.py -q
.venv/Scripts/python.exe -m unittest discover -s tests -p test_network_guard.py -q
```

Final results: **175/175 backend; 17/17 security; 9/9 network guard; 26/26 frontend;
44/44 real browser**. Lint/build passed without build warnings. Git diff check passed
with only LF-to-CRLF notices. Backend commands used the approved unrestricted runner
for Windows asyncio initialization; all existing test network guards stayed enabled.

## Responsive, accessibility, downloads and print evidence

Authentication and result/improvement pages were exercised at **1440×900, 1366×768,
768×1024, 390×844 and 360×800**. Screenshots were captured and document horizontal
overflow was checked at each viewport. Dark theme switching and persistence passed.
The long result page scrolls normally; controls use native buttons, textareas/selects.
Keyboard checks cover email-to-password Tab order and actual upload filechooser
activation. This is not a complete keyboard-only walkthrough or screen-reader audit.

Downloaded analysis TXT contains the current fictional candidate and server score;
improvement TXT contains source/proposed/current wording, acceptance state and an
unverified-edit notice. Unicode résumé/em-dash text survived. React displayed injected
script-looking draft text as text without execution. Original content remained visible.

Chromium's print renderer produced the actual four-page final report, then Poppler
rendered all pages for visual review. Final pages have readable headings, expanded
limitations, correctly wrapped skill labels and draft text, no overlapping blocks or
clipped content observed for this fixture. Page breaks can still split a draft's fields;
the report remains readable. This is browser print-to-PDF testing, not a new native
PDF product feature or a physical-printer/dialog test.

## Console, network, compatibility and privacy

Final browser run: zero page errors, zero unexpected origins. Console resource errors
correspond to deliberately induced 401/422/503 or connection-refused cases. Cancelled
history requests occur on refresh/logout (AbortController cleanup), not data leaks.
The initial empty-analysis scenario produced one page error; the final run did not.

All seven existing API routes and fields remain. Authentication, ownership, CORS
defaults, upload limits, provider allowlist, matching aliases, thresholds, rounding,
weak-match cap and AI-first selection were not changed. Resume quality remains
10/25/20/45; local job fit 60/25/15%; overall quality/job fit 30/70%.
Correcting extraction can legitimately change a new evaluation's source-derived
completeness score; it does not change formulas. Suggestion edits never rescore.
No live AI requests, credentials, real resumes or real account records were used.

## Limitations and remaining checks

- Chrome only; no Firefox/Safari, real mobile devices, assistive technology or formal
  WCAG/contrast audit. Viewport checks cover authentication/results, not every possible
  intermediate-state/viewport combination.
- Backend tests cover more alias/false-positive, overlap, missing-skills, long-content,
  unsupported-claim and provider-response variants than were repeated in the browser.
  Those unit results are not labelled browser coverage.
- AI unavailability was tested in browser with disabled client construction. Timeout,
  malformed provider output and unsupported claims use existing offline backend tests;
  no live provider quality/latency assessment. Transport timeout is a Node test, not
  a full 45-second browser wait. Session expiry uses a controlled HTTP 401, not elapsed TTL.
- No assertion of complete arbitrary malformed-success-response schema validation;
  the confirmed empty-analysis case is handled. Large/empty checklist behavior has
  component/backend coverage rather than a separate real-browser case.
- No OCR, production deployment, load test, physical printer or durable draft storage
  was added. Existing extraction remains heuristic.
- An approval-review usage limit interrupted an attempted run; after the user asked
  to continue, normal approval succeeded. Test servers were restarted because they
  had stopped during that interruption. This was an environment interruption, not a
  passing test. Final counts refer only to the completed run.

## Cleanup and final Git safety

Only the QA API/Vite processes started for this task are stopped after verification.
Disposable accounts existed only in those processes. Synthetic artifacts are retained
in ignored test-results for review; no user data is deleted. Branch is unchanged;
all prior work, including reviewer files, is preserved. Nothing staged, committed,
pushed or merged. No manifests or lockfiles were changed.

## Final browser scenario ledger

The following list is copied from the final executed JSON result, not a test plan.

- **passed** — Authentication required fields and malformed email
- **passed** — Signup connects to isolated API and opens step 1
- **passed** — Dark theme remains selectable and persistent
- **passed** — Refresh retains authentication without candidate state
- **passed** — Resume upload is keyboard reachable
- **passed** — PDF upload and candidate extraction
- **passed** — Back and continue preserve extracted candidate
- **passed** — Resume-only evaluation displays server score and no JD fit
- **passed** — Generate local suggestions preserves source and score
- **passed** — Accept reject edit and restore are reversible
- **passed** — Checklist complete not-applicable pending and duplicate actions
- **passed** — AI unavailable returns local advice and caches repeated request
- **passed** — Improvement TXT contains original current edits and decisions
- **passed** — Analysis TXT downloads current candidate and server score
- **passed** — Results and improvements viewport 1440x900
- **passed** — Results and improvements viewport 1366x768
- **passed** — Results and improvements viewport 768x1024
- **passed** — Results and improvements viewport 390x844
- **passed** — Results and improvements viewport 360x800
- **passed** — Browser print renders analysis and edited improvement report
- **passed** — Refresh drops session-only drafts but keeps login
- **passed** — DOCX upload and alias JD explanation agree with backend
- **passed** — Old analysis without explanation remains readable
- **passed** — Improvement endpoint failure recovers without losing analysis
- **passed** — Logout removes candidate and drafts; back cannot reveal them
- **passed** — Wrong password and unknown account return safe errors
- **passed** — Login restores authenticated navigation and history
- **passed** — Rejected replacement upload preserves valid candidate
- **passed** — Rejected upload: empty.pdf
- **passed** — Rejected upload: corrupt.pdf
- **passed** — Rejected upload: corrupt.docx
- **passed** — Rejected upload: misleading.pdf
- **passed** — Rejected upload: large.pdf
- **passed** — Valid PDF with unexpected MIME is parsed by content
- **passed** — JD file picker supports keyboard and actual text upload
- **passed** — Invalid JSON and network failure recover generation controls
- **passed** — Server 401 clears session and private drafts
- **passed** — Authentication viewport 1440x900
- **passed** — Authentication viewport 1366x768
- **passed** — Authentication viewport 768x1024
- **passed** — Authentication viewport 390x844
- **passed** — Authentication viewport 360x800
- **passed** — Second UI account cannot access first account improvements
- **passed** — Empty analysis response displays an error and allows retry
