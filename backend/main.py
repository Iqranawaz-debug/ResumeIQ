import os
from datetime import datetime

from fastapi import Depends, FastAPI, Form, Header, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

from auth.auth import (
    AuthError,
    create_session,
    create_user,
    destroy_session,
    get_email_from_token,
    verify_user,
)
from ai.categorizer import categorize_skills_ai
from ai.openrouter_client import MODEL
from auth.schemas import LoginRequest, SignupRequest
from evaluator.analyzer import analyze_resume_for_job
from extractor.extractor import extract_candidate_info
from parser.document_parser import parse_document
from parser.resume_parser import parse_resume
from utils.resume_checker import looks_like_resume
from utils.skills import categorize_skills
from utils.validators import validate_resume_file

ALLOWED_JOB_DESCRIPTION_EXTENSIONS = ["pdf", "docx", "txt"]

# Comma-separated list, e.g. "https://myapp.vercel.app,http://localhost:5173"
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

app = FastAPI(title="ResumeIQ API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage, keyed per logged-in user's email (no database required).
validated_resumes: dict = {}
evaluation_histories: dict = {}
MAX_HISTORY = 5


def require_user(authorization: str = Header(default="")) -> str:
    token = authorization.removeprefix("Bearer ").strip()
    email = get_email_from_token(token) if token else None
    if not email:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return email


@app.post("/api/signup")
async def signup(payload: SignupRequest):
    email = payload.email.strip()
    try:
        create_user(email, payload.password, payload.full_name, payload.company)
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    token = create_session(email)
    return {"token": token, "username": email}


@app.post("/api/login")
async def login(payload: LoginRequest):
    email = payload.email.strip()
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
    content = await file.read()

    is_valid, error_message = validate_resume_file(file.filename, len(content))
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_message)

    try:
        text = parse_resume(file.filename, content)
    except Exception:
        raise HTTPException(
            status_code=422, detail="Could not read this file. It may be corrupted."
        )

    is_resume, resume_error = looks_like_resume(text)
    if not is_resume:
        raise HTTPException(status_code=400, detail=resume_error)

    # Extraction runs rule-based only (fast, instant) — AI is reserved for
    # skill categorization below and the JD-matching step in /api/analyze,
    # where it adds the most value.
    candidate = extract_candidate_info(text)
    extraction_method = "rule-based"
    extraction_model = None

    try:
        candidate["skills_by_category"] = categorize_skills_ai(candidate.get("skills") or [])
        categorization_method = "ai"
        categorization_model = MODEL
    except Exception:
        candidate["skills_by_category"] = categorize_skills(candidate.get("skills") or [])
        categorization_method = "rule-based"
        categorization_model = None

    validated_resumes[username] = {
        "filename": file.filename,
        "content_type": file.content_type,
        "size": len(content),
        "bytes": content,
        "text": text,
        "candidate": candidate,
        "extraction_method": extraction_method,
        "extraction_model": extraction_model,
        "categorization_method": categorization_method,
        "categorization_model": categorization_model,
    }

    return {
        "filename": file.filename,
        "size": len(content),
        "message": f"'{file.filename}' uploaded and validated successfully.",
        "text": text,
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
    file: UploadFile | None = File(None),
    username: str = Depends(require_user),
):
    resume = validated_resumes.get(username)
    candidate = resume.get("candidate") if resume else None
    if not candidate:
        raise HTTPException(
            status_code=400, detail="Upload a resume before analyzing it."
        )

    jd_text = job_description.strip()

    if file is not None:
        extension = (file.filename or "").rsplit(".", 1)[-1].lower()
        if extension not in ALLOWED_JOB_DESCRIPTION_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail="Job description file must be PDF, DOCX, or TXT.",
            )
        content = await file.read()
        if not content:
            raise HTTPException(
                status_code=400, detail="The uploaded job description file is empty."
            )
        try:
            jd_text = parse_document(file.filename, content)
        except Exception:
            raise HTTPException(
                status_code=422, detail="Could not read the job description file."
            )

    analysis = analyze_resume_for_job(candidate, jd_text)
    resume["analysis"] = analysis

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
