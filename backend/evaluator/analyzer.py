from ai.matcher import match_resume_to_job_ai
from ai.openrouter_client import MODEL
from evaluator.evaluator import evaluate_candidate
from evaluator.recommendation import generate_interview_questions
from evaluator.scorer import determine_recommendation
from matcher.matcher import match_resume_to_job

RESUME_QUALITY_WEIGHT = 0.4
JOB_FIT_WEIGHT = 0.6


def analyze_resume_for_job(candidate: dict, job_description: str = "") -> dict:
    """Combine general resume quality with job-description fit into a
    single score and recommendation.

    The job description is optional. Without one, the resume is scored on
    its own (rule-based quality only, no job-fit component)."""
    general_eval = evaluate_candidate(candidate)
    job_description = (job_description or "").strip()

    if not job_description:
        return {
            "overall_score": general_eval["resume_score"],
            "recommendation": general_eval["recommendation"],
            "resume_quality_score": general_eval["resume_score"],
            "job_fit_score": None,
            "job_fit_method": None,
            "job_fit_model": None,
            "extracted_requirements": None,
            "experience_level": general_eval["experience_level"],
            "total_experience_years": general_eval["total_experience_years"],
            "skills_count": general_eval["skills_count"],
            "missing_sections": general_eval["missing_sections"],
            "matched_skills": [],
            "missing_skills": [],
            "experience_note": None,
            "education_note": None,
            "strengths": general_eval["strengths"],
            "weaknesses": general_eval["weaknesses"],
            "suggestions": general_eval["suggestions"],
            "interview_questions": general_eval["interview_questions"],
            "radar": general_eval["radar"],
        }

    try:
        job_match = match_resume_to_job_ai(candidate, job_description)
        job_fit_method = "ai"
        job_fit_model = MODEL
    except Exception:
        job_match = match_resume_to_job(candidate, job_description)
        job_fit_method = "rule-based"
        job_fit_model = None

    overall_score = round(
        general_eval["resume_score"] * RESUME_QUALITY_WEIGHT
        + job_match["overall_score"] * JOB_FIT_WEIGHT
    )
    recommendation = determine_recommendation(overall_score)

    if job_fit_method == "ai" and job_match.get("strengths") and job_match.get("suggestions"):
        strengths = job_match["strengths"]
        suggestions = job_match["suggestions"]
    else:
        strengths = general_eval["strengths"]
        suggestions = list(general_eval["suggestions"])
        if job_match["missing_skills"]:
            suggestions.append(
                "Ask the candidate about experience with: "
                + ", ".join(job_match["missing_skills"])
                + "."
            )

    if job_fit_method == "ai" and job_match.get("weaknesses"):
        weaknesses = job_match["weaknesses"]
    else:
        weaknesses = general_eval["weaknesses"]

    if job_fit_method == "ai" and job_match.get("interview_questions"):
        interview_questions = job_match["interview_questions"]
    else:
        interview_questions = generate_interview_questions(candidate, job_match["missing_skills"])

    return {
        "overall_score": overall_score,
        "recommendation": recommendation,
        "resume_quality_score": general_eval["resume_score"],
        "resume_only_recommendation": general_eval["recommendation"],
        "job_fit_score": job_match["overall_score"],
        "job_fit_label": job_match["match_label"],
        "job_fit_method": job_fit_method,
        "job_fit_model": job_fit_model,
        "extracted_requirements": job_match.get("extracted_requirements"),
        "experience_level": general_eval["experience_level"],
        "total_experience_years": general_eval["total_experience_years"],
        "skills_count": general_eval["skills_count"],
        "missing_sections": general_eval["missing_sections"],
        "matched_skills": job_match["matched_skills"],
        "missing_skills": job_match["missing_skills"],
        "experience_note": job_match["experience_note"],
        "education_note": job_match["education_note"],
        "strengths": strengths,
        "weaknesses": weaknesses,
        "suggestions": suggestions,
        "interview_questions": interview_questions,
        "radar": general_eval["radar"],
    }
