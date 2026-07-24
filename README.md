# ResumeEvaluator (ResumeIQ)

A resume evaluation application with a React frontend and a Python (FastAPI) backend.

## Structure
- backend/: FastAPI app (`main.py`), resume parsing/extraction/evaluation logic
  - parser/: resume parsing modules (PDF/DOCX)
  - extractor/: rule-based extraction logic (fallback)
  - ai/: LLM-powered extraction and job matching, via OpenRouter (optional; falls back to rule-based on any failure)
  - evaluator/: scoring and recommendations
  - matcher/: rule-based job-description matching (fallback)
  - utils/: validators and constants
  - history/: session history handling
- frontend/: React (Vite) app — resume upload UI
- assets/: static assets
- sample_resumes/: sample resumes
- tests/: test files

## Running locally

### Backend
```
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8001
```

#### Optional: enable AI-powered extraction/matching
By default the app uses rule-based (regex/keyword) extraction and matching. To
use an LLM instead (better handling of varied resume formats and semantic
skill matching), set `OPENROUTER_API_KEY` before starting the backend:

```
$env:OPENROUTER_API_KEY = "sk-or-..."   # PowerShell
python -m uvicorn main:app --reload --port 8001
```

Get a key at https://openrouter.ai/settings/keys. The model used
(`backend/ai/openrouter_client.py`) defaults to a free-tier model
(`openai/gpt-oss-20b:free`) so no paid credits are required to try it —
swap in a paid model there for higher-quality extraction. If the key is
missing or a call fails for any reason, the app automatically falls back to
the rule-based path — check `extraction_method` / `job_fit_method` in API
responses to see which path actually ran.

### Frontend
```
cd frontend
npm install
npm run dev
```

The frontend runs on http://localhost:5173 and talks to the backend at http://localhost:8001.

Storage is in-memory only — no database is used.
