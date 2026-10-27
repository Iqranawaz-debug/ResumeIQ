import os
import secrets
from starlette.concurrency import run_in_threadpool
from utils import limits
from utils.upload import read_upload
from utils.body_limit import BodyLimitMiddleware
from datetime import datetime

from fastapi import Depends, FastAPI, Form, Header, HTTPException, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from auth.auth import (
    AuthError,
    allow_login,
    normalize_email,
    LOGIN_WINDOW,
    create_session,
    create_user,
    destroy_session,
    get_email_from_token,
    verify_user,
)
from auth.schemas import LoginRequest, SignupRequest
from evaluator.analyzer import analyze_resume_for_job
from evaluator.improvements import generate_improvements
from extractor.extractor import extract_candidate_info
from parser.document_parser import parse_document
from parser.resume_parser import parse_resume
from utils.resume_checker import looks_like_resume
from utils.candidate_processing import process_resume
from recruiter import create_router

# Comma-separated list, e.g. "https://myapp.vercel.app,http://localhost:5173"
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

app = FastAPI(title="ResumeIQ API")
app.add_middleware(BodyLimitMiddleware)


@app.exception_handler(RequestValidationError)
async def invalid_request(request, exc):
    # Pydantic's default detail can echo supplied credentials/document fields.
    return JSONResponse({"detail": "Invalid or missing request fields."}, status_code=422)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage, keyed per logged-in user's email (no database required).
validated_resumes: dict = {}
evaluation_histories: dict = {}
upload_versions: dict = {}
MAX_HISTORY = 5


def require_user(authorization: str = Header(default="")) -> str:
    token = authorization.removeprefix("Bearer ").strip()
    email = get_email_from_token(token) if token else None
    if not email:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return email


@app.post("/api/signup")
async def signup(payload: SignupRequest):
    email = normalize_email(payload.email)
    try:
        create_user(email, payload.password, payload.full_name, payload.company)
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    token = create_session(email)
    return {"token": token, "username": email}


@app.post("/api/login")
async def login(payload: LoginRequest, request: Request):
    if not allow_login(request.client.host if request.client else "unknown"):
        raise HTTPException(429, "Too many login attempts. Try again later.", headers={"Retry-After": str(LOGIN_WINDOW)})
    email = normalize_email(payload.email)
    if not verify_user(email, payload.password):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token = create_session(email)
    return {"token": token, "username": email}


@app.post("/api/logout")
async def logout(authorization: str = Header(default="")):
    token = authorization.removeprefix("Bearer ").strip()
    if token:
        destroy_session(token)
    return {"message": "Logged out."}


@app.post("/api/upload")
async def upload_resume(
    file: UploadFile = File(...), username: str = Depends(require_user)
):
    upload_version = secrets.token_urlsafe(16)
    upload_versions[username] = upload_version
    content = await read_upload(file, ("pdf", "docx"), limits.RESUME_BYTES)

    # Basic extraction/categorization is deterministic and never calls a provider.
    candidate = await run_in_threadpool(process_resume, file.filename, content,
                                        parse_resume, looks_like_resume, extract_candidate_info)
    extraction_method = "rule-based"
    extraction_model = None
    categorization_method = "rule-based"
    categorization_model = None
    processing_note = "Skills extracted and categorized locally."

    if upload_versions.get(username) != upload_version:
        raise HTTPException(409, "A newer upload has started. Please use the latest upload.")
    resume_id = secrets.token_urlsafe(16)
    validated_resumes[username] = {
        "resume_id": resume_id,
        "filename": file.filename,
        "content_type": file.content_type,
        "size": len(content),
        "candidate": candidate,
        "extraction_method": extraction_method,
        "extraction_model": extraction_model,
        "categorization_method": categorization_method,
        "categorization_model": categorization_model,
    }

    return {
        "resume_id": resume_id,
        "processing_note": processing_note,
        "filename": file.filename,
        "size": len(content),
        "message": f"'{file.filename}' uploaded and validated successfully.",
        "candidate": candidate,
        "extraction_method": extraction_method,
        "extraction_model": extraction_model,
        "categorization_method": categorization_method,
        "categorization_model": categorization_model,
    }


@app.get("/api/history")
async def get_history(username: str = Depends(require_user)):
    return {"history": evaluation_histories.get(username, [])}


@app.post("/api/analyze")
async def analyze_resume(
    job_description: str = Form(""),
    resume_id: str = Form(""),
    file: UploadFile | None = File(None),
    username: str = Depends(require_user),
    use_ai: bool = Form(False),
):
    # AI job matching is opt-in, as in recruiter workspaces: without it, nothing
    # is sent to the provider even when OPENROUTER_API_KEY is configured.
    resume = validated_resumes.get(username)
    candidate = resume.get("candidate") if resume else None
    if not candidate:
        raise HTTPException(
            status_code=400, detail="Upload a resume before analyzing it."
        )

    if not resume_id or resume_id != resume["resume_id"]:
        raise HTTPException(409, "Resume changed or missing. Upload again before analyzing.")
    if len(job_description) > limits.TEXT_CHARS:
        raise HTTPException(413, "Job description exceeds the configured text limit.")
    jd_text = job_description.strip()

    if file is not None:
        if jd_text:
            raise HTTPException(400, "Provide job description text or a file, not both.")
        content = await read_upload(file, ("pdf", "docx", "txt"), limits.JD_BYTES)
        try:
            jd_text = await run_in_threadpool(parse_document, file.filename, content)
        except limits.DocumentLimitError as exc:
            raise HTTPException(413, str(exc))
        except Exception:
            raise HTTPException(422, "Could not read the job description file.")
        if not jd_text.strip():
            raise HTTPException(422, "No readable job description text found. Scanned files require text extraction first.")

    analysis = await run_in_threadpool(analyze_resume_for_job, candidate, jd_text, use_ai=use_ai)
    if validated_resumes.get(username) is not resume:
        raise HTTPException(409, "Resume changed during analysis. Please retry.")
    resume["analysis"] = analysis
    analysis['analysis_id'] = secrets.token_urlsafe(16)
    resume['improvement_cache'] = {}
    resume['improvement_pending'] = set()

    now = datetime.now()

    history = evaluation_histories.setdefault(username, [])
    history.insert(
        0,
        {
            "name": candidate.get("name") or "Unknown",
            "score": analysis["overall_score"],
            "recommendation": analysis["recommendation"],
            "evaluated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        },
    )
    del history[MAX_HISTORY:]

    return {
        "analysis": analysis,
        "history": history,
    }


@app.post('/api/improvements')
async def improve_resume(
    resume_id: str = Form(..., min_length=1, max_length=128),
    analysis_id: str = Form(..., min_length=1, max_length=128),
    username: str = Depends(require_user),
):
    """Explicit draft generation, separate from scoring and history writes.

    Local only: the former AI copy-edit step could only accept output identical
    to the local rewrite, so it added a provider call without changing results.
    """
    resume = validated_resumes.get(username)
    analysis = resume.get('analysis') if resume else None
    if not resume or resume.get('resume_id') != resume_id or not analysis or analysis.get('analysis_id') != analysis_id:
        raise HTTPException(409, 'Resume or analysis changed. Analyze the current resume first.')
    cache = resume.setdefault('improvement_cache', {})
    pending = resume.setdefault('improvement_pending', set())
    if 'local' in cache:
        return {'resume_id': resume_id, 'analysis_id': analysis_id, 'improvements': cache['local']}
    if 'local' in pending:
        raise HTTPException(409, 'Improvement generation is already in progress.')
    pending.add('local')
    try:
        result = await run_in_threadpool(generate_improvements, resume['candidate'], analysis)
        if validated_resumes.get(username) is not resume or resume.get('analysis') is not analysis:
            raise HTTPException(409, 'Resume or analysis changed during generation. Please retry.')
        cache['local'] = result
        return {'resume_id': resume_id, 'analysis_id': analysis_id, 'improvements': result}
    finally:
        pending.discard('local')


app.include_router(create_router(require_user))
