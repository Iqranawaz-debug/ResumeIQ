# ResumeIQ

ResumeIQ is an explainable resume evaluation tool built with React and FastAPI. Upload a resume, optionally add a job description, and get an evidence-based review: requirement-by-requirement matching with source quotes, a transparent score breakdown, honest improvement suggestions, interview preparation, and document readability checks.

Scores are indicative heuristics, not official ATS scores or hiring probabilities. Every view separates **evidence found in the resume** from **inference**, and AI is always optional.

## Highlights

- **Requirement review**: each job-description requirement is marked *Matched*, *Partial*, *Not evidenced* or *Can't assess*, with a reason, an evidence/inference label and a short quote from the resume. Company and benefits text is ignored. Display-only: it never changes the score.
- **Explainable scoring**: the exact formula, component points and weights; preferred-only skills count half; a weak-fit cap stops a polished resume from rescuing the wrong role.
- **What would change this score**: re-runs the same scoring rules on hypothetical edits ("Show your Kubernetes experience: +12 job fit"), always conditional on being true.
- **Improvement assistant**: flags weak openings, passive voice, missing outcomes and long bullets. Optional AI rewrites are kept only if a grounding validator confirms they add no new numbers, tools, names, responsibility level or content; bracketed placeholders must be replaced before a draft can be accepted.
- **Document readability**: image-only PDF pages, contact details hidden in DOCX headers/footers, text boxes, tables, icon-font glyphs, out-of-order text, unrecognized headings and unreadable dates, each with a fix. Worded as possible risks, never as ATS guarantees.
- **Reliable AI**: the AI job-fit score (when requested) stays the main score with the local score always shown beside it; AI-matched skills are labelled *found in resume* or *inferred*; malformed output is retried once; any fallback is shown in a banner.
- **Resume versions**: analyze a revised resume against the same job and compare scores, skills added/removed and requirement status changes.
- **Recruiter workspace**: per-job workspaces, batch upload of up to 5 resumes, review statuses with an audit trail, and side-by-side comparison with no automatic ranking.
- **Privacy controls**: a Privacy & data page shows exactly what is stored and what AI calls send, with one-click deletion and automatic expiry of inactive data.
- **One-click demo**: "Try a fictional sample" loads a bundled sample resume and job description through the real pipeline.
- Light/dark themes, keyboard-accessible tabs, responsive layout, TXT summary and print/PDF report.

## Quick start

### Docker (production-like)

```powershell
copy .env.example .env
docker compose up --build
```

Open `http://localhost:8080` (API on `http://localhost:8000`, health at `/api/health`). Compose enables SQLite persistence in a named volume. The Docker files have not been built in the verification environment for this release; see [Known limitations](#known-limitations).

### Local development

Verified on Windows with Python **3.14.3**, Node **24.21.0** and npm **11.19.0**. Commands start at the repository root.

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt -c backend/constraints-baseline.txt
cd backend
.venv/Scripts/python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
cd frontend
npm ci
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Open `http://localhost:5173`, create a local account, then choose **Try a fictional sample** to see every feature without your own resume. No API key is needed; AI features stay off until a key is configured and you opt in.

## Configuration

All values are optional. See [.env.example](.env.example).

| Variable | Default / purpose |
| --- | --- |
| `OPENROUTER_API_KEY` | Enables opt-in AI job matching and AI wording suggestions. Backend only; never put secrets in `VITE_*` values. |
| `OPENROUTER_MODEL` | `openai/gpt-oss-20b:free` |
| `ALLOWED_ORIGINS` | `http://localhost:5173`; comma-separated, exact scheme/host/port |
| `RESUMEIQ_DB_PATH` | Empty = working data in memory only. Set a file path to persist it in SQLite. |
| `DATA_RETENTION_SECONDS` | `7200`; inactive users' working data is erased after this period |
| `SESSION_TTL_SECONDS` | `3600` |
| `VITE_API_BASE_URL` | Frontend build setting; `http://localhost:8000` |
| `MAX_RESUME_BYTES`, `MAX_JD_BYTES`, `MAX_TEXT_CHARS`, `MAX_PDF_PAGES`, ... | Resource limits (see `backend/utils/limits.py`) |

The backend does not load `.env` by itself; Docker Compose passes it, or use Uvicorn's `--env-file`.

## Privacy and data handling

- Uploaded files are parsed and discarded. Extracted fields, analyses, history, version snapshots (scores, skills and requirement statuses only) and workspaces are kept in memory, or in SQLite when `RESUMEIQ_DB_PATH` is set.
- Working data is erased after `DATA_RETENTION_SECONDS` of inactivity, on request (`DELETE /api/me/data` or the Privacy page), and on restart when persistence is off.
- Accounts are stored locally in `backend/data/users.json` with salted PBKDF2 hashes; writes are atomic and a corrupt file stops startup rather than wiping accounts. Sessions are in memory, so a restart requires signing in again.
- AI is used only when the user ticks an AI option. Job matching sends skills, education and employment titles/dates/descriptions with best-effort contact redaction, plus the job description. Wording suggestions send only flagged employment bullets containing no names, organizations, contact details or sensitive attributes. Projects, evidence quotations and files are never sent. Redaction is best effort, not anonymization.

## Architecture

```text
backend/
  main.py              API routes, retention, persistence wiring
  recruiter.py         Recruiter workspaces router
  samples.py           Bundled fictional demo resume and job description
  auth/                Local accounts and sessions
  parser/              PDF/DOCX/text parsing with layout stats
  extractor/           Rule-based extraction (contact, skills, experience, projects, certifications, evidence)
  matcher/             Local job matching and requirement-line review
  evaluator/           Scoring, explanation, score impacts, document checks, improvements, versions
  ai/                  OpenRouter adapters: job matching, grounded rewrites, privacy filtering
  utils/               Limits, upload validation, skills vocabulary, SQLite persistence
  tests/               Synthetic unittest suites (no network, no real data)
  Dockerfile
frontend/
  src/                 App shell, results dashboard and components, recruiter workspace, styles
  tests/               node:test component and state tests; Playwright browser QA script
  Dockerfile, nginx.conf
docker-compose.yml, .env.example, .github/workflows/ci.yml
docs/                  Phase reports and verification notes
```

Business logic lives in the backend; the frontend renders backend results without recomputing scores (`resultsModel.js` holds only presentation helpers).

## API

| Method/path | Behavior |
| --- | --- |
| `POST /api/signup`, `/api/login`, `/api/logout` | Local accounts; bearer tokens |
| `POST /api/upload` | Multipart `file` (PDF/DOCX); extraction, categorization and readability checks |
| `POST /api/upload/sample` | Loads the bundled fictional resume; returns a sample job description |
| `POST /api/analyze` | `resume_id`, optional `job_description` text or `file`, optional `use_ai`; returns analysis, history, versions and version comparison |
| `POST /api/improvements` | `resume_id`, `analysis_id`, optional `use_ai` for grounded AI wording suggestions; cached, never rescoring |
| `GET /api/history`, `GET /api/versions` | Recent evaluations; version snapshots and comparison |
| `GET /api/me/data`, `DELETE /api/me/data` | What is stored for the account; erase it |
| `GET /api/health` | Liveness and storage mode (no user data) |
| `/api/workspaces/...` | Recruiter workspaces, batch uploads, review statuses, comparison |

Interactive docs: `http://localhost:8000/docs`. Stale `resume_id`/`analysis_id`/workspace versions return 409.

## Tests and validation

```powershell
cd backend
.venv/Scripts/python.exe -m unittest discover -s tests
.venv/Scripts/python.exe -m pip check
```

```powershell
cd frontend
node --test tests/*.test.js
npm run lint
npm run build
```

Current results: **270 backend tests** and **47 frontend tests** pass; lint, build and `pip check` are clean. Tests use synthetic data, mock every AI call and block network access. GitHub Actions runs both suites on pushes and pull requests (`.github/workflows/ci.yml`). `frontend/tests/browser-qa.mjs` is a Playwright scenario script that needs Playwright installed separately.

## Known limitations

- Extraction is rule-based with a bounded skill vocabulary; complex layouts, unusual headings and scanned PDFs (no OCR) can lose information.
- Requirement statuses based on related skills or similar wording are inferences; certification validity and degree field/completion are not verified.
- The rewrite validator is intentionally strict and may reject useful AI output; it still permits plain verb changes, so every draft needs human review.
- Sessions live in process memory and the API runs a single worker; a restart signs users out (persisted working data remains when SQLite is enabled).
- The Docker images and CI workflow were written for this release but not built or run in the verification environment; the Playwright script was updated but not run.
- Exports are reports, not rewritten resume files; print-to-PDF uses the browser dialog.

Historical phase reports live in [docs/](docs/).
