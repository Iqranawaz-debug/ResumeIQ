import re

from utils.skills import find_known_skills

EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_PATTERN = re.compile(r"(\+?\d[\d\-\s()]{7,}\d)")
YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")
MONTH = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)
DURATION_LINE_PATTERN = re.compile(
    rf"^(?:{MONTH}\.?\s+)?(19|20)\d{{2}}\s*[-–—]\s*"
    rf"(?:(?:{MONTH}\.?\s+)?(19|20)\d{{2}}|present)\.?$",
    re.IGNORECASE,
)
INLINE_DURATION_PATTERN = re.compile(
    rf"\s*\(\s*(?:{MONTH}\.?\s+)?(19|20)\d{{2}}\s*[-–—]\s*"
    rf"(?:(?:{MONTH}\.?\s+)?(19|20)\d{{2}}|present)\s*\)",
    re.IGNORECASE,
)

SECTION_HEADERS = {
    "skills": [
        "technical skills",
        "core competencies",
        "skills",
        "key skills",
        "skills and tools",
    ],
    "education": ["academic background", "education", "educational background"],
    "experience": [
        "professional experience",
        "work experience",
        "employment history",
        "work history",
        "relevant experience",
        "internship experience",
        "internships experience",
        "experience",
        "internship",
        "internships",
    ],
    "projects": ["projects", "project experience", "personal projects", "academic projects"],
    "certifications": ["certification", "certifications", "licenses & certifications"],
    # Recognized only to correctly bound the sections above; their content
    # isn't extracted since the candidate object has no field for them.
    "other": [
        "awards",
        "honors",
        "volunteer",
        "volunteer work",
        "volunteer experience",
        "languages",
        "leadership",
        "leadership & activities",
        "activities",
        "interests",
        "hobbies",
        "references",
        "publications",
        "achievements",
        "additional information",
    ],
}

def _lines(text):
    return [line.strip() for line in text.splitlines()]


def _find_headers(lines):
    headers = []
    for index, line in enumerate(lines):
        normalized = line.strip(":").strip().lower()
        if not normalized or len(normalized.split()) > 4:
            continue
        for category, phrases in SECTION_HEADERS.items():
            if normalized in phrases:
                headers.append((index, category))
                break
    return headers


def _section_lines(lines, headers, category):
    for position, (index, cat) in enumerate(headers):
        if cat != category:
            continue
        start = index + 1
        end = headers[position + 1][0] if position + 1 < len(headers) else len(lines)
        return [line for line in lines[start:end] if line]
    return []


def extract_email(text):
    match = EMAIL_PATTERN.search(text)
    return match.group(0) if match else None


def extract_phone(text):
    for match in PHONE_PATTERN.finditer(text):
        candidate = match.group(0).strip()
        if DURATION_LINE_PATTERN.match(candidate):
            continue
        return candidate
    return None


def extract_name(text, email=None):
    for line in _lines(text)[:5]:
        if not line:
            continue
        if email and email in line:
            continue
        if EMAIL_PATTERN.search(line) or PHONE_PATTERN.search(line):
            continue
        words = line.split()
        if 1 <= len(words) <= 4 and all(word.strip(".,").isalpha() for word in words):
            return line
    return None


def extract_skills(text, lines, headers):
    section = _section_lines(lines, headers, "skills")
    skills = []
    for line in section:
        _, _, after_colon = line.partition(":")
        content = after_colon if after_colon else line
        skills.extend(
            part.strip() for part in re.split(r"[,•|/;]", content) if part.strip()
        )

    if not skills:
        skills = find_known_skills(text)

    seen = set()
    unique = []
    for skill in skills:
        key = skill.lower()
        if key not in seen:
            seen.add(key)
            unique.append(skill)
    return unique


def extract_education(lines, headers):
    section = _section_lines(lines, headers, "education")
    entries = []
    buffer = []
    for line in section:
        buffer.append(line)
        if YEAR_PATTERN.search(line):
            entries.append(" ".join(buffer))
            buffer = []
    if buffer:
        entries.append(" ".join(buffer))
    return entries


def _extract_inline_duration(line):
    """Pull a '(Month YYYY - Month YYYY)' style date out of a title line."""
    match = INLINE_DURATION_PATTERN.search(line)
    if not match:
        return line, None
    duration = match.group(0).strip(" ()")
    title = (line[: match.start()] + line[match.end() :]).strip(" -,")
    return title, duration


def _is_new_entry(section, index):
    line = section[index]
    n = len(section)
    if INLINE_DURATION_PATTERN.search(line):
        return True
    if index + 1 < n and DURATION_LINE_PATTERN.match(section[index + 1]):
        return True
    if index + 2 < n and DURATION_LINE_PATTERN.match(section[index + 2]):
        return True
    return False


def _merge_wrapped_lines(lines):
    """Rejoin lines that are really the wrapped continuation of the
    previous sentence (a line starting with a lowercase letter)."""
    merged = []
    for line in lines:
        if merged and line and line[0].islower():
            merged[-1] = f"{merged[-1]} {line}"
        else:
            merged.append(line)
    return merged


def extract_experience(lines, headers):
    section = _section_lines(lines, headers, "experience")
    entries = []
    i, n = 0, len(section)

    while i < n:
        title, duration = _extract_inline_duration(section[i])

        if duration is not None:
            i += 1
        elif i + 1 < n and DURATION_LINE_PATTERN.match(section[i + 1]):
            duration = section[i + 1]
            i += 2
        elif i + 2 < n and DURATION_LINE_PATTERN.match(section[i + 2]):
            title = f"{section[i]}, {section[i + 1]}"
            duration = section[i + 2]
            i += 3
        else:
            i += 1

        details = []
        while i < n and not _is_new_entry(section, i):
            details.append(section[i])
            i += 1

        entries.append(
            {"title": title, "duration": duration, "details": _merge_wrapped_lines(details)}
        )

    return entries


def extract_candidate_info(text: str) -> dict:
    """Extract structured candidate info (name, email, phone, skills,
    education, experience) from plain resume text."""
    lines = _lines(text)
    headers = _find_headers(lines)
    email = extract_email(text)
    detected_sections = sorted({category for _, category in headers})

    return {
        "name": extract_name(text, email),
        "email": email,
        "phone": extract_phone(text),
        "skills": extract_skills(text, lines, headers),
        "education": extract_education(lines, headers),
        "experience": extract_experience(lines, headers),
        "detected_sections": detected_sections,
    }
