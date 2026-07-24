from datetime import datetime

from fastapi import Depends, FastAPI, Form, Header, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

from auth.auth import (
    AuthError,
    create_session,
    create_user,
    destroy_session,
    get_username_from_token,
    verify_user,
)
from ai.extractor import extract_candidate_info_ai
from auth.schemas import LoginRequest, SignupRequest
from evaluator.analyzer import analyze_resume_for_job
from extractor.extractor import extract_candidate_info
from parser.document_parser import parse_document
from parser.resume_parser import parse_resume
from utils.resume_checker import looks_like_resume
from utils.validators import validate_resume_file

ALLOWED_JOB_DESCRIPTION_EXTENSIONS = ["pdf", "docx", "txt"]

app = FastAPI(title="ResumeIQ API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage, keyed per logged-in user (no database required).
validated_resumes: dict = {}
evaluation_histories: dict = {}
MAX_HISTORY = 5


def require_user(authorization: str = Header(default="")) -> str:
    token = authorization.removeprefix("Bearer ").strip()
    username = get_username_from_token(token) if token else None
    if not username:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return username


@app.post("/api/signup")
async def signup(payload: SignupRequest):
    username = payload.username.strip()
    try:
        create_user(username, payload.email, payload.password)
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    token = create_session(username)
    return {"token": token, "username": username}


@app.post("/api/login")
async def login(payload: LoginRequest):
    username = payload.username.strip()
    if not verify_user(username, payload.password):
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    token = create_session(username)
    return {"token": token, "username": username}


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

    try:
        candidate = extract_candidate_info_ai(text)
        extraction_method = "ai"
    except Exception:
        candidate = extract_candidate_info(text)
        extraction_method = "rule-based"

    validated_resumes[username] = {
        "filename": file.filename,
        "content_type": file.content_type,
        "size": len(content),
        "bytes": content,
        "text": text,
        "candidate": candidate,
        "extraction_method": extraction_method,
    }

    return {
        "filename": file.filename,
        "size": len(content),
        "message": f"'{file.filename}' uploaded and validated successfully.",
        "text": text,
        "candidate": candidate,
        "extraction_method": extraction_method,
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

    if not jd_text.strip():
        raise HTTPException(
            status_code=400, detail="Provide a job description as text or a file."
        )

    analysis = analyze_resume_for_job(candidate, jd_text)
    resume["analysis"] = analysis

    history = evaluation_histories.setdefault(username, [])
    history.insert(
        0,
        {
            "name": candidate.get("name") or "Unknown",
            "score": analysis["overall_score"],
            "recommendation": analysis["recommendation"],
            "evaluated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
    )
    del history[MAX_HISTORY:]

    return {"analysis": analysis, "history": history}
