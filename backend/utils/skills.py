import re

from utils.constants import KNOWN_SKILLS, SKILL_CATEGORIES

_SKILL_TO_CATEGORY = {
    skill.lower(): category
    for category, skills in SKILL_CATEGORIES.items()
    for skill in skills
}


def _category_for_skill(skill: str) -> str:
    lower = skill.lower()
    if lower in _SKILL_TO_CATEGORY:
        return _SKILL_TO_CATEGORY[lower]

    # Real resume phrasing rarely matches our vocabulary word-for-word
    # ("Splunk Enterprise Security" vs. "splunk", "CrowdStrike Falcon" vs.
    # "crowdstrike") — fall back to a whole-word substring search so a known
    # keyword appearing anywhere inside the phrase still categorizes.
    for known_skill, category in _SKILL_TO_CATEGORY.items():
        pattern = r"(?<![a-z0-9])" + re.escape(known_skill) + r"(?![a-z0-9])"
        if re.search(pattern, lower):
            return category
    return "Other"


def categorize_skills(skills: list) -> dict:
    """Group a candidate's skills into named categories (Languages,
    Frontend, Backend, etc.), with an "Other" bucket for anything not in
    the known-skills list. Only non-empty categories are returned, in a
    fixed, sensible display order."""
    grouped: dict = {}
    for skill in skills:
        category = _category_for_skill(skill)
        grouped.setdefault(category, []).append(skill)

    order = list(SKILL_CATEGORIES.keys()) + ["Other"]
    return {category: grouped[category] for category in order if category in grouped}


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
