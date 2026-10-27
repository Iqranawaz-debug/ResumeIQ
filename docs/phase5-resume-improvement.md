# Phase 5: resume improvement

## Pipeline and integration decision (before implementation)

Authenticated upload retains a structured candidate, short source evidence and
a resume ID in per-user process memory. Raw documents/full parsed text are not
retained. Analyze evaluates that original candidate, optionally matches a JD,
and adds Phase 4 local requirement explanations. History stores summaries.
The current provider is OpenRouter via the existing OpenAI client (20-second
timeout, no retries). Its allowlist permits skills, education and employment
title/duration/details; projects, organizations and skill evidence are excluded.

Existing recommendations are read-only strings with no draft, checklist or
accept/reject state. The safest integration is a separate authenticated
`POST /api/improvements` action bound to both the resume and latest analysis.
Reusing `/api/analyze` for editing would unnecessarily rescore, call the matcher
and add history entries. The new action will not evaluate or modify scores.
An additive analysis ID protects against stale suggestions after reanalysis.
Draft decisions remain in the active frontend session, not shared storage.

Local conservative wording edits and clarification advice are the baseline.
Optional AI assistance can propose only bounded employment rewrites. Output
outside the locally verifiable edit set is rejected; model claims cannot be
made trustworthy by keyword checks alone. Projects and unretained summary text
are never sent externally. Manual edits always require the user's review.

## Implemented architecture

`evaluator/improvements.py` reads the retained employment/project descriptions,
dates, skills, education and Phase 4 requirement rows. It returns stable source-linked
suggestions, deduplicated checklist items, descriptive feedback and limitations.
It does not parse a second resume, rematch a JD or call the scoring engine.
Weak descriptions receive clarification requests; repetition, long descriptions,
missing contributions and uncertain dates receive review advice. Skills and education
receive presentation/completion advice, without invented qualifications.

Copy edits remove a supported initial first-person pronoun, replace “utilized”
with “used”, shorten “in order to”, or shorten “was responsible for”. Negative,
hypothetical, quoted and obvious instructional passages are excluded from rewriting.
AI output must equal the permitted local transformation of the original text.
Schema, size and unique-index validation reject malformed or unsupported responses.
One invalid provider edit rejects the entire provider response. This is intentionally
more restrictive than keyword checks, but cannot verify the truth of original claims
or guarantee preservation of contextual meaning. Every suggestion requires review.

The engine returns at most 16 suggestions, 24 checklist items and 40 requirement
rows. It examines at most 30 entries per section and 30 descriptions per entry.
Descriptions above 1,200 characters receive splitting advice instead of rewrites.
Checklist limits can omit later job-relevance advice when content issues fill the list.
The UI permits manual drafts up to 2,000 characters. No numeric writing score exists.

## Provider, privacy and fallback

The existing OpenRouter client/model, timeout and zero-retry configuration are reused.
No dependencies, environment variables or credentials were added. Local generation
does not call the provider. The separate explicit AI action can add one completion
request for up to eight eligible employment descriptions per current evaluation.
Results, including unavailable/invalid-output fallback, are cached until reanalysis
or replacement upload. Concurrent duplicate requests return 409.

The original `candidate_payload` allowlist is unchanged. Phase 5 uses a smaller
subset: employment details, with empty skills/education arrays. No JD, whole document,
project descriptions, organization fields or skill-evidence records are sent.
Passages changed by existing contact redaction, containing known organization names,
URLs or selected sensitive-attribute terms are excluded. This is best-effort filtering,
not guaranteed anonymization of arbitrary prose. Project advice stays local.
No actual external provider calls were made during verification; configuration values
were neither exposed nor changed. Missing keys, timeouts, rate limits, empty/malformed
responses and invented claims retain local suggestions and a generic notice without
provider error details. Free-form stronger AI rewrites are intentionally unsupported.

## Synthetic before-and-after examples

| Original | Proposed draft | Basis |
| --- | --- | --- |
| I helped with Python testing. | Helped with Python testing. | Removes first person; keeps assistance level. |
| Utilized SQL for reports. | Used SQL for reports. | Simplifies an existing verb. |
| Built scripts in order to prepare data. | Built scripts to prepare data. | Removes unnecessary wording. |
| I was responsible for report checks. | Responsible for report checks. | Shortens the stated responsibility. |
| I maintained FastAPI services. | Maintained FastAPI services. | Retains the activity and named technology. |

“Worked on Python automation” receives clarification advice, not a claim that the
candidate developed scripts or achieved an outcome. An unsupported Docker requirement
gets conditional advice to add an example only if the user has practical experience;
Docker is never inserted into a draft. Matched skills with quotations need no extra
keyword suggestion. A listed skill without a quotation receives an evidence prompt.
All requirement status and context come from Phase 4's existing rows.

## Frontend and exports

The existing four-step flow and theme remain. Results now include original/proposed
comparisons, reasons, local/AI provenance, editable text, accept/reject/restore and
checklist pending/complete/not-applicable controls with counts. Editing an accepted
draft returns it to pending and marks it unverified. Restore copies the original
wording back into the draft. Accept/reject decisions never mutate the source candidate.
Generation buttons display loading/error/unavailable states. Existing transport
timeouts and abort handling protect against stale responses after reset or logout.

Drafts and checklist decisions remain in React memory. Same-evaluation generation
preserves decisions by stable ID; upload, analysis, logout, expiry, start-over and
reload discard them. They are not added to shared storage, history or localStorage.
TXT export includes source/proposed/current text, decisions, reasons, provenance,
requirements, checklist counts/status and limitations. The existing full-report print
view includes the same content for browser print/save-as-PDF. No standalone PDF file
generator or rewritten resume download is claimed. Rejected drafts remain visible
in reports with their rejected status for auditability.

## API, security and score preservation

All previous routes and response fields remain; successful analyze adds
`analysis.analysis_id`. History retains its existing summary schema. Older analyses
remain displayable but must be analyzed again to generate improvements.
`POST /api/improvements` takes authenticated form fields `resume_id`, `analysis_id`
and optional boolean `use_ai` (false). It returns those IDs and `improvements`.
The response contains version, suggestions, checklist, feedback, requirements,
method, note, limitations and bounded-selection indicator. Source references use
section/entry/detail indices and stable IDs. Wrong-user, stale or missing analysis
requests return 409 without returning another user's data. Authentication failures
remain 401 and invalid form inputs 422. Checks after worker completion discard
results if the resume or analysis changed in flight.

React renders untrusted text as text, not HTML. Tests use synthetic fixtures and
mock providers under the existing network guards. Original Windows guard lifecycle,
DNS/socket/HTTP restrictions and negative controls were not weakened.

SHA-256 comparisons against the saved pre-Phase-4.1 snapshot found **45 preserved
files unchanged**, including all existing scoring, matching, extraction, parser,
auth and provider/privacy modules, dependency manifests/lockfile, and frontend
transport. The only existing application files intentionally changed for Phase 5
are main.py, App.jsx, App.css and PrintableReport.jsx.
Quality weights remain contact 10, skills 25, education 20, experience/details 45.
Local job fit remains 60% skills / 25% experience / 15% education. Overall remains
30% quality / 70% fit. Thresholds, weak-match cap, formulas, rounding, recommendation
bands and AI-first selection are unchanged. Draft generation and all editing actions
do not rescore. Only the existing explicit analysis flow evaluates a candidate.

## Phase 5 file inventory

| File | Change and purpose |
| --- | --- |
| backend/evaluator/improvements.py | New bounded local advice, stable IDs and strict rewrite validation. |
| backend/ai/improvements.py | New optional minimized provider call and fail-closed validation/fallback. |
| backend/main.py | Add analysis IDs, authenticated generation, ownership/stale checks and caching. |
| backend/tests/test_improvements.py | New 28 local, privacy, provider and API regression tests. |
| backend/tests/test_phase4.py | Extend route-contract expectation for the additive endpoint. |
| frontend/src/improvementState.js | New immutable draft/checklist operations and text report formatter. |
| frontend/src/ImprovementWorkspace.jsx | New comparisons, decisions, checklist and TXT export. |
| frontend/src/ImprovementReport.jsx | New printable draft report. |
| frontend/src/App.jsx | Integrate generation, cancellation, session reset and draft state. |
| frontend/src/PrintableReport.jsx | Include current improvement report in existing print output. |
| frontend/src/App.css | Theme-compatible responsive comparison and print styles. |
| frontend/tests/improvements.test.js | New 10 state, rendering, callback and export tests. |
| README.md | Describe features, route, test commands and current limitations. |
| docs/phase5-resume-improvement.md | This implementation and verification report. |

## Verification on Windows / Python 3.14

The baseline was rerun before implementation: 144 backend tests passed. Final checks:

| Command (in backend or frontend as appropriate) | Result |
| --- | --- |
| `.venv/Scripts/python.exe -m unittest discover -s tests -p test_improvements.py -q` | 28 passed |
| `.venv/Scripts/python.exe -m unittest discover -s tests -q` | 172 passed; no failures or expected failures |
| `.venv/Scripts/python.exe -m unittest discover -s tests -p test_security.py -q` | 17 passed (included in 172) |
| `.venv/Scripts/python.exe -m unittest discover -s tests -p test_network_guard.py -q` | 9 passed (included in 172) |
| `node --test tests/*.test.js` | 25 passed: 15 existing + 10 new |
| `npm run lint` | Passed |
| `npm run build` | Passed; no warnings |

Backend tests ran outside the restricted command runner because its Windows internal
asyncio socketpair initialization stalls before test setup. Test network guards stayed
active. No original Windows socket-mock failures returned. Occasional asyncio slow-task
diagnostics were timing messages, not failures. An initial frontend test supplied an
incorrect prop name to the printable component; correcting the fixture produced the
reported passing results without a production-code workaround.

Coverage includes five rewrite examples, vague/strong/long/duplicate/missing content,
Unicode, unsafe prompts, immutable original scores, Phase 4 reuse, provider privacy,
unsupported metrics/technology/qualifications/leadership, invalid responses, cache
reuse, cross-user isolation, stale responses and simultaneous requests. Frontend
tests compile the actual JSX using existing Vite tooling, render with React SSR,
invoke actual callback props, test reducer transitions and mock TXT download DOM APIs.
They are not real-browser interaction, mobile-layout or print-pagination tests.

## Remaining limits and next work

- Existing text-based PDF/DOCX parsing remains; OCR and layout-preserving resume editing
  are absent. Summary source text is unavailable. Education advice cannot establish
  graduation. Complex prose and unsupported languages can need manual review.
- Only narrow copy edits are offered automatically. They cannot fact-check the source.
  User edits are not validated against resume evidence and are explicitly labelled.
- No durable drafts, modified DOCX/PDF resume, version history or automatic rescoring.
  Cached AI fallback is not retried until a new analysis; multiple-worker storage is
  outside the current process-memory design.
- Live AI response quality, browser interaction, visual mobile layout and print page
  breaks remain unverified; no claims of verified hiring suitability are made.
- Suggested next work: browser-level interaction/print QA, then an explicitly approved
  source-preserving editing/storage design and broader evidence-backed rewrite rules.
  Expanding the provider privacy allowlist requires separate authorization.

Branch remains `feature/resumeiq-redesign`. Earlier uncommitted/untracked work,
including unrelated reviewer files, is preserved. No dependencies installed or
upgraded; no secrets or user data modified. Nothing staged, committed, pushed or merged.
