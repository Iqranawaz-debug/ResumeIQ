SECTION_LABELS = {
    "name": "the candidate's name",
    "email": "an email address",
    "phone": "a phone number",
    "skills": "a skills section",
    "education": "education history",
    "experience": "work experience",
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


def generate_weaknesses(
    candidate: dict, skills_count: int, total_experience_years: int, missing_sections: list
) -> list:
    weaknesses = []

    if skills_count < 5:
        weaknesses.append("Limited number of listed technical skills.")
    if total_experience_years < 1:
        weaknesses.append("Little to no professional experience documented.")

    experience = candidate.get("experience") or []
    if experience and not any(entry.get("details") for entry in experience):
        weaknesses.append("Work experience entries lack detailed descriptions.")

    if "education" in missing_sections:
        weaknesses.append("No education section found on the resume.")
    if "phone" in missing_sections or "email" in missing_sections:
        weaknesses.append("Contact information is incomplete.")

    if not weaknesses:
        weaknesses.append("No major weaknesses identified from the resume alone.")

    return weaknesses


def generate_interview_questions(
    candidate: dict, missing_skills: list | None = None
) -> list:
    questions = []
    skills = candidate.get("skills") or []
    missing_skills = missing_skills or []

    if skills:
        questions.append(f"Can you walk us through a project where you used {skills[0]}?")
    if len(skills) > 1:
        questions.append(f"How do you decide between using {skills[0]} and {skills[1]} on a project?")
    if missing_skills:
        questions.append(
            f"This role involves {missing_skills[0]} — do you have any exposure to it, even outside formal work?"
        )

    experience = candidate.get("experience") or []
    if experience:
        title = experience[0].get("title") or "your most recent role"
        questions.append(f"Tell us more about your responsibilities as {title}.")

    questions.append("What's a challenging problem you've solved recently, and how did you approach it?")
    questions.append("Where do you see yourself professionally in the next few years?")

    return questions[:5]


def generate_suggestions(
    missing_sections: list, skills_count: int, detected_sections: set
) -> list:
    suggestions = []

    for field in missing_sections:
        label = SECTION_LABELS.get(field, field)
        suggestions.append(f"Resume is missing {label} — follow up with the candidate to confirm.")

    if skills_count and skills_count < 5:
        suggestions.append("Candidate lists fewer than 5 technical skills — verify their skill set during screening.")

    if "projects" not in detected_sections:
        suggestions.append("No projects section found — ask about hands-on work during the interview.")
    if "certifications" not in detected_sections:
        suggestions.append("No certifications listed — confirm whether the role requires any.")

    if not suggestions:
        suggestions.append(
            "Resume looks complete — proceed to the next step in the screening process."
        )

    return suggestions
