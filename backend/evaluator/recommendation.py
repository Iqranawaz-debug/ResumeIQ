SECTION_LABELS = {
    "name": "your name",
    "email": "an email address",
    "phone": "a phone number",
    "skills": "a skills section",
    "education": "your education history",
    "experience": "your work experience",
}


def generate_strengths(
    candidate: dict, skills_count: int, total_experience_years: int
) -> list:
    strengths = []

    if skills_count >= 5:
        strengths.append("Good technical skill coverage.")
    if candidate.get("education"):
        strengths.append("Clear educational background.")

    experience = candidate.get("experience") or []
    if experience and any(entry.get("details") for entry in experience):
        strengths.append("Relevant, detailed work experience.")

    if candidate.get("email") and candidate.get("phone"):
        strengths.append("Complete contact information.")
    if total_experience_years >= 3:
        strengths.append("Solid track record of professional experience.")

    return strengths


def generate_suggestions(
    missing_sections: list, skills_count: int, detected_sections: set
) -> list:
    suggestions = []

    for field in missing_sections:
        label = SECTION_LABELS.get(field, field)
        suggestions.append(f"Add {label}.")

    if skills_count and skills_count < 5:
        suggestions.append("List more relevant technical skills — aim for at least 5.")

    if "projects" not in detected_sections:
        suggestions.append("Add a projects section to showcase hands-on work.")
    if "certifications" not in detected_sections:
        suggestions.append("Include relevant certifications to strengthen your profile.")

    if not suggestions:
        suggestions.append(
            "Resume looks complete — consider tailoring it for each job application."
        )

    return suggestions
