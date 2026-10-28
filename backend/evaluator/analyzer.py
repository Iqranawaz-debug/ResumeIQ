from ai.matcher import match_resume_to_job_ai
from ai.openrouter_client import MODEL
from evaluator.evaluator import evaluate_candidate
from evaluator.explanation import explain
from evaluator.impact import score_impacts
from evaluator.recommendation import generate_interview_questions
from evaluator.scorer import determine_recommendation
from matcher.matcher import match_resume_to_job
from utils.skills import display_skill

RESUME_QUALITY_WEIGHT = 0.3
JOB_FIT_WEIGHT = 0.7
WEAK_FIT_CAP = 49

AI_NOTES = {
    "not_configured": "AI matching was requested, but no AI provider is configured; local matching was used.",
    "invalid_response": "The AI provider returned an unusable result (after one retry); local matching was used.",
    "unavailable": "The AI provider was unavailable or timed out; local matching was used.",
}


def blend_scores(resume_score: int, job_match: dict) -> tuple[int, int]:
    """Return (rounded blend, final score after the weak-fit cap)."""
    rounded = round(resume_score * RESUME_QUALITY_WEIGHT + job_match["overall_score"] * JOB_FIT_WEIGHT)
    # A confirmed weak job fit should never be rescued by a polished resume —
    # a great resume for the wrong role is still the wrong role. Without this,
    # a high resume-quality score could blend a "Weak Match" job fit up past
    # the "Consider" threshold, which is exactly backwards for a tool whose
    # purpose is judging fit for a specific job.
    final = min(rounded, WEAK_FIT_CAP) if job_match["match_label"] == "Weak Match" else rounded
    return rounded, final


def _failure_reason(exc: Exception) -> str:
    if isinstance(exc, KeyError):
        return "not_configured"
    if isinstance(exc, (ValueError, TypeError)):
        return "invalid_response"
    return "unavailable"


def analyze_resume_for_job(candidate: dict, job_description: str = "", *, use_ai: bool = True) -> dict:
    """Combine general resume quality with job-description fit into a
    single score and recommendation.

    The job description is optional. Without one, the resume is scored on
    its own (rule-based quality only, no job-fit component). When an AI job-fit
    score is used it stays the main score, and the local score is always
    reported beside it."""
    general_eval = evaluate_candidate(candidate)
    job_description = (job_description or "").strip()

    if not job_description:
        result = {
            "overall_score": general_eval["resume_score"],
            "recommendation": general_eval["recommendation"],
            "resume_quality_score": general_eval["resume_score"],
            "job_fit_score": None,
            "job_fit_method": None,
            "job_fit_model": None,
            "ai_status": "not_applicable",
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

        result["explanation"] = explain(candidate, job_description, result)
        result["impacts"] = score_impacts(candidate, job_description, result, blend_scores)
        return result

    # The local result is always computed: it is the fallback, and it is shown
    # beside any AI score so the two can be compared.
    local_match = match_resume_to_job(candidate, job_description)
    processing_note = None
    if use_ai:
        try:
            job_match = match_resume_to_job_ai(candidate, job_description)
            job_fit_method, job_fit_model, ai_status = "ai", MODEL, "used"
        except Exception as exc:
            job_match = local_match
            job_fit_method, job_fit_model, ai_status = "rule-based", None, "fallback"
            processing_note = AI_NOTES[_failure_reason(exc)]
    else:
        job_match = local_match
        job_fit_method, job_fit_model, ai_status = "rule-based", None, "not_requested"
        processing_note = "Local matching requested; no provider call was made."

    blend_before_cap, overall_score = blend_scores(general_eval["resume_score"], job_match)
    local_overall = blend_scores(general_eval["resume_score"], local_match)[1]

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
                + ", ".join(display_skill(skill) for skill in job_match["missing_skills"])
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

    result = {
        "overall_score": overall_score,
        "recommendation": recommendation,
        "resume_quality_score": general_eval["resume_score"],
        "resume_only_recommendation": general_eval["recommendation"],
        "job_fit_score": job_match["overall_score"],
        "job_fit_label": job_match["match_label"],
        "job_fit_method": job_fit_method,
        "ai_status": ai_status,
        "processing_note": processing_note,
        "job_fit_model": job_fit_model,
        "local_job_fit_score": local_match["overall_score"],
        "local_job_fit_label": local_match["match_label"],
        "local_overall_score": local_overall,
        "local_recommendation": determine_recommendation(local_overall),
        "ai_match_evidence": job_match.get("match_evidence") if job_fit_method == "ai" else None,
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

    result["explanation"] = explain(candidate, job_description, result, job_match, {
        "resume_quality_weight": RESUME_QUALITY_WEIGHT, "job_fit_weight": JOB_FIT_WEIGHT,
        "resume_quality_points": general_eval["resume_score"] * RESUME_QUALITY_WEIGHT,
        "job_fit_points": job_match["overall_score"] * JOB_FIT_WEIGHT,
        "rounded_before_cap": blend_before_cap,
        "weak_fit_cap": WEAK_FIT_CAP if job_match["match_label"] == "Weak Match" else None,
        "final_score": overall_score,
    }, local_match=local_match)
    result["impacts"] = score_impacts(candidate, job_description, result, blend_scores, local_match)
    return result
