import os
import secrets
import time
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
from ai.rewriter import suggest_rewrites
from extractor.extractor import extract_candidate_info
from parser.document_parser import parse_document
from parser.resume_parser import parse_resume
from utils.resume_checker import looks_like_resume
from utils.candidate_processing import process_resume
import recruiter
import samples
from recruiter import create_router
from evaluator.versions import compare_versions, record_version, version_snapshot
from utils import persistence
from ai import openrouter_client as ai_client

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

# Working data, keyed per logged-in user's email. Held in memory; mirrored to
# SQLite only when RESUMEIQ_DB_PATH is set (see utils/persistence.py).
validated_resumes: dict = {}
evaluation_histories: dict = {}
resume_versions: dict = {}
upload_versions: dict = {}
MAX_HISTORY = 5
# Inactive users' extracted resume data, history and workspaces are erased
# after this many seconds; uploaded file bytes are never retained.
DATA_RETENTION_SECONDS = limits.positive_int("DATA_RETENTION_SECONDS", 2 * 3600)
last_activity: dict = {}
store = persistence.from_environment()


def snapshot(username: str) -> dict:
    """The persistable part of a user's data (no transient caches or locks)."""
    resume = validated_resumes.get(username)
    return {
        "resume": {k: v for k, v in resume.items() if not k.startswith("improvement_")} if resume else None,
        "history": evaluation_histories.get(username, []),
        "versions": resume_versions.get(username, []),
        "workspaces": recruiter.workspaces.get(username, {}),
    }


def restore_persisted_data() -> None:
    now = time.monotonic()
    for username, (data, age) in store.load_all(DATA_RETENTION_SECONDS).items():
        if data.get("resume"):
            validated_resumes[username] = data["resume"]
        if data.get("history"):
            evaluation_histories[username] = data["history"]
        if data.get("versions"):
            resume_versions[username] = data["versions"]
        if data.get("workspaces"):
            recruiter.workspaces[username] = data["workspaces"]
        last_activity[username] = now - age


def erase_user_data(username: str) -> None:
    recruiter.remove_user_data(username)
    for user_store in (validated_resumes, evaluation_histories, resume_versions, upload_versions, last_activity):
        user_store.pop(username, None)
    store.delete_user(username)


def expire_inactive_data(now: float | None = None) -> None:
    now = time.monotonic() if now is None else now
    for username, seen in list(last_activity.items()):
        if now - seen > DATA_RETENTION_SECONDS and username not in recruiter.active_users:
            erase_user_data(username)


def require_user(authorization: str = Header(default="")) -> str:
    token = authorization.removeprefix("Bearer ").strip()
    email = get_email_from_token(token) if token else None
    if not email:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    expire_inactive_data()
    last_activity[email] = time.monotonic()
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
    if upload_versions.get(username) != upload_version:
        raise HTTPException(409, "A newer upload has started. Please use the latest upload.")
    return store_resume(username, file.filename, file.content_type, len(content), candidate)


@app.post("/api/upload/sample")
async def upload_sample(username: str = Depends(require_user)):
    """Load the bundled fictional resume through the same local pipeline."""
    upload_versions[username] = secrets.token_urlsafe(16)
    candidate = await run_in_threadpool(
        process_resume, samples.SAMPLE_FILENAME, samples.SAMPLE_RESUME.encode(),
        lambda name, content, stats: stats.update(format="sample") or content.decode())
    return store_resume(username, samples.SAMPLE_FILENAME, "text/plain", len(samples.SAMPLE_RESUME), candidate) | {
        "sample_job_description": samples.SAMPLE_JOB_DESCRIPTION,
        "message": "Sample resume loaded. It is fictional; a matching sample job description has been filled in.",
    }


def store_resume(username, filename, content_type, size, candidate):
    resume_id = secrets.token_urlsafe(16)
    record = {
        "resume_id": resume_id,
        "filename": filename,
        "content_type": content_type,
        "size": size,
        "candidate": candidate,
        "extraction_method": "rule-based",
        "extraction_model": None,
        "categorization_method": "rule-based",
        "categorization_model": None,
    }
    validated_resumes[username] = record
    store.save_user(username, snapshot(username))
    return {
        "resume_id": resume_id,
        "processing_note": "Skills extracted and categorized locally.",
        "filename": filename,
        "size": size,
        "message": f"'{filename}' uploaded and validated successfully.",
        "candidate": candidate,
        **{key: record[key] for key in ("extraction_method", "extraction_model", "categorization_method", "categorization_model")},
    }


@app.get("/api/history")
async def get_history(username: str = Depends(require_user)):
    return {"history": evaluation_histories.get(username, [])}


@app.get("/api/me/data")
async def get_my_data(username: str = Depends(require_user)):
    """What ResumeIQ currently holds for this account, without the data itself."""
    resume = validated_resumes.get(username)
    return {
        "resume_stored": bool(resume),
        "analysis_stored": bool(resume and resume.get("analysis")),
        "history_entries": len(evaluation_histories.get(username, [])),
        "versions": len(resume_versions.get(username, [])),
        **recruiter.user_data_summary(username),
        "retention_seconds": DATA_RETENTION_SECONDS,
        "storage": "database" if store.enabled else "memory",
        "ai_provider_configured": ai_client.is_configured(),
        "ai_provider": ai_client.provider_name() if ai_client.is_configured() else None,
    }


@app.delete("/api/me/data")
async def delete_my_data(username: str = Depends(require_user)):
    """Erase extracted resume data, analyses, history and workspaces. The account remains."""
    erase_user_data(username)
    return {"message": "Your resume data, analyses, history and workspaces were deleted."}


@app.post("/api/analyze")
async def analyze_resume(
    job_description: str = Form(""),
    resume_id: str = Form(""),
    file: UploadFile | None = File(None),
    username: str = Depends(require_user),
    use_ai: bool = Form(False),
):
    # AI job matching is opt-in, as in recruiter workspaces: without it, nothing
    # is sent to the provider even when an AI key is configured.
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
        except limits.UnreadableDocument as exc:
            raise HTTPException(422, str(exc))
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

    versions = record_version(resume_versions.setdefault(username, []),
                              version_snapshot(resume, analysis, jd_text, now.strftime("%Y-%m-%d %H:%M:%S")))
    store.save_user(username, snapshot(username))

    return {
        "analysis": analysis,
        "history": history,
        "versions": versions,
        "version_comparison": compare_versions(versions[0], versions[1]) if len(versions) > 1 else None,
    }


@app.get("/api/versions")
async def get_versions(username: str = Depends(require_user)):
    versions = resume_versions.get(username, [])
    return {"versions": versions,
            "comparison": compare_versions(versions[0], versions[1]) if len(versions) > 1 else None}


@app.get("/api/health")
async def health():
    """Liveness for deployments. Reveals no user data or configuration secrets."""
    return {"status": "ok", "storage": "sqlite" if store.enabled else "memory"}


@app.post('/api/improvements')
async def improve_resume(
    resume_id: str = Form(..., min_length=1, max_length=128),
    analysis_id: str = Form(..., min_length=1, max_length=128),
    username: str = Depends(require_user),
    use_ai: bool = Form(False),
):
    """Explicit draft generation, separate from scoring and history writes.

    Local advice always comes first. With use_ai, flagged employment bullets are
    sent for wording suggestions, each kept only if it passes grounded_rewrite.
    """
    resume = validated_resumes.get(username)
    analysis = resume.get('analysis') if resume else None
    if not resume or resume.get('resume_id') != resume_id or not analysis or analysis.get('analysis_id') != analysis_id:
        raise HTTPException(409, 'Resume or analysis changed. Analyze the current resume first.')
    mode = 'ai' if use_ai else 'local'
    cache = resume.setdefault('improvement_cache', {})
    pending = resume.setdefault('improvement_pending', set())
    if mode in cache:
        return {'resume_id': resume_id, 'analysis_id': analysis_id, 'improvements': cache[mode]}
    if mode in pending:
        raise HTTPException(409, 'Improvement generation is already in progress.')
    pending.add(mode)
    try:
        local = cache.get('local')
        if local is None:
            local = await run_in_threadpool(generate_improvements, resume['candidate'], analysis)
        result = await run_in_threadpool(suggest_rewrites, resume['candidate'], local) if use_ai else local
        if validated_resumes.get(username) is not resume or resume.get('analysis') is not analysis:
            raise HTTPException(409, 'Resume or analysis changed during generation. Please retry.')
        cache['local'] = local
        cache[mode] = result
        return {'resume_id': resume_id, 'analysis_id': analysis_id, 'improvements': result}
    finally:
        pending.discard(mode)


app.include_router(create_router(require_user, on_change=lambda user: store.save_user(user, snapshot(user))))
restore_persisted_data()
