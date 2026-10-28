# Phase 6 — Recruiter workflow: notes and tags, export, pipeline board

Completed: 28 October 2026 (Asia/Karachi).

## Result and scope

Three features were added to the recruiter workspace, one commit each:

| Commit | Feature |
| --- | --- |
| `feat: private notes and tags for recruiter candidates` | Per-candidate notes (create, edit, delete) and tags, a tag filter and search over notes and tags |
| `feat: export recruiter comparisons to CSV and PDF` | CSV export built on the backend; PDF via the existing browser print pattern |
| `feat: pipeline board view for recruiter review statuses` | A board with one column per existing review status, drag and drop plus a keyboard "Move to" menu |

Verification at the end of this phase: **299 backend tests** and **72 frontend Node tests** pass;
`oxlint`, `vite build` and `pip check` are clean. Each feature was also exercised end to end in a
real browser (headless Microsoft Edge driven over the DevTools protocol against an isolated copy of
the API and the Vite dev server). The Playwright script `frontend/tests/browser-recruiter-workflow.mjs`
was written for these flows but **not run** here, because no Playwright package is installed on the
verification machine.

The human-review policy is unchanged: no automatic ranking, shortlisting or rejection. Filters,
exports and the board never reorder candidates by score; lists keep upload order and comparisons
and exports keep the order the reviewer selected.

## Data model changes (`backend/recruiter.py`)

Each candidate record gained two fields. They live on the record, **not** on `record['candidate']`
(the extracted resume data), which is the only source `ai/privacy.py` uses to build AI requests.

| Field | Shape | Notes |
| --- | --- | --- |
| `notes` | list of `{id, text, created_at, updated_at}` | Creation order. `updated_at` is `null` until edited. IDs are random URL-safe tokens. |
| `tags` | list of strings | Insertion order. Unique case-insensitively; re-adding keeps the first spelling. |

Candidate summaries (workspace detail, candidate detail, comparison rows) now include `tags`, `notes`,
and `matched_skill_names` / `missing_skill_names` (display spellings such as "AWS" and "Go" used by
exports; the lowercase keys remain for filtering). Records created before this phase have no fields;
endpoints treat missing fields as empty lists. With SQLite persistence enabled
(`RESUMEIQ_DB_PATH`), notes and tags are saved with the rest of the workspace and follow the same
retention and deletion rules.

## API endpoints

All require `Authorization: Bearer <token>` and are scoped to the owner's workspace. Any workspace,
candidate, note or tag that the caller does not own returns **404**; requests without a valid token
return **401**. (A separate 403 never applies: other users' resources are not visible at all.)

| Method and path | Body | Result |
| --- | --- | --- |
| `POST /api/workspaces/{group_id}/candidates/{candidate_id}/notes` | `{"text"}` | 201, the new note |
| `PATCH /api/workspaces/{group_id}/candidates/{candidate_id}/notes/{note_id}` | `{"text"}` | The edited note |
| `DELETE /api/workspaces/{group_id}/candidates/{candidate_id}/notes/{note_id}` | — | `{"message"}` |
| `POST /api/workspaces/{group_id}/candidates/{candidate_id}/tags` | `{"tag"}` | `{"tags": [...]}` (a duplicate is a no-op) |
| `DELETE /api/workspaces/{group_id}/candidates/{candidate_id}/tags/{tag}` | — | `{"tags": [...]}`; tag matched case-insensitively |
| `POST /api/workspaces/{group_id}/comparison/csv` | `{"candidate_ids", "version", "include_notes": false}` | `{"filename", "content", "include_notes"}` |

`GET /api/workspaces` now also returns the annotation limits (`note_chars`, `notes`, `tags`,
`tag_chars`) so the frontend validates with the server's values. The board uses the existing
`PATCH .../review` endpoint, including its revision check; no new status values were added.

## Limits and validation

Configured in `backend/utils/limits.py` in the existing environment-variable style:

| Setting | Default | Enforcement |
| --- | --- | --- |
| `MAX_NOTE_CHARS` | 2,000 | Checked after cleaning; 422 when exceeded or empty |
| `MAX_NOTES_PER_CANDIDATE` | 100 | 409 when full |
| `MAX_TAGS_PER_CANDIDATE` | 10 | 409 when full (re-adding an existing tag still succeeds) |
| `MAX_TAG_CHARS` | 30 | Tags must be 1–30 characters after cleaning; 422 otherwise |

Cleaning (`backend/utils/text.py`): Unicode NFKC normalization, removal of control characters,
zero-width characters and bidirectional override/isolate marks, whitespace trimming (tags also
collapse internal whitespace; notes keep at most one blank line between paragraphs). Lengths are
checked after cleaning, so invisible characters cannot pad past a limit. Pydantic schemas reject
extra fields and bound raw input before cleaning. Tags may contain letters, numbers, spaces and
`+ # . & ' - _`, and must start with a letter or number; there is no slash, so a tag is always a
safe single URL path segment. `body_limit.py` already caps total request size and was not changed.

Text is stored as plain text and rendered as React text nodes (escaped). There is no
`dangerouslySetInnerHTML`; tests confirm that HTML in notes and names is displayed literally.

## Export

**Choice:** CSV is generated on the backend so formula-injection protection and wording come from
the same records as the comparison and are tested in Python; PDF uses the existing print-report
pattern on the frontend, so no PDF library was added.

- **CSV columns:** Candidate, Review status, Tags, Matched skills, Missing skills, Years of experience,
  Score, plus Notes only when requested. Score uses the UI wording, e.g. `80 / 100 (Local score)` or
  `75 / 100 (AI score)`; unscored rows read `Not scored yet`. Every cell is quoted, and any cell
  beginning with `=`, `+`, `-`, `@`, tab or carriage return is prefixed with `'`. The browser saves the
  file with a UTF-8 byte-order mark so spreadsheet apps read accented names correctly.
- **PDF:** a print-only `ComparisonReport` is mounted outside the app shell; while
  `body[data-print="comparison"]` is set, everything else is hidden. It includes the job title and
  version, generation date, each candidate (status, score, years, tags, matched and missing skills),
  the full score explanation, and the footer **"Decision support only. Human review required."**
  The report is removed after the browser's `afterprint` event.
- **Notes are excluded by default** from both exports; the "Include private notes" checkbox opts in.
- Both buttons show loading text and an inline error (for example a 409 when the job description
  changed and candidates must be re-analyzed).

## Pipeline board

- A List / Board toggle in the Candidates card. Columns are exactly `Not Reviewed`, `Under Review`,
  `Shortlisted`, `Not Selected`, in that order.
- Cards show the name, file name, up to three tags (`+N` for more) and a neutral evidence line such
  as `5 matched · 4 not evidenced · Python, PostgreSQL, Docker`. **No scores are shown on cards**, so
  the board does not read as a ranking.
- Cards move by HTML5 drag and drop or by the "Move {name} to" select on each card (keyboard and
  touch accessible). Both persist through the existing review endpoint.
- Filters apply to the board as well. Within a column, cards keep upload order.
- Columns scroll horizontally inside the board on small screens; the page itself does not scroll
  sideways. Colors use the shared theme tokens, so dark mode works without extra rules.

## Privacy notes

- Notes and tags are private to the owning account and visible only through owner-scoped endpoints.
- They are **never sent to an AI provider**: they are stored outside `record['candidate']`, and a
  backend test asserts that neither note nor tag text appears in the analysis input or the AI payload.
- The Privacy & data page now states that workspaces include private notes and tags, and that notes
  and tags are never sent to AI. Deletion and inactivity expiry remove them with the workspace.

## How to test

```powershell
cd backend
.venv/Scripts/python.exe -m unittest discover -s tests
```

New suites: `tests/test_notes_tags.py` (validation limits, cleaning, ownership 404/401, privacy,
persistence hook, no reordering or automatic status changes) and `tests/test_export.py` (formula
neutralization, wording, notes opt-in, selection order, ownership, stale versions).

```powershell
cd frontend
node --test tests/*.test.js
npm run lint
npm run build
```

New suites: `tests/recruiter-annotations.test.js` (tag and note validation, filters, immutable
updates, API functions, notes panel rendering), `tests/recruiter-export.test.js` (score wording,
PDF report content, notes opt-in, CSV request) and `tests/recruiter-board.test.js` (status columns,
upload order, card helpers, Move to menu, drag and drop, busy state). `tests/load-component.mjs` now
resolves extensionless `.js` imports.

Browser journeys (requires a Playwright package and Chrome, as in Phase 5.1):

```powershell
cd backend
.venv/Scripts/python.exe tests/browser_server.py
```

```powershell
cd frontend
$env:VITE_API_BASE_URL='http://127.0.0.1:8003'
npm run dev -- --host 127.0.0.1 --port 5175 --strictPort
```

```powershell
cd frontend
$env:QA_PLAYWRIGHT='<existing playwright package directory>'
$env:QA_BROWSER='<installed Chrome executable>'
node tests/browser-recruiter-workflow.mjs
```

## Known limitations

- **The Playwright scripts were not run** in this phase (no Playwright installed). Two pre-existing
  issues will affect them and were deliberately left unfixed:
  - `backend/tests/browser_server.py` patches `ai.improvements.get_client`, but `ai/improvements.py`
    was removed in an earlier review round, so the QA server fails to start. It also clears only the
    old `OPENROUTER_API_KEY` name, not `AI_API_KEY`.
  - `frontend/tests/browser-recruiter.mjs` asserts the text "server memory only", which the earlier
    Recruitment page redesign replaced.
- Drag and drop uses the HTML5 API, which mobile browsers do not support; the "Move to" menu covers
  touch devices.
- The candidate list and workspace detail include every note's text so search works client-side.
  With the maximum limits (20 candidates × 100 notes × 2,000 characters) that payload can reach a few
  megabytes; typical use is far smaller.
- The PDF relies on the browser's print dialog ("Save as PDF"); page breaks and margins vary by browser.
- CSV is returned inside JSON rather than as a `text/csv` response, so it is downloaded through the app
  rather than by opening the endpoint URL directly.
- Name extraction (pre-existing) does not treat a first line such as `=Formula Person` as a name and
  may fall back to a heading; exports neutralize whatever value is stored.
