from ai.matcher import match_resume_to_job_ai
from evaluator.evaluator import evaluate_candidate
from evaluator.scorer import determine_recommendation
from matcher.matcher import match_resume_to_job

RESUME_QUALITY_WEIGHT = 0.4
JOB_FIT_WEIGHT = 0.6


def analyze_resume_for_job(candidate: dict, job_description: str) -> dict:
    """Combine general resume quality with job-description fit into a
    single score and recommendation."""
    general_eval = evaluate_candidate(candidate)

    try:
        job_match = match_resume_to_job_ai(candidate, job_description)
        job_fit_method = "ai"
    except Exception:
        job_match = match_resume_to_job(candidate, job_description)
        job_fit_method = "rule-based"

    overall_score = round(
        general_eval["resume_score"] * RESUME_QUALITY_WEIGHT
        + job_match["overall_score"] * JOB_FIT_WEIGHT
    )
    recommendation = determine_recommendation(overall_score)

    suggestions = list(general_eval["suggestions"])
    if job_match["missing_skills"]:
        suggestions.append(
            "For this role, consider highlighting or developing: "
            + ", ".join(job_match["missing_skills"])
            + "."
        )

    return {
        "overall_score": overall_score,
        "recommendation": recommendation,
        "resume_quality_score": general_eval["resume_score"],
        "job_fit_score": job_match["overall_score"],
        "job_fit_method": job_fit_method,
        "extracted_requirements": job_match.get("extracted_requirements"),
        "experience_level": general_eval["experience_level"],
        "total_experience_years": general_eval["total_experience_years"],
        "skills_count": general_eval["skills_count"],
        "missing_sections": general_eval["missing_sections"],
        "matched_skills": job_match["matched_skills"],
        "missing_skills": job_match["missing_skills"],
        "experience_note": job_match["experience_note"],
        "education_note": job_match["education_note"],
        "strengths": general_eval["strengths"],
        "suggestions": suggestions,
    }
