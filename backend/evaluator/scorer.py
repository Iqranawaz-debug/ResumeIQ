import re
from datetime import date

YEAR_PATTERN = re.compile(r"\b(?:19|20)\d{2}\b")

REQUIRED_SECTIONS = ["name", "email", "phone", "skills", "education", "experience"]

EXPERIENCE_LEVELS = [
    (0, "Fresher"),
    (2, "Junior"),
    (5, "Mid-Level"),
    (float("inf"), "Senior"),
]

RECOMMENDATION_THRESHOLDS = [
    (85, "Highly Recommended"),
    (70, "Recommended"),
    (50, "Consider"),
]
NOT_RECOMMENDED = "Not Recommended"


def calculate_skills_count(candidate: dict) -> int:
    return len(candidate.get("skills") or [])


def _extract_years(duration):
    if not duration:
        return []
    years = [int(y) for y in YEAR_PATTERN.findall(duration)]
    if re.search(r"present", duration, re.IGNORECASE):
        years.append(date.today().year)
    return years


def calculate_total_experience_years(candidate: dict) -> int:
    all_years = []
    for entry in candidate.get("experience") or []:
        all_years.extend(_extract_years(entry.get("duration")))
    if not all_years:
        return 0
    return max(all_years) - min(all_years)


def determine_experience_level(total_years: int) -> str:
    for threshold, label in EXPERIENCE_LEVELS:
        if total_years <= threshold:
            return label
    return EXPERIENCE_LEVELS[-1][1]


def determine_recommendation(resume_score: int) -> str:
    for threshold, label in RECOMMENDATION_THRESHOLDS:
        if resume_score >= threshold:
            return label
    return NOT_RECOMMENDED


def find_missing_sections(candidate: dict) -> list:
    return [
        field
        for field in REQUIRED_SECTIONS
        if not candidate.get(field)
    ]


def calculate_score_components(candidate: dict) -> dict:
    """Return (points_earned, max_points) per scoring category."""
    contact_points = sum(
        10 for field in ("name", "email", "phone") if candidate.get(field)
    )

    skills_points = min(calculate_skills_count(candidate) * 4, 20)

    education_points = 15 if candidate.get("education") else 0

    experience = candidate.get("experience") or []
    experience_points = 0
    if experience:
        total_details = sum(len(entry.get("details") or []) for entry in experience)
        experience_points = 20 + min(total_details * 2, 15)

    return {
        "contact": (contact_points, 30),
        "skills": (skills_points, 20),
        "education": (education_points, 15),
        "experience": (experience_points, 35),
    }


def calculate_resume_score(candidate: dict) -> int:
    components = calculate_score_components(candidate)
    total = sum(points for points, _ in components.values())
    return min(total, 100)


def calculate_score_breakdown(candidate: dict) -> dict:
    """Return each scoring category as a 0-100 percentage of its max."""
    components = calculate_score_components(candidate)
    return {
        category: round(points / max_points * 100)
        for category, (points, max_points) in components.items()
    }
