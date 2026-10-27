"""Bounded draft advice; never mutates candidates, analyses, or their scores."""
import hashlib
import re

from utils.employment_dates import interval
from utils.skills import display_skill, matching_skills

MAX_SUGGESTIONS = 16
MAX_CHECKLIST = 24
MAX_TEXT = 1200


def conservative_rewrite(text):
    """Only narrow copy edits; no inferred responsibilities or outcomes."""
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT:
        return None
    value = ' '.join(text.split())
    # Do not mechanically edit quoted, hypothetical, negative or instructional text.
    if re.search(r'\b(?:not|never|no|if|would|could|should|ignore|instructions?|prompt)\b|["“”]', value, re.I):
        return None
    value = re.sub(r'^I\s+(?=(?:helped|assisted|built|created|developed|tested|maintained|used)\b)', '', value, flags=re.I)
    value = re.sub(r'^Was responsible for\b', 'Responsible for', value, flags=re.I)
    value = re.sub(r'^I was responsible for\b', 'Responsible for', value, flags=re.I)
    value = re.sub(r'\bin order to\b', 'to', value, flags=re.I)
    value = re.sub(r'\butilized\b', 'used', value, flags=re.I)
    if value:
        value = value[0].upper() + value[1:]
    return value if value != text else None


WEAK_OPENING = re.compile(r'^(?:I\s+)?(?:worked on|helped(?: with| to)?|assisted(?: with| in)?|(?:was |were )?responsible for|involved in|participated in|duties included|tasked with|in charge of)\b', re.I)
PASSIVE = re.compile(r'\b(?:was|were|been|being|is|are)\s+\w+ed\b', re.I)
OUTCOME = re.compile(r'\d|%|\b(?:reduc|increas|improv|sav|grew|grow|cut|achiev|result|enabl|decreas|boost|accelerat|shorten|faster|fewer|lower|higher)\w*', re.I)
ISSUES = {
    'weak_opening': ('Weak opening', 'Start with a specific action verb that accurately describes your role.'),
    'passive_voice': ('Passive voice', 'Say who did the work: active voice reads more directly.'),
    'no_outcome': ('No stated outcome', 'If you know the result (time saved, errors reduced, users served), add it. Do not estimate.'),
    'too_long': ('Long sentence', 'Split or trim it without dropping facts.'),
    'first_person': ('First person', 'Resume bullets usually omit "I".'),
}


def bullet_issues(text):
    """Writing issues a reviewer would flag. Advice only; nothing is rewritten here."""
    value = ' '.join(text.split())
    codes = []
    if re.match(r'^I\s', value):
        codes.append('first_person')
    if WEAK_OPENING.match(value):
        codes.append('weak_opening')
    if PASSIVE.search(value):
        codes.append('passive_voice')
    if not OUTCOME.search(value):
        codes.append('no_outcome')
    if len(value.split()) > 40:
        codes.append('too_long')
    return [{'code': code, 'label': ISSUES[code][0], 'tip': ISSUES[code][1]} for code in codes]


# Grounding rules for AI wording suggestions: the rewrite may reorder, trim and
# choose a more direct verb, but must not introduce facts the original lacks.
PLACEHOLDER = re.compile(r'\[[^\[\]]{1,60}\]')
NEW_WORDS_ALLOWED = set("""built created developed designed implemented delivered maintained improved streamlined
automated analyzed analysed prepared produced documented tested supported assisted contributed coordinated
collaborated handled processed resolved reviewed configured deployed integrated migrated monitored optimized
optimised organized organised planned researched wrote drafted conducted performed operated used applied executed
completed provided responded communicated presented reported tracked updated upgraded refactored debugged
troubleshot ensured enabled facilitated helped worked partnered answered drafted compiled calculated scheduled
using with across through within including into from while during resulting ensuring enabling which that their
these those other each both also""".split())
ESCALATION = {'led', 'lead', 'leading', 'managed', 'manage', 'managing', 'directed', 'owned', 'spearheaded',
              'architected', 'supervised', 'headed', 'oversaw', 'overseeing', 'mentored', 'championed', 'pioneered'}
NEGATION = re.compile(r"\b(?:not|never|no|without|n't)\b", re.I)


def _stem(word):
    # Light suffix stripping so "fixed"/"fixing" and "developed"/"development" agree.
    for suffix in ('ments', 'ment', 'ings', 'ing', 'ions', 'ion', 'ers', 'er', 'ed', 'es', 's'):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            word = word[:-len(suffix)]
            break
    return word[:5]


def grounded_rewrite(original, rewrite):
    """Return (accepted, reason). Accepts only rewrites that add no new facts.

    Checked: numbers, recognized skills/tools, capitalized names, responsibility
    level, negation and length. New words must be on a small list of plain action
    verbs and connectors, compared by stem so "developed"/"development" agree.
    Bracketed placeholders such as "[result, if known]" are allowed (max 2, no
    digits) because they ask the user for facts rather than inventing them.
    """
    if not isinstance(rewrite, str) or not rewrite.strip() or len(rewrite) > MAX_TEXT:
        return False, 'empty or too long'
    source, text = ' '.join(original.split()), ' '.join(rewrite.split())
    if text.casefold() == source.casefold():
        return False, 'unchanged'
    placeholders = PLACEHOLDER.findall(text)
    if len(placeholders) > 2 or any(re.search(r'\d', p) for p in placeholders):
        return False, 'placeholder must not contain numbers'
    stripped = PLACEHOLDER.sub(' ', text)
    if re.search(r'[\[\]]', stripped):
        return False, 'malformed placeholder'
    if len(stripped) > len(source) * 1.6 + 20:
        return False, 'much longer than the original'
    numbers = lambda value: set(re.findall(r'\d+(?:[.,]\d+)?', value))
    if not numbers(stripped) <= numbers(source):
        return False, 'adds a number'
    if not set(matching_skills(stripped)) <= set(matching_skills(source)):
        return False, 'adds a tool or skill'
    if len(NEGATION.findall(stripped)) != len(NEGATION.findall(source)):
        return False, 'changes negation'
    tokens = lambda value: [w.strip(".'-") for w in re.findall(r"[A-Za-z][A-Za-z'+#.]*", value)]
    source_words = {w.casefold() for w in tokens(source)}
    source_stems = {_stem(w) for w in source_words}
    for position, word in enumerate(tokens(stripped)):
        key = word.casefold()
        if key in ESCALATION and _stem(key) not in source_stems:
            return False, f'raises responsibility level ("{word}")'
        if key in source_words or _stem(key) in source_stems or len(key) < 4:
            continue
        if position and word[0].isupper():
            return False, f'adds a name ("{word}")'
        if key not in NEW_WORDS_ALLOWED:
            return False, f'adds new content ("{word}")'
    return True, None


def _id(section, index, detail_index, text):
    return hashlib.sha256(f'{section}:{index}:{detail_index}:{text}'.encode()).hexdigest()[:20]


def generate_improvements(candidate, analysis):
    suggestions, checklist, feedback, review = [], [], [], []
    seen = set()

    def check(category, text, source_id=None):
        if len(checklist) < MAX_CHECKLIST and text not in {item['text'] for item in checklist}:
            checklist.append({'id': _id(category, 0, 0, text), 'category': category,
                              'text': text, 'source_id': source_id, 'status': 'pending'})

    for section in ('experience', 'projects'):
        for index, entry in enumerate((candidate.get(section) or [])[:30]):
            if not entry.get('details'):
                check('Content quality', f'Clarify your actual contributions in {section} entry {index + 1}; add only facts you can verify.')
            for detail_index, original in enumerate((entry.get('details') or [])[:30]):
                if not isinstance(original, str) or not original.strip():
                    continue
                normalized = ' '.join(original.casefold().split())
                if normalized in seen:
                    check('Content quality', f'Review repeated wording in {section} entry {index + 1}; remove repetition only if it describes the same work.')
                    continue
                seen.add(normalized)
                if len(original) > MAX_TEXT:
                    check('Content quality', f'Consider splitting the long description in {section} entry {index + 1} while preserving its facts.')
                    continue
                proposed = conservative_rewrite(original)
                issues = bullet_issues(original)
                if issues and len(review) < MAX_SUGGESTIONS:
                    review.append({'id': _id(section, index, detail_index, original), 'section': section,
                                   'entry_index': index, 'detail_index': detail_index,
                                   'original_text': original, 'issues': issues})
                vague = bool(re.match(r'^(?:worked on|helped with|assisted with|responsible for|involved in)\b', original.strip(), re.I))
                long = len(original.split()) > 40
                if not (proposed or vague or long):
                    if len(feedback) < 8:
                        label = ('Could be stronger: ' + ', '.join(i['label'].lower() for i in issues)) if issues else 'No specific wording issue detected'
                        note = ' '.join(i['tip'] for i in issues) if issues else 'This is a limited document check, not verification of its claims.'
                        feedback.append({'section': section, 'entry_index': index, 'label': label, 'note': note})
                    continue
                if len(suggestions) >= MAX_SUGGESTIONS:
                    continue
                reason = ('Removes unnecessary wording while retaining the stated activity.' if proposed else
                          'Clarify the activity, tools or contribution using facts you can verify; no stronger claim was generated.' if vague else
                          'Potentially too long. Consider splitting the sentence without adding or dropping material facts.')
                item = {'id': _id(section, index, detail_index, original), 'section': section,
                        'entry_index': index, 'detail_index': detail_index, 'original_text': original,
                        'suggested_text': proposed, 'reason': reason, 'source': 'local',
                        'status': 'pending', 'requires_review': True, 'issues': issues,
                        'feedback': 'Needs clarification' if vague else 'Potentially too long' if long else 'Conciseness'}
                suggestions.append(item)
                check('Content quality', f'Review {section} entry {index + 1}, description {detail_index + 1}.', item['id'])
            if section == 'experience' and interval(entry.get('duration'))[0] is None:
                check('Completeness', f'Review uncertain dates for employment entry {index + 1}; do not estimate dates you cannot verify.')

    # Read Phase 4's already computed rows; never rematch the JD or rescore.
    requirements = []
    for row in (analysis.get('explanation') or {}).get('requirements') or []:
        if len(requirements) >= 40:
            break
        skill = row.get('skill')
        if not isinstance(skill, str) or len(skill) > 100 or skill in {r['skill'] for r in requirements}:
            continue
        requirements.append({'skill': skill, 'status': row.get('status'), 'contexts': row.get('contexts') or []})
        if row.get('status') == 'not_evidenced':
            check('Job relevance', f'If you have practical {display_skill(skill)} experience, add a factual example. Otherwise leave it out.')
        elif row.get('status') == 'matched' and not row.get('evidence'):
            check('Job relevance', f'If available, clarify your existing {display_skill(skill)} experience with a concrete example; a listed keyword alone does not show proficiency.')
    if candidate.get('skills'):
        check('Presentation', 'Review the existing skill categories for readability; do not add unrelated keywords or imply proficiency you cannot support.')
    if candidate.get('education'):
        check('Completeness', 'Make education completion status clear; attendance alone does not establish graduation.')
    else:
        check('Completeness', 'If relevant, include actual education and completion status; do not invent qualifications.')
    return {'version': 1, 'suggestions': suggestions, 'checklist': checklist,
            'feedback': feedback, 'requirements': requirements, 'method': 'local', 'bullet_review': review,
            'note': 'Draft advice only. Original resume content and scores are unchanged. Review every edit.',
            'limitations': ['Professional summary is not retained by the parser; no summary rewrite is generated.',
                            'Local advice never contacts a provider. Optional AI wording suggestions send only flagged employment bullets and are kept only if they pass grounding checks.',
                            'Accepted drafts are not a modified resume file and do not change scores.'],
            'bounded': len(suggestions) == MAX_SUGGESTIONS or len(checklist) == MAX_CHECKLIST}
