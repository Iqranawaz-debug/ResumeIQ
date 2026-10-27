# ResumeIQ

ResumeIQ is a recruiter-oriented resume review prototype built with React and FastAPI. Its workflow uploads a resume, displays extracted information, optionally accepts a job description, and presents an indicative evaluation. Scores are heuristics, not official ATS scores or verified hiring probabilities.

## Existing functionality

- Local account signup, login, and logout; no Supabase integration.
- PDF/DOCX resume upload with a 10 MB application limit.
- Rule-based extraction of contact information, skills, education, and experience.
- Local skill categorization and optional AI job matching, with a local fallback.
- Job descriptions supplied as text or PDF/DOCX/TXT files.
- Resume-only scoring, matched/missing skills, suggestions, and interview questions.
- Five recent evaluation summaries per user in process memory; name search.
- Light/dark themes, TXT report download, and browser print/save-as-PDF.
- Conservative local resume wording suggestions, editable comparisons, and an interactive improvement checklist with TXT/print export.

Extracted information remains read-only. Improvement drafts are editable in the active session and never change the original candidate or score. OCR, durable analysis history, password recovery, email verification, team authorization, and batch uploads are not implemented.

## Stack and runtime requirements

Frontend: React 19, Vite 8, plain CSS, Oxlint. Backend: FastAPI, Uvicorn, python-multipart, python-docx, pypdf, and the OpenAI SDK configured for OpenRouter. Tests use standard-library unittest; no extra test framework.

Verified on Windows with Python **3.14.3**, Node **24.21.0**, and npm **11.19.0**. Locked frontend tools require Node `^20.19.0 || >=22.12.0`. Backend source uses Python 3.10+ syntax; other Python/platform combinations have not been verified. Use the tested version for this baseline.

`frontend/package-lock.json` is the existing npm lockfile. `backend/requirements.txt` remains unpinned. The new `backend/constraints-baseline.txt` records exact versions resolved from that manifest in the isolated Windows/Python 3.14 environment. It is a version snapshot, not a hash-verified or cross-platform lockfile. Platform-specific dependencies elsewhere may differ. Pydantic is imported directly but currently supplied transitively by FastAPI/OpenAI; its tested version is captured in the constraints.

## Structure

```text
backend/
  main.py                     API setup and routes
  auth/                       Local accounts and sessions
  parser/                     PDF/DOCX/text parsing
  extractor/                  Rule-based candidate extraction
  evaluator/                  Scoring and recommendations
  matcher/                    Local job matching
  ai/                         OpenRouter adapters and schemas
  utils/                      Validation and skill vocabulary
  tests/                      Synthetic baseline/known-defect tests
  requirements.txt
  constraints-baseline.txt
frontend/
  src/                        App, auth, report, branding, themes, CSS
  public/                     Static assets
  package.json
  package-lock.json
  vite.config.js
docs/                         Baseline verification report
```

`backend/data/users.json` is created when accounts are saved and is ignored by Git. It is not a test fixture. Do not commit real resumes or account records.

## Installation and startup

PowerShell commands below start at the repository root. No API key is required for local processing.

### Backend

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt -c backend/constraints-baseline.txt
backend/.venv/Scripts/python.exe -m pip check
cd backend
.venv/Scripts/python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

API: `http://localhost:8000`; interactive API docs: `http://localhost:8000/docs`. Run Uvicorn from `backend/` because imports use that root. On macOS/Linux, use `python3` to create the environment and `.venv/bin/python` instead of `.venv/Scripts/python.exe`; those platforms are unverified in this baseline.

### Frontend

In another terminal, from the repository root:

```powershell
cd frontend
npm ci
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Open `http://localhost:5173`, the default allowed origin. `npm ci` installs the existing lockfile without a dependency update.

## Configuration

| Variable | Location | Default / purpose |
| --- | --- | --- |
| `VITE_API_BASE_URL` | Frontend environment or `frontend/.env.local` | `http://localhost:8000`; omit trailing slash |
| `ALLOWED_ORIGINS` | Backend process environment | `http://localhost:5173`; comma-separated browser origins |
| `OPENROUTER_API_KEY` | Backend process environment only | Optional secret; absence triggers local fallback |
| `OPENROUTER_MODEL` | Backend process environment | Code default `openai/gpt-oss-20b:free`; availability/pricing not verified |

No Supabase variables are consumed. Backend code does not automatically load `.env`; set process variables before startup or explicitly use Uvicorn's `--env-file` with a private ignored file. Never put secrets in `VITE_*` values: they become public browser configuration. Restart/rebuild after changing configuration.

CORS must match scheme, host, and port exactly. Browsing at `127.0.0.1` instead of `localhost` needs a matching allowed origin. Vite preview normally uses port 4173, which also needs explicit CORS configuration. No Vite API proxy is configured.

## Authentication, storage, and AI processing

Accounts use local salted PBKDF2 password hashes plus optional profile metadata in `backend/data/users.json`. Writes are atomic (temp file + replace); a corrupt file stops startup instead of being treated as empty. Sessions are opaque tokens held in backend memory and stored in browser localStorage. No external identity provider is used. Restarting the backend invalidates sessions and loses resumes/history.

Resume bytes and full parsed text are processed transiently and are not kept in the validated-resume store. Extracted candidates, bounded evidence quotations and evaluation results remain in process memory until replacement or process exit. Logout removes a token but does **not** erase stored resumes/history. There is no retention timer or deletion endpoint.

Uploads extract and categorize skills locally. AI job matching is opt-in per analysis (`use_ai=true`, the "Use AI job matching" checkbox); with an OpenRouter key configured and the option selected, JD matching sends only skills, education and employment title/duration/details, with best-effort contact redaction, plus the JD. Organizations, projects and evidence quotations are excluded from the provider payload. Exceptions fall back locally. The AI extraction module is unused. Redaction is not guaranteed anonymization.

Phase 4 adds local score explanations, alias matching, requirement context and short source quotations. The existing AI-first score selection is preserved; its unverifiable judgments are labelled separately from local evidence checks. See [Phase 4 implementation and verification](docs/phase4-explainable-matching.md) for exact formulas, privacy limits, tests and known issues.

Phase 5 generates local advice after analysis; no improvement content is sent to a provider. (An earlier AI copy-edit step was removed because its validator only accepted output identical to the local rewrite.) Cached results avoid regenerating advice for the same evaluation. Manual edits require review. Drafts reset on upload, analysis, logout, start-over or reload. See [Phase 5 implementation and verification](docs/phase5-resume-improvement.md).

## API

| Method/path | Behavior |
| --- | --- |
| `POST /api/signup` | JSON email/password, optional full_name/company; returns token |
| `POST /api/login` | JSON email/password; returns token |
| `POST /api/logout` | Invalidates supplied bearer token |
| `POST /api/upload` | Authenticated multipart `file`; stores latest resume |
| `GET /api/history` | Authenticated; up to five summary entries |
| `POST /api/analyze` | Authenticated; current `resume_id`, optional form `job_description` or multipart `file`, optional `use_ai=false`; returns additive `analysis.analysis_id` |
| `POST /api/improvements` | Authenticated form `resume_id`, `analysis_id`; returns cached local draft advice without rescoring |

Protected requests use `Authorization: Bearer <token>`. Analyze checks the submitted ID against the latest stored resume for the user. Improvements also require the current analysis ID; stale requests return 409. Responses include extraction/categorization or job-fit method/model metadata; the UI does not display all of it.

## Tests and validation

From `backend/`:

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe -m pip check
```

Tests use synthetic data and in-memory PDF/DOCX fixtures. AI calls are mocked; no credentials are needed. Account storage is isolated and tests do not modify user data. The current backend suite passes 219 tests without expected failures. Phase 5 adds 28 tests in `test_improvements.py`. Security and network-guard suites preserve the Windows asyncio isolation fixes.

From `frontend/`:

```powershell
node --test tests/*.test.js
npm run lint
npm run build
npm run preview
```

The frontend suite has 35 tests, including draft state, component rendering, event callbacks and exports. Build output goes to ignored `frontend/dist/`. Preview is for local validation, not production hosting. See [Phase 1 verification](docs/phase-1-baseline.md) for historical dependency findings and the Phase 5 report for current verification.

## Current limitations

- Extraction remains heuristic with a bounded skill vocabulary; complex layouts, ambiguous dates and scanned PDFs can lose information.
- Scores are indicative heuristics and provider judgments are not proof of suitability or proficiency.
- Account storage and process-memory resumes/history are unsuitable for a distributed production deployment.
- Provider redaction is best effort, not guaranteed anonymization. The configured 20-second provider timeout is not a guaranteed total deadline.
- Local skill scoring counts skills listed only under preferred/nice-to-have headings at half weight. Required-years detection ignores company/benefit durations such as "founded 25 years ago".
- Improvement rewriting deliberately supports a narrow set of copy edits. Unsupported claims produce fallback/clarification; professional summary text is not retained for rewriting.
- Drafts are session-only; exports are advice reports, not rewritten PDF/DOCX resumes. Print-to-PDF uses the browser dialog.
- No production deployment configuration or health endpoint exists. Phase 5 tests do not constitute live browser/mobile or print-pagination validation.

Earlier phase reports describe their historical scope; the Phase 5 report records the current implementation and verification.

Phase 5.1 real-browser QA: 44 browser scenarios, 175 backend tests and 26 frontend tests passed. See [browser QA and stabilization](docs/phase5-1-browser-qa.md) for fixes, reproduction commands and coverage limits.
