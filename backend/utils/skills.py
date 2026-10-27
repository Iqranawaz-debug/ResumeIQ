import re
import unicodedata

from utils.constants import KNOWN_SKILLS, SKILL_CATEGORIES, SKILL_ALIASES, SKILL_DISPLAY_NAMES

_SKILL_TO_CATEGORY = {
    skill.lower(): category
    for category, skills in SKILL_CATEGORIES.items()
    for skill in skills
}


def _category_for_skill(skill: str) -> str:
    lower = SKILL_ALIASES.get(skill.lower(), skill.lower())
    if lower in _SKILL_TO_CATEGORY:
        return _SKILL_TO_CATEGORY[lower]

    # Real resume phrasing rarely matches our vocabulary word-for-word
    # ("Splunk Enterprise Security" vs. "splunk", "CrowdStrike Falcon" vs.
    # "crowdstrike") — fall back to a whole-word substring search so a known
    # keyword appearing anywhere inside the phrase still categorizes.
    for known_skill in sorted(_SKILL_TO_CATEGORY, key=len, reverse=True):
        category = _SKILL_TO_CATEGORY[known_skill]
        pattern = r"(?<![a-z0-9])" + re.escape(known_skill) + r"(?![a-z0-9])"
        if re.search(pattern, lower):
            return category
    return "Other"


def categorize_skills(skills: list) -> dict:
    """Group a candidate's skills into stable domain categories,
    with an "Other" bucket for anything not in
    the known-skills list. Only non-empty categories are returned, in a
    fixed, sensible display order."""
    grouped: dict = {}
    seen = set()
    for skill in skills or []:
        if not isinstance(skill, str) or not skill.strip():
            continue
        skill = skill.strip()
        key = SKILL_ALIASES.get(skill.casefold(), skill.casefold())
        skill = SKILL_DISPLAY_NAMES.get(key, skill)
        if key in seen:
            continue
        seen.add(key)
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
    """Keep the matcher's lowercase contract while recognizing the same aliases."""
    return [skill.lower() for skill in extract_known_skills(text, structured=True)]


def display_skill(key):
    """Human-readable name for a canonical skill key."""
    return SKILL_DISPLAY_NAMES.get(key, key.title() if key.islower() else key)


def canonical_skill(value):
    """Canonicalize a complete skill label, including historical candidate data."""
    value = unicodedata.normalize('NFKC', value).replace('\u00ad', '').replace('\u200b', '').replace('\u2011', '-')
    value = ' '.join(value.casefold().split())
    value = re.sub(r'-\s+', '-', value)
    return SKILL_ALIASES.get(value, value)


def matching_skills(text, extra_skills=()):
    """Vocabulary matching with list/context safeguards for ambiguous words.

    Candidate-only unknown skills remain supported, but use the same strict
    punctuation boundaries. This does not extract arbitrary prose as skills.
    """
    text = unicodedata.normalize('NFKC', text).replace('\u2011', '-').replace('\u200b', '').replace('\u00ad', '')
    # Ordinary verbs must not pass through even inside a qualifications section.
    text = re.sub(r'\breact\s+(?:to|quickly|calmly|appropriately)\b', ' ', text, flags=re.I)
    text = re.sub(r'\bgo\s+(?:to|above|beyond|through|the|an?|on)\b', ' ', text, flags=re.I)
    result = [canonical_skill(s) for s in extract_known_skills(text)]
    for line in text.splitlines():
        clean = line.strip(' \t•-*')
        labels = re.split(r'[,;|/]', clean)
        # A bare skill or a list of recognized labels is structured evidence.
        structured = bool(labels) and all(canonical_skill(s.strip().strip('.')) in _SKILL_TO_CATEGORY or canonical_skill(s.strip()) in _SKILL_TO_CATEGORY for s in labels)
        found = extract_known_skills(clean, structured=structured)
        for spelling, key, pattern in _RECOGNIZERS:
            if key in _AMBIGUOUS and re.search(r'(?:using|with|in|of|skills?:)\s+' + re.escape(spelling) + r'\b|\b' + re.escape(spelling) + r'\s+(?:developer|framework|programming|development)\b', clean, re.I):
                if pattern.search(clean):
                    found.append(key)
        result.extend(canonical_skill(s) for s in found)
        for skill in extra_skills:
            key = canonical_skill(skill)
            if key not in _SKILL_TO_CATEGORY and _phrase_pattern(key).search(clean):
                # Do not let unknown aliases bypass common-word safeguards.
                if key != 'go' or re.search(r'\bGo\b|\bgo\s+(?:developer|programming|language)\b', clean):
                    result.append(key)
    return list(dict.fromkeys(result))


def _phrase_pattern(phrase):
    # Allow one wrapped line within a phrase, not a blank paragraph or list bullet.
    gap = r"(?:[^\S\r\n]+|[^\S\r\n]*\r?\n[^\S\r\n]*)"
    pattern = gap.join(re.escape(part) for part in phrase.split())
    pattern = pattern.replace(r"\-", r"-\s*")
    return re.compile(r"(?<![\w.+#-])" + pattern + r"(?![\w+#-]|\.[A-Za-z])", re.I)


_RECOGNIZERS = [(name, SKILL_ALIASES.get(name, name), _phrase_pattern(name))
                for name in dict.fromkeys(KNOWN_SKILLS + list(SKILL_ALIASES))]
_AMBIGUOUS = {"r", "rust", "swift", "ruby", "spring", "excel", "react", "watchdog", "rag", "express", "sketch"}


def extract_known_skills(text, *, structured=False):
    """Return canonical skills in evidence order, preferring longest overlaps.

    This intentionally omits unknown terms rather than accepting arbitrary prose.
    No fuzzy OCR guesses: normalize Unicode/soft hyphens and known phrase wraps.
    The legacy matcher helpers retain their existing output contract.
    """
    if not isinstance(text, str) or not text.strip():
        return []
    text = unicodedata.normalize("NFKC", text).replace("\u00ad", "").replace("\u200b", "")
    text = text.replace("\u2011", "-")
    text = re.sub(r"(?m)^[ \t]*[-•·][ \t]*", "; ", text)
    # Do not recognize technology-shaped tokens inside contact addresses/URLs.
    text = re.sub(r"\S+@\S+|https?://\S+", " ", text)
    matches = []
    for spelling, key, pattern in _RECOGNIZERS:
        for match in pattern.finditer(text):
            if spelling == 'go':
                if re.match(r'\s+(?:to|above|beyond|through|the|an?|on)\b', text[match.end():], re.I):
                    continue
                if not structured and match.group().islower() and not re.match(r'\s+(?:developer|programming|language)\b', text[match.end():], re.I):
                    continue
            if key in _AMBIGUOUS and not structured and match.group().islower():
                continue
            if key == "r" and text[match.end():match.end() + 1] == "&":
                continue
            matches.append((match.start(), match.end(), key))
    selected, occupied_end = [], -1
    for start, end, key in sorted(matches, key=lambda item: (item[0], -(item[1] - item[0]))):
        if start < occupied_end:
            continue
        occupied_end = end
        selected.append((start, key))
    result, seen = [], set()
    for _, key in sorted(selected):
        if key not in seen:
            seen.add(key)
            result.append(SKILL_DISPLAY_NAMES.get(key, key.title()))
    return result
