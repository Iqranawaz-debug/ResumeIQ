import re

from evaluator.scorer import calculate_total_experience_years
from utils.skills import find_known_skills, find_skills_in_text

YEARS_REQUIRED_PATTERN = re.compile(r"(\d+)\+?\s*(?:to\s*\d+\s*)?years?", re.IGNORECASE)

DEGREE_KEYWORDS = [
    "bachelor",
    "master",
    "phd",
    "doctorate",
    "degree",
    "mba",
]

MATCH_THRESHOLDS = [
    (80, "Strong Match"),
    (50, "Partial Match"),
]
WEAK_MATCH = "Weak Match"


def extract_required_years(job_description: str):
    match = YEARS_REQUIRED_PATTERN.search(job_description)
    return int(match.group(1)) if match else None


def requires_degree(job_description: str) -> bool:
    lower_text = job_description.lower()
    return any(keyword in lower_text for keyword in DEGREE_KEYWORDS)


def determine_match_label(overall_score: int) -> str:
    for threshold, label in MATCH_THRESHOLDS:
        if overall_score >= threshold:
            return label
    return WEAK_MATCH


def _find_required_skills(job_description: str, resume_skills: list) -> list:
    """Skills the job description asks for: anything from our known-skills
    list it mentions, plus any of the candidate's own resume skills it also
    mentions (catches real skills our fixed keyword list doesn't cover)."""
    known_in_job = find_known_skills(job_description)
    resume_skills_in_job = find_skills_in_text(job_description, resume_skills)

    combined = []
    seen = set()
    for skill in resume_skills_in_job + known_in_job:
        key = skill.lower()
        if key not in seen:
            seen.add(key)
            combined.append(skill)
    return combined


def match_resume_to_job(candidate: dict, job_description: str) -> dict:
    """Compare a candidate object against a job description's skills,
    experience, and education requirements."""
    resume_skills = candidate.get("skills") or []
    job_skills = _find_required_skills(job_description, resume_skills)
    resume_skills_lower = {skill.lower() for skill in resume_skills}

    matched_skills = [skill for skill in job_skills if skill.lower() in resume_skills_lower]
    missing_skills = [skill for skill in job_skills if skill.lower() not in resume_skills_lower]
    skills_detected = bool(job_skills)
    skills_score = round(len(matched_skills) / len(job_skills) * 100) if skills_detected else 0

    required_years = extract_required_years(job_description)
    candidate_years = calculate_total_experience_years(candidate)
    if required_years is None:
        experience_score = 100
        experience_note = "No specific experience requirement detected in the job description."
    elif candidate_years >= required_years:
        experience_score = 100
        experience_note = f"Meets the {required_years}+ year requirement ({candidate_years} years found)."
    else:
        experience_score = round(candidate_years / required_years * 100) if required_years else 0
        experience_note = f"Below the {required_years}+ year requirement ({candidate_years} years found)."

    needs_degree = requires_degree(job_description)
    has_education = bool(candidate.get("education"))
    if not needs_degree:
        education_score = 100
        education_note = "No specific degree requirement detected in the job description."
    elif has_education:
        education_score = 100
        education_note = "Education requirement appears to be met."
    else:
        education_score = 0
        education_note = "The job description mentions a degree requirement, but no education was found on the resume."

    if skills_detected:
        overall_score = round(
            skills_score * 0.6 + experience_score * 0.25 + education_score * 0.15
        )
    else:
        # No required skills could be detected at all — our keyword
        # vocabulary doesn't cover this job's domain. experience_score and
        # education_score are unreliable signals here too: they only check
        # generic presence ("has *a* degree", "has *enough* years"), not
        # whether that degree/experience is actually relevant to this role,
        # so they can't be trusted to rescue the score. Cap the whole job-fit
        # score low instead of blending in those inflated defaults — this is
        # what previously let a completely wrong-domain candidate (e.g. a
        # software engineer resume against a nursing job) still land on
        # "Recommended" once experience/education padded the blend back up.
        overall_score = 35

    return {
        "overall_score": overall_score,
        "match_label": determine_match_label(overall_score),
        "skills_score": skills_score,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "experience_score": experience_score,
        "experience_note": experience_note,
        "education_score": education_score,
        "education_note": education_note,
    }
