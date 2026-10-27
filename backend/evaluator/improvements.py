"""Bounded draft advice; never mutates candidates, analyses, or their scores."""
import hashlib
import re

from utils.employment_dates import interval

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


def _id(section, index, detail_index, text):
    return hashlib.sha256(f'{section}:{index}:{detail_index}:{text}'.encode()).hexdigest()[:20]


def generate_improvements(candidate, analysis):
    suggestions, checklist, feedback = [], [], []
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
                vague = bool(re.match(r'^(?:worked on|helped with|assisted with|responsible for|involved in)\b', original.strip(), re.I))
                long = len(original.split()) > 40
                if not (proposed or vague or long):
                    if len(feedback) < 8:
                        feedback.append({'section': section, 'entry_index': index, 'label': 'No specific wording issue detected', 'note': 'This is a limited document check, not verification of its claims.'})
                    continue
                if len(suggestions) >= MAX_SUGGESTIONS:
                    continue
                reason = ('Removes unnecessary wording while retaining the stated activity.' if proposed else
                          'Clarify the activity, tools or contribution using facts you can verify; no stronger claim was generated.' if vague else
                          'Potentially too long. Consider splitting the sentence without adding or dropping material facts.')
                item = {'id': _id(section, index, detail_index, original), 'section': section,
                        'entry_index': index, 'detail_index': detail_index, 'original_text': original,
                        'suggested_text': proposed, 'reason': reason, 'source': 'local',
                        'status': 'pending', 'requires_review': True,
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
            check('Job relevance', f'If you have practical {skill} experience, add a factual example. Otherwise leave it out.')
        elif row.get('status') == 'matched' and not row.get('evidence'):
            check('Job relevance', f'If available, clarify your existing {skill} experience with a concrete example; a listed keyword alone does not show proficiency.')
    if candidate.get('skills'):
        check('Presentation', 'Review the existing skill categories for readability; do not add unrelated keywords or imply proficiency you cannot support.')
    if candidate.get('education'):
        check('Completeness', 'Make education completion status clear; attendance alone does not establish graduation.')
    else:
        check('Completeness', 'If relevant, include actual education and completion status; do not invent qualifications.')
    return {'version': 1, 'suggestions': suggestions, 'checklist': checklist,
            'feedback': feedback, 'requirements': requirements, 'method': 'local',
            'note': 'Draft advice only. Original resume content and scores are unchanged. Review every edit.',
            'limitations': ['Professional summary is not retained by the parser; no summary rewrite is generated.',
                            'All improvement advice is generated locally; no resume content is sent to an AI provider.',
                            'Accepted drafts are not a modified resume file and do not change scores.'],
            'bounded': len(suggestions) == MAX_SUGGESTIONS or len(checklist) == MAX_CHECKLIST}
