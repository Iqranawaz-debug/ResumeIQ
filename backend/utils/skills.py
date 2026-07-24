import re

from utils.constants import KNOWN_SKILLS


def find_skills_in_text(text: str, skills: list) -> list:
    """Return which of the given skills appear in text as whole words
    (case-insensitive), avoiding false positives like "go" inside "google"."""
    lower_text = text.lower()
    found = []
    for skill in skills:
        pattern = r"(?<![a-z0-9])" + re.escape(skill.lower()) + r"(?![a-z0-9])"
        if re.search(pattern, lower_text):
            found.append(skill)
    return found


def find_known_skills(text: str) -> list:
    """Scan free text for any of the known technical skill keywords."""
    return find_skills_in_text(text, KNOWN_SKILLS)
