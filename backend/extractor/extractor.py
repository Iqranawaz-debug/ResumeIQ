import re

from utils.skills import extract_known_skills
from extractor.employment import employment, projects
from utils.employment_dates import DATE_PATTERN
from extractor.evidence import collect_skill_evidence

EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_PATTERN = re.compile(r"(\+?\d[\d\-\s()]{7,}\d)")
YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")
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
        "career history",
        "work history",
        "relevant experience",
        "internship experience",
        "internships experience",
        "experience",
        "internship",
        "internships",
    ],
    "projects": ["projects", "project experience", "personal projects", "academic projects",
                 "featured projects", "portfolio projects", "selected projects", "research projects",
                 "earlier projects & open source", "open source contributions", "open source"],
    "certifications": [
        "certification",
        "certifications",
        "licenses & certifications",
        "certifications & licenses",
        "certifications & licences",
        "licences & certifications",
        "certifications and licenses",
        "certifications and licences",
    ],
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
    # Longest exact heading first, including up to three PDF-wrapped lines.
    phrases = {phrase: category for category, values in SECTION_HEADERS.items() for phrase in values}
    headers = []
    index = 0
    while index < len(lines):
        found = False
        for width in (3, 2, 1):
            chunk = lines[index:index + width]
            if len(chunk) != width or not all(chunk):
                continue
            normalized = " ".join(" ".join(chunk).strip(" :.–—-•*#").lower().split())
            if normalized in phrases:
                headers.append((index, phrases[normalized]))
                # Blank continuation lines so all consumers retain (index, category).
                for offset in range(1, width):
                    lines[index + offset] = ""
                index += width
                found = True
                break
        if not found:
            index += 1
    return headers


def _sections(lines, headers, category):
    for position, (index, cat) in enumerate(headers):
        if cat == category:
            end = headers[position + 1][0] if position + 1 < len(headers) else len(lines)
            yield lines[index + 1:end]


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
    date_spans = [match.span() for match in DATE_PATTERN.finditer(text)]
    for match in PHONE_PATTERN.finditer(text):
        candidate = match.group(0).strip()
        if any(start < match.end() and end > match.start() for start, end in date_spans):
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
    """Prefer skills sections, then supplement with identifiable technologies.

    Only vocabulary terms become output; prose is never a candidate skill.
    Other extraction fields retain their existing section parsing behavior.
    """
    skills = []
    for position, (index, category) in enumerate(headers):
        if category == "skills":
            end = headers[position + 1][0] if position + 1 < len(headers) else len(lines)
            skills.extend(extract_known_skills("\n".join(lines[index + 1:end]), structured=True))
    skills.extend(extract_known_skills(text))
    return list(dict.fromkeys(skills))


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


def extract_experience(lines, headers):
    entries = []
    for section in _sections(lines, headers, "experience"):
        for entry in employment(section):
            if entry not in entries:
                entries.append(entry)
    return entries


def extract_projects(lines, headers):
    return [entry for section in _sections(lines, headers, "projects") for entry in projects(section)]


def extract_certifications(lines, headers):
    """One entry per non-empty line of certification sections, verbatim minus bullets."""
    entries = []
    for section in _sections(lines, headers, "certifications"):
        for line in section:
            value = re.sub(r"^[\s•●▪*\-–]+", "", line).strip()
            if value and len(value) <= 200 and value not in entries:
                entries.append(value)
    return entries[:20]


def extract_candidate_info(text: str) -> dict:
    """Extract structured candidate info (name, email, phone, skills,
    education, experience) from plain resume text."""
    lines = _lines(text)
    headers = _find_headers(lines)
    email = extract_email(text)
    detected_sections = sorted({category for _, category in headers})

    candidate = {
        "name": extract_name(text, email),
        "email": email,
        "phone": extract_phone(text),
        "skills": extract_skills(text, lines, headers),
        "education": extract_education(lines, headers),
        "experience": extract_experience(lines, headers),
        "projects": extract_projects(lines, headers),
        "certifications": extract_certifications(lines, headers),
        "detected_sections": detected_sections,
    }
    candidate['skill_evidence'] = collect_skill_evidence(candidate, text, _sections(lines, headers, 'skills'))
    return candidate
