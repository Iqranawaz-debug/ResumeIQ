import re

EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_PATTERN = re.compile(r"(\+?\d[\d\-\s()]{7,}\d)")
LINK_PATTERN = re.compile(r"(linkedin\.com|github\.com)", re.IGNORECASE)

SECTION_CATEGORIES = {
    "contact": ["contact information", "contact details", "contact"],
    "summary": ["professional summary", "summary", "objective"],
    "skills": ["skills", "technical skills", "core competencies"],
    "experience": [
        "work experience",
        "professional experience",
        "employment history",
        "experience",
        "internship",
        "internships",
    ],
    "education": ["education", "academic background"],
    "certifications": ["certification", "certifications"],
    "projects": ["projects", "project experience"],
    "additional": [
        "awards",
        "volunteer",
        "volunteer work",
        "languages",
        "leadership",
        "activities",
        "honors",
    ],
}

MIN_SECTION_MATCHES = 2

ERROR_NOT_A_RESUME = (
    "This document doesn't look like a resume. Make sure it includes "
    "contact details (email/phone) and sections like Experience, "
    "Education, or Skills."
)
ERROR_EMPTY_TEXT = "No readable text was found in this document."


def looks_like_resume(text: str):
    """Heuristically check whether extracted text resembles a resume.

    Returns a (is_resume, error_message) tuple; error_message is None when valid.
    """
    if not text or not text.strip():
        return False, ERROR_EMPTY_TEXT

    lower_text = text.lower()

    has_contact = bool(EMAIL_PATTERN.search(text)) or bool(
        PHONE_PATTERN.search(text)
    ) or bool(LINK_PATTERN.search(text))
    section_hits = sum(
        1
        for phrases in SECTION_CATEGORIES.values()
        if any(phrase in lower_text for phrase in phrases)
    )

    if has_contact and section_hits >= MIN_SECTION_MATCHES:
        return True, None

    return False, ERROR_NOT_A_RESUME
