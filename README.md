# ResumeEvaluator (ResumeIQ)

A resume evaluation application with a React frontend and a Python (FastAPI) backend.

## Structure
- backend/: FastAPI app (`main.py`), resume parsing/extraction/evaluation logic
  - parser/: resume parsing modules (PDF/DOCX)
  - extractor/: rule-based extraction logic (fallback)
  - ai/: LLM-powered job-description matching, via OpenRouter (optional; falls back to rule-based on any failure)
  - evaluator/: scoring and recommendations
  - matcher/: rule-based job-description matching (fallback)
  - auth/: verifies Supabase-issued access tokens (see Authentication below)
  - utils/: validators and constants
- frontend/: React (Vite) app — resume upload UI
- assets/: static assets
- sample_resumes/: sample resumes
- tests/: test files

## Authentication (required)

Signup and login are handled by [Supabase](https://supabase.com) — the
backend only verifies the access token Supabase issues. You need a free
Supabase project before the app will run:

1. Create a project at https://supabase.com/dashboard.
2. In **Authentication → Providers**, make sure Email is enabled (and
   disable "Confirm email" for easier local testing).
3. In **Project Settings → API**, copy the **Project URL** and **anon
   public** key.

Set them for both the backend and frontend:

```
frontend/.env
  VITE_SUPABASE_URL=https://xxxx.supabase.co
  VITE_SUPABASE_ANON_KEY=eyJ...
```

```
$env:SUPABASE_URL = "https://xxxx.supabase.co"      # PowerShell, backend
$env:SUPABASE_ANON_KEY = "eyJ..."
```

## Running locally

### Backend
```
cd backend
pip install -r requirements.txt
$env:SUPABASE_URL = "https://xxxx.supabase.co"      # PowerShell
$env:SUPABASE_ANON_KEY = "eyJ..."
python -m uvicorn main:app --reload --port 8001
```

#### Optional: enable AI-powered job-description matching
Resume upload always uses rule-based extraction (fast, no external calls).
Job-description matching (the "Add Job Description" step) uses rule-based
matching by default too. To use an LLM instead for that step (semantic skill
matching, e.g. recognizing "infrastructure as code" satisfies a "Terraform"
requirement, plus JD-specific strengths/suggestions), set
`OPENROUTER_API_KEY` before starting the backend:

```
$env:OPENROUTER_API_KEY = "sk-or-..."   # PowerShell
python -m uvicorn main:app --reload --port 8001
```

Get a key at https://openrouter.ai/settings/keys. The model used
(`backend/ai/openrouter_client.py`) defaults to a free-tier model
(`openai/gpt-oss-20b:free`) so no paid credits are required to try it. If the
key is missing or the call fails for any reason, the app automatically falls
back to the rule-based matcher — check `job_fit_method` (and `job_fit_model`)
in the `/api/analyze` response to see which path, and which model, actually
ran.

To try a different LLM (e.g. to compare providers), set `OPENROUTER_MODEL`
to any OpenRouter model slug before starting the backend — no code changes
needed:

```
$env:OPENROUTER_MODEL = "google/gemini-2.0-flash-001"   # PowerShell
python -m uvicorn main:app --reload --port 8001
```

Note: only model slugs ending in `:free` don't consume OpenRouter credit.

### Frontend
```
cd frontend
npm install
npm run dev
```

The frontend runs on http://localhost:5173 and talks to the backend at http://localhost:8001.

User accounts live in Supabase. Resume/evaluation data stays in-memory in
the backend only — no app database is used.
