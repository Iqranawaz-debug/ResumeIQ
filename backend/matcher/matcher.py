import re

from evaluator.scorer import calculate_total_experience_years
from utils.skills import canonical_skill
from matcher.requirements import skill_requirements

YEARS_REQUIRED_PATTERN = re.compile(r"(?<![\d.])(\d+)\+?\s*(?:(?:to|[-–—])\s*\d+\s*)?years?", re.IGNORECASE)

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
SKILLS_WEIGHT = 0.6
EXPERIENCE_WEIGHT = 0.25
EDUCATION_WEIGHT = 0.15
# A skill mentioned only under preferred/nice-to-have headings counts half
# toward the skills component; every other JD mention counts in full.
PREFERRED_SKILL_WEIGHT = 0.5


def skill_weight(contexts) -> float:
    return PREFERRED_SKILL_WEIGHT if contexts and set(contexts) == {"preferred"} else 1.0


# Company/benefit durations ("founded 25 years ago", "over the past 20 years")
# are not candidate requirements.
NOT_REQUIREMENT_AFTER = re.compile(r"\s*(?:ago|old|in business|of (?:history|operation|service|growth|excellence|innovation))\b", re.IGNORECASE)
NOT_REQUIREMENT_BEFORE = re.compile(r"\b(?:over the (?:past|last)|in the (?:past|last)|for over|for more than|founded|established|within|after)\s*$", re.IGNORECASE)
REQUIREMENT_BEFORE = re.compile(r"\b(?:minimum(?: of)?|at least|requires?|required|must have|need)\W*$", re.IGNORECASE)


def extract_required_years(job_description: str):
    """Prefer an explicit experience requirement; otherwise the first plausible one."""
    fallback = None
    for match in YEARS_REQUIRED_PATTERN.finditer(job_description):
        before = job_description[max(0, match.start() - 30):match.start()]
        after = job_description[match.end():match.end() + 60]
        if NOT_REQUIREMENT_AFTER.match(after) or NOT_REQUIREMENT_BEFORE.search(before):
            continue
        sentence_after = re.split(r"[.;\n]", after, maxsplit=1)[0]
        if REQUIREMENT_BEFORE.search(before) or re.search(r"\bexperience", sentence_after, re.IGNORECASE):
            return int(match.group(1))
        if fallback is None:
            fallback = int(match.group(1))
    return fallback


def requires_degree(job_description: str) -> bool:
    # Remove explicit negated degree clauses, without erasing another requirement.
    text = re.sub(r"\bno\s+(?:\w+\s+){0,2}degree\s+(?:is\s+)?(?:required|necessary)\b|\bdegree\s+(?:is\s+)?not\s+(?:required|necessary)\b", "", job_description, flags=re.I)
    return bool(re.search(r"\b(?:bachelor(?:'s)?|master(?:'s)?|phd|doctorate|degree|mba)\b", text, re.I))



def determine_match_label(overall_score: int) -> str:
    for threshold, label in MATCH_THRESHOLDS:
        if overall_score >= threshold:
            return label
    return WEAK_MATCH


def _find_required_skills(job_description: str, resume_skills: list) -> list:
    """Skills the job description asks for: anything from our known-skills
    list it mentions, plus any of the candidate's own resume skills it also
    mentions (catches real skills our fixed keyword list doesn't cover)."""
    requirements = skill_requirements(job_description, resume_skills)
    known = {item['skill'] for item in requirements}
    # Retain the legacy order: candidate matches first, then other JD terms.
    combined = [canonical_skill(skill) for skill in resume_skills if canonical_skill(skill) in known]
    combined += [item['skill'] for item in requirements]
    return list(dict.fromkeys(combined))



def match_resume_to_job(candidate: dict, job_description: str) -> dict:
    """Compare a candidate object against a job description's skills,
    experience, and education requirements."""
    resume_skills = candidate.get("skills") or []
    requirements = skill_requirements(job_description, resume_skills)
    job_skills = _find_required_skills(job_description, resume_skills)
    resume_skills_lower = {canonical_skill(skill) for skill in resume_skills}
    weights = {item["skill"]: skill_weight(item["contexts"]) for item in requirements}

    matched_skills = [skill for skill in job_skills if skill.lower() in resume_skills_lower]
    missing_skills = [skill for skill in job_skills if skill.lower() not in resume_skills_lower]
    skills_detected = bool(job_skills)
    total_weight = sum(weights.get(skill, 1.0) for skill in job_skills)
    matched_weight = sum(weights.get(skill, 1.0) for skill in matched_skills)
    skills_score = round(matched_weight / total_weight * 100) if skills_detected else 0

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
        education_note = "Education text is present; the current rule awards presence credit. Degree type and completion are not verified."
    else:
        education_score = 0
        education_note = "The job description mentions a degree requirement, but no education was found on the resume."

    if skills_detected:
        overall_score = round(
            skills_score * SKILLS_WEIGHT + experience_score * EXPERIENCE_WEIGHT + education_score * EDUCATION_WEIGHT
        )
    else:
        # No required skills could be detected at all; our keyword
        # vocabulary doesn't cover this job's domain. experience_score and
        # education_score are unreliable signals here too: they only check
        # generic presence ("has *a* degree", "has *enough* years"), not
        # whether that degree/experience is actually relevant to this role,
        # so they can't be trusted to rescue the score. Cap the whole job-fit
        # score low instead of blending in those inflated defaults; this is
        # what previously let a completely wrong-domain candidate (e.g. a
        # software engineer resume against a nursing job) still land on
        # "Recommended" once experience/education padded the blend back up.
        overall_score = 35

    return {
        "score_components": [
            {"component": name, "score": score, "weight": weight, "weighted_points": score * weight}
            for name, score, weight in (("skills", skills_score, SKILLS_WEIGHT), ("experience", experience_score, EXPERIENCE_WEIGHT), ("education", education_score, EDUCATION_WEIGHT))
        ],
        "match_inputs": {"requirements": requirements, "skill_weights": {skill: weights.get(skill, 1.0) for skill in job_skills}, "required_years": required_years, "candidate_years": candidate_years, "degree_required": needs_degree, "education_present": has_education, "skills_detected": skills_detected},
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
