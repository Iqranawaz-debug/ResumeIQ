"""Small local-only quotations, verified against the parsed source text."""
import re
from utils.skills import canonical_skill, matching_skills


def safe_excerpt(value, candidate):
    if not isinstance(value, str) or len(value) > 240:
        return False
    if re.search(r'\S+@\S+|https?://\S+|\+?\d[\d ()-]{7,}\d', value):
        return False
    if re.search(r'\b(?:nationality|religion|gender|marital|passport|address|born)\b', value, re.I):
        return False
    return not any(str(candidate.get(key) or '').casefold() in value.casefold()
                   for key in ('name', 'email', 'phone') if candidate.get(key))


def collect_skill_evidence(candidate, source_text, skills_sections):
    """No raw document retained; omit uncertain provenance and contact excerpts."""
    sources = []
    for section in ('experience', 'projects'):
        for index, entry in enumerate(candidate.get(section) or []):
            for detail in entry.get('details') or []:
                sources.append((section, index, detail))
    for section in skills_sections:
        for line in section:
            if line:
                sources.append(('skills', None, line))
    allowed = {canonical_skill(s) for s in candidate.get('skills') or []}
    result = {}
    for section, index, text in sources:
        # Sentence fragments remain exact substrings, not rewritten quotations.
        for excerpt in re.split(r'(?<=[.!?;])\s+', text):
            if excerpt not in source_text or not safe_excerpt(excerpt, candidate):
                continue
            for key in matching_skills(excerpt):
                if key not in allowed or len(result.get(key, [])) >= 2:
                    continue
                evidence = {'section': section, 'entry_index': index, 'excerpt': excerpt}
                if evidence not in result.setdefault(key, []):
                    result[key].append(evidence)
    return result
