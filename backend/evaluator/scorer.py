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


CONTACT_FIELD_POINTS = {"name": 4, "email": 3, "phone": 3}


def calculate_score_components(candidate: dict) -> dict:
    """Return (points_earned, max_points) per scoring category."""
    contact_points = sum(
        points
        for field, points in CONTACT_FIELD_POINTS.items()
        if candidate.get(field)
    )

    skills_points = min(calculate_skills_count(candidate) * 5, 25)

    education_points = 20 if candidate.get("education") else 0

    experience = candidate.get("experience") or []
    experience_points = 0
    if experience:
        total_details = sum(len(entry.get("details") or []) for entry in experience)
        experience_points = 25 + min(total_details * 2, 20)

    return {
        "contact": (contact_points, 10),
        "skills": (skills_points, 25),
        "education": (education_points, 20),
        "experience": (experience_points, 45),
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


COMMUNICATION_KEYWORDS = [
    "communication",
    "presentation",
    "public speaking",
    "leadership",
    "teamwork",
    "collaboration",
    "negotiation",
    "interpersonal",
]


def calculate_radar_scores(candidate: dict, score_breakdown: dict) -> dict:
    """Score five candidate-strength dimensions (0-100 each) for the
    strength radar visualization."""
    skills_text = " ".join(candidate.get("skills") or []).lower()
    communication_hits = sum(1 for kw in COMMUNICATION_KEYWORDS if kw in skills_text)
    communication_score = min(communication_hits * 34, 100)

    detected_sections = set(candidate.get("detected_sections") or [])
    projects_score = 100 if "projects" in detected_sections else 0

    return {
        "technical_skills": score_breakdown["skills"],
        "communication": communication_score,
        "projects": projects_score,
        "experience": score_breakdown["experience"],
        "education": score_breakdown["education"],
    }
