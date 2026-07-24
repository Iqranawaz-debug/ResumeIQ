from evaluator.recommendation import generate_strengths, generate_suggestions
from evaluator.scorer import (
    calculate_resume_score,
    calculate_score_breakdown,
    calculate_skills_count,
    calculate_total_experience_years,
    determine_experience_level,
    determine_recommendation,
    find_missing_sections,
)


def evaluate_candidate(candidate: dict) -> dict:
    """Evaluate a candidate object and return skills count, experience
    level, missing sections, resume score, recommendation, strengths,
    and improvement suggestions."""
    skills_count = calculate_skills_count(candidate)
    total_experience_years = calculate_total_experience_years(candidate)
    experience_level = determine_experience_level(total_experience_years)
    missing_sections = find_missing_sections(candidate)
    resume_score = calculate_resume_score(candidate)
    score_breakdown = calculate_score_breakdown(candidate)
    recommendation = determine_recommendation(resume_score)
    detected_sections = set(candidate.get("detected_sections") or [])

    strengths = generate_strengths(candidate, skills_count, total_experience_years)
    suggestions = generate_suggestions(missing_sections, skills_count, detected_sections)

    return {
        "skills_count": skills_count,
        "experience_level": experience_level,
        "total_experience_years": total_experience_years,
        "missing_sections": missing_sections,
        "resume_score": resume_score,
        "score_breakdown": score_breakdown,
        "recommendation": recommendation,
        "strengths": strengths,
        "suggestions": suggestions,
    }
