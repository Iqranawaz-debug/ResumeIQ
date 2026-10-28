"""Requirement-by-requirement review of a job description. Display-only.

Each JD requirement line is classified and given a status with a reason:
matched / partial / not_evidenced / unclear. "basis" separates explicit resume
evidence from inference (related skills, similar wording). Nothing here feeds
the score; the existing skill/experience/education rules remain authoritative.
"""
import re

from evaluator.scorer import calculate_total_experience_years
from extractor.evidence import safe_excerpt
from matcher.matcher import extract_required_years
from matcher.requirements import HEADINGS
from utils.employment_dates import interval
from utils.skills import _category_for_skill, canonical_skill, display_skill as _display, matching_skills

MAX_LINES = 40
LINE_HEADINGS = {**HEADINGS, 'qualifications': 'required', 'basic qualifications': 'required',
                 'required qualifications': 'required', "what you'll need": 'required',
                 "what you'll bring": 'required', "what we're looking for": 'required',
                 'must have': 'required', 'must-have': 'required', 'skills': 'required',
                 'about you': 'required', 'you have': 'required', 'key responsibilities': 'responsibilities',
                 "what you'll do": 'responsibilities', 'the role': 'responsibilities',
                 'preferred': 'preferred', 'desired skills': 'preferred', 'bonus points': 'preferred',
                 'bonus': 'preferred', 'nice to haves': 'preferred',
                 # Company and benefits sections are not requirements.
                 'about us': 'skip', 'about the company': 'skip', 'who we are': 'skip', 'benefits': 'skip',
                 'perks': 'skip', 'what we offer': 'skip', 'we offer': 'skip', 'compensation': 'skip'}
CUE = re.compile(r"\b(?:experience|\d+\+?\s*years?\s+(?:of|in|with|experience)|degree|bachelor|master|phd|certif\w*|licen[cs]\w*|proficien\w*|knowledge of|"
                 r"familiar\w*|ability to|understanding of|expertise|must|required|qualif\w*)\b", re.I)
BULLET = re.compile(r'^[•*\-–·▪●]\s*')
DEGREE_LEVELS = [('associate', r"associate'?s?\s+degree"),
                 ('bachelor', r"bachelor|b\.?\s?sc\b|\bb\.?s\.?\b|\bb\.?a\.?\b|b\.?\s?eng\b|b\.?\s?tech\b|undergraduate"),
                 ('master', r"master|m\.?\s?sc\b|\bm\.?s\.?\b|\bmba\b|m\.?\s?eng\b|m\.?\s?tech\b|postgraduate"),
                 ('doctorate', r"ph\.?\s?d|doctor(?:ate|al)")]
STOPWORDS = set('''about above across after also and any are been being both but can could each from have having
into more most must other our over such than that the their them then there these they this those through under
using very well were what when where which while will with within would your you we work working strong ability
including related relevant role team teams skills experience years year plus required preferred knowledge'''.split())


def _names(skills):
    return ', '.join(_display(s) for s in skills)


def _lines(text):
    context, bullets_seen = 'unspecified', False
    for raw in (text or '').replace('’', "'").splitlines():
        line = raw.strip()
        bullet = bool(BULLET.match(line))
        clean = BULLET.sub('', line).strip()
        heading, separator, remainder = clean.partition(':')
        key = ' '.join(heading.casefold().split())
        if key in LINE_HEADINGS and len(key.split()) <= 5:
            context, bullets_seen = LINE_HEADINGS[key], False
            clean = remainder.strip() if separator else ''
        elif clean.endswith(':') and len(clean.split()) <= 6:
            context, bullets_seen = 'unspecified', False
            continue
        elif bullet:
            bullets_seen = True
        elif bullets_seen:
            # Prose after a bulleted list usually closes that section.
            context, bullets_seen = 'unspecified', False
        if not clean or context == 'skip':
            continue
        for part in ([clean] if bullet else re.split(r'(?<=[.;])\s+', clean)):
            part = part.strip(' .;')
            if part and len(part) <= 300:
                yield context, part


CERT_STOPWORDS = {'certification', 'certifications', 'certified', 'certificate', 'certificates', 'license', 'licence',
                  'licensed', 'licenses', 'licences', 'or', 'and', 'a', 'an', 'the', 'in', 'of', 'is', 'are', 'preferred',
                  'required', 'must', 'have', 'equivalent', 'relevant', 'industry', 'professional', 'such', 'as', 'e.g',
                  'plus', 'with', 'current', 'valid', 'active', 'similar', 'any', 'one', 'related', 'nice', 'to', 'be'}


def _cert_tokens(text):
    # Distinctive words such as "aws", "pmp", "cissp", "security+"; generic certification words are ignored.
    return {w for w in re.findall(r"[a-z0-9][a-z0-9+#.-]*", text.casefold()) if w.strip('.') not in CERT_STOPWORDS and len(w) >= 2}


def _words(text):
    return {w for w in re.findall(r"[a-z][a-z+#.-]{3,}", text.casefold()) if w not in STOPWORDS}


def _degree_level(text):
    found = [rank for rank, (_, pattern) in enumerate(DEGREE_LEVELS) if re.search(pattern, text, re.I)]
    return min(found) if found else None


def _skill_evidence(candidate, skill):
    return [dict(record) for record in (candidate.get('skill_evidence') or {}).get(skill, [])[:1]]


def _row(context, text, kind, status, basis, reason, evidence=(), skills=()):
    return {'text': text, 'context': context, 'type': kind, 'status': status, 'basis': basis,
            'reason': reason, 'evidence': list(evidence), 'skills': [_display(s) for s in skills]}


def _skills_row(context, text, kind, candidate, skills, held):
    matched = [s for s in skills if s in held]
    missing = [s for s in skills if s not in held]
    evidence = [e for s in matched for e in _skill_evidence(candidate, s)][:2]
    if not missing:
        return _row(context, text, kind, 'matched', 'explicit', f"Listed in the resume: {_names(matched)}.", evidence, skills)
    if matched:
        return _row(context, text, kind, 'partial', 'explicit',
                    f"Listed: {_names(matched)}. Not found: {_names(missing)}.", evidence, skills)
    held_categories = {}
    for skill in held:
        held_categories.setdefault(_category_for_skill(skill), []).append(skill)
    related = sorted({s for m in missing for s in held_categories.get(_category_for_skill(m), [])
                      if _category_for_skill(m) != 'Other'})
    if related:
        return _row(context, text, kind, 'partial', 'inference',
                    f"Not found: {_names(missing)}. Related skills in the same category are listed ({_names(related[:4])}); "
                    "whether they transfer is a judgment call.", (), skills)
    return _row(context, text, kind, 'not_evidenced', 'none', f"Not found in the resume: {_names(missing)}.", (), skills)


def _assess(context, text, candidate, held, years, uncertain_dates):
    skills = matching_skills(text, candidate.get('skills') or [])
    if re.search(r'\b(?:certif\w*|licen[cs]\w*)\b', text, re.I):
        certifications = candidate.get('certifications') or []
        wanted = _cert_tokens(text)
        found = [c for c in certifications if wanted and wanted & _cert_tokens(c)]
        if found:
            evidence = [{'section': 'certifications', 'entry_index': None, 'excerpt': c} for c in found[:2] if safe_excerpt(c, candidate)]
            return _row(context, text, 'certification', 'matched', 'explicit',
                        f"Listed certification: {'; '.join(found[:2])}. Validity and expiry are not verified.", evidence, skills)
        if certifications:
            return _row(context, text, 'certification', 'not_evidenced', 'none',
                        f"{len(certifications)} certification(s) listed, but none mention this requirement.", (), skills)
        if 'certifications' in (candidate.get('detected_sections') or []):
            return _row(context, text, 'certification', 'unclear', 'none',
                        'A certifications heading exists, but no entries could be read under it. Review it manually.', (), skills)
        if skills and all(s in held for s in skills):
            return _row(context, text, 'certification', 'partial', 'inference',
                        f"Related skill listed ({_names(skills)}), but no certification was found.", (), skills)
        return _row(context, text, 'certification', 'not_evidenced', 'none', 'No certification section or matching certification found.', (), skills)

    wanted = _degree_level(text)
    if wanted is not None or re.search(r'\bdegree\b', text, re.I):
        education = candidate.get('education') or []
        if not education:
            return _row(context, text, 'education', 'not_evidenced', 'none', 'No education entries were found in the resume.')
        levels = [(level, entry) for entry in education if (level := _degree_level(entry)) is not None]
        best = max(levels, default=(None, None), key=lambda item: item[0])
        excerpt = [{'section': 'education', 'entry_index': None, 'excerpt': best[1]}] if best[1] and safe_excerpt(best[1], candidate) else []
        if best[0] is not None and (wanted is None or best[0] >= wanted):
            return _row(context, text, 'education', 'matched', 'explicit',
                        f'A {DEGREE_LEVELS[best[0]][0]}-level qualification is listed. Field of study and completion are not verified.', excerpt)
        if best[0] is not None:
            return _row(context, text, 'education', 'partial', 'explicit',
                        f'Listed qualification appears to be {DEGREE_LEVELS[best[0]][0]}-level; the requirement asks for {DEGREE_LEVELS[wanted][0]}.', excerpt)
        return _row(context, text, 'education', 'partial', 'inference',
                    'Education is listed, but its degree level could not be identified.')

    required_years = extract_required_years(text)
    if required_years is not None:
        skill_note = ''
        evidenced = all(any(e.get('section') == 'experience' for e in (candidate.get('skill_evidence') or {}).get(s, [])) for s in skills)
        if skills:
            skill_note = (f" Years using {_names(skills)} specifically are not calculated" +
                          ('; the skill appears in employment descriptions.' if evidenced else '; the skill is not evidenced in employment descriptions.'))
        if years >= required_years and (not skills or evidenced):
            return _row(context, text, 'experience', 'matched', 'explicit',
                        f'{years} years of dated employment documented (requires {required_years}).{skill_note}', (), skills)
        if years >= required_years or years > 0:
            status, basis = ('unclear', 'none') if uncertain_dates and years < required_years else ('partial', 'explicit')
            extra = ' Some employment dates could not be read, so the total may be understated.' if status == 'unclear' else ''
            return _row(context, text, 'experience', status, basis,
                        f'{years} years of dated employment documented (requires {required_years}).{skill_note}{extra}', (), skills)
        if uncertain_dates:
            return _row(context, text, 'experience', 'unclear', 'none',
                        'No dated employment could be calculated; some dates were unreadable.', (), skills)
        return _row(context, text, 'experience', 'not_evidenced', 'none', 'No dated employment was found.', (), skills)

    if skills:
        return _skills_row(context, text, 'skill', candidate, skills, held)

    kind = 'responsibility' if context == 'responsibilities' else 'qualification'
    wanted_words = _words(text)
    best, best_overlap = None, set()
    for section in ('experience', 'projects'):
        for index, entry in enumerate(candidate.get(section) or []):
            for detail in entry.get('details') or []:
                overlap = wanted_words & _words(detail)
                if len(overlap) > len(best_overlap):
                    best, best_overlap = (section, index, detail), overlap
    if best and len(best_overlap) >= 2 and len(best_overlap) / max(len(wanted_words), 1) >= 0.4:
        section, index, detail = best
        excerpt = detail if len(detail) <= 240 else detail[:237].rsplit(' ', 1)[0] + '…'
        evidence = [{'section': section, 'entry_index': index, 'excerpt': excerpt}] if safe_excerpt(excerpt, candidate) else []
        return _row(context, text, kind, 'partial', 'inference',
                    f"Similar wording in {'an experience' if section == 'experience' else 'a project'} description ({', '.join(sorted(best_overlap)[:4])}). Similar words do not prove equivalent work.",
                    evidence)
    return _row(context, text, kind, 'unclear', 'none', 'Cannot be assessed automatically from the extracted resume. Review manually.')


def evaluate_requirement_lines(candidate, job_description):
    held = {canonical_skill(s) for s in candidate.get('skills') or []}
    years = calculate_total_experience_years(candidate)
    uncertain = any(interval(e.get('duration'))[0] is None for e in candidate.get('experience') or [])
    rows, seen = [], set()
    for context, text in _lines(job_description):
        if context == 'unspecified' and not CUE.search(text) and not matching_skills(text, candidate.get('skills') or []):
            continue  # Company and benefits prose.
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        rows.append(_assess(context, text, candidate, held, years, uncertain))
        if len(rows) >= MAX_LINES:
            break
    counts = {status: sum(r['status'] == status for r in rows) for status in ('matched', 'partial', 'not_evidenced', 'unclear')}
    return {'version': 1, 'rows': rows, 'counts': counts, 'bounded': len(rows) >= MAX_LINES,
            'note': 'Requirement statuses are an evidence review for human judgment. They do not change the score.'}
