"""What would change this score: re-run the existing local rules on edited copies.

Each estimate comes from the same scorer and matcher that produced the score,
applied to a hypothetical copy of the candidate. Nothing is invented about the
candidate: every action is conditional on being true.
"""
import copy

from evaluator.scorer import calculate_resume_score, calculate_skills_count
from matcher.matcher import match_resume_to_job
from utils.skills import display_skill

MAX_ITEMS = 10
MAX_SKILL_SIMULATIONS = 12
SKILLS_FOR_FULL_POINTS = 5
DETAILS_FOR_FULL_POINTS = 10
NOTE = ('Estimates re-run the existing scoring rules on a hypothetical edit. Only make a change if it is '
        'true; a higher score is not evidence of a better hiring outcome.')


def score_impacts(candidate, job_description, analysis, blend, local_match=None):
    """Return ranked score changes for honest edits.

    blend(quality, job_match) -> (rounded, final) is the analyzer's own blend.
    With an AI job-fit score, only resume-quality edits can be estimated because
    the provider's judgment cannot be re-run deterministically.
    """
    quality = calculate_resume_score(candidate)
    job_fit = analysis.get('job_fit_score')
    ai_main = analysis.get('job_fit_method') == 'ai'
    if job_fit is None:
        base_match = None
    elif ai_main:
        base_match = {'overall_score': job_fit, 'match_label': analysis.get('job_fit_label')}
    else:
        base_match = local_match
    current = analysis['overall_score']
    items = []

    def overall(new_quality, match):
        return new_quality if match is None else blend(new_quality, match)[1]

    def add(action, condition, kind, edited=None, match=None):
        new_quality = calculate_resume_score(edited) if edited is not None else quality
        match = match or base_match
        new_job_fit = match['overall_score'] if match else None
        item = {'action': action, 'condition': condition, 'kind': kind,
                'quality_delta': new_quality - quality,
                'job_fit_delta': (new_job_fit - job_fit) if match else 0,
                'overall_delta': overall(new_quality, match) - current}
        if item['quality_delta'] or item['job_fit_delta'] or item['overall_delta']:
            items.append(item)

    def edited(change):
        value = copy.deepcopy(candidate)
        change(value)
        return value

    for field, label in (('name', 'your name'), ('email', 'an email address'), ('phone', 'a phone number')):
        if not candidate.get(field):
            add(f'Add {label} as plain text near the top', 'Include your real contact details.', 'quality',
                edited(lambda v, f=field: v.__setitem__(f, 'present')))

    count = calculate_skills_count(candidate)
    if count < SKILLS_FOR_FULL_POINTS:
        extra = SKILLS_FOR_FULL_POINTS - count
        add(f'List up to {extra} more skill{"s" if extra > 1 else ""} you genuinely use',
            'Only skills you can discuss with real examples.', 'quality',
            edited(lambda v: v.__setitem__('skills', list(v.get('skills') or []) + [f'skill-{i}' for i in range(extra)])))

    if not candidate.get('education'):
        add('Add your education, including completion status', 'Only qualifications you have earned or are actively pursuing.',
            'quality', edited(lambda v: v.__setitem__('education', ['present'])))

    experience = candidate.get('experience') or []
    if not experience:
        add('Add your employment history with dates', 'Only roles you actually held.', 'quality',
            edited(lambda v: v.__setitem__('experience', [{'details': []}])))
    else:
        details = sum(len(entry.get('details') or []) for entry in experience)
        if details < DETAILS_FOR_FULL_POINTS:
            extra = DETAILS_FOR_FULL_POINTS - details
            empty = sum(not entry.get('details') for entry in experience)
            action = (f'Describe your work in the {empty} employment entr{"ies" if empty > 1 else "y"} with no description'
                      if empty else f'Add up to {extra} more factual achievement bullet{"s" if extra > 1 else ""}')
            add(action, 'Describe real responsibilities and results only.', 'quality',
                edited(lambda v: v['experience'][0].setdefault('details', []).extend(['detail'] * extra)))

    if base_match is not None and not ai_main:
        for skill in (local_match.get('missing_skills') or [])[:MAX_SKILL_SIMULATIONS]:
            name = display_skill(skill)
            value = edited(lambda v, s=name: v.__setitem__('skills', list(v.get('skills') or []) + [s]))
            add(f'Show your {name} experience in the resume', f'Only if you have genuinely used {name}.', 'job_fit',
                value, match_resume_to_job(value, job_description))

    items.sort(key=lambda item: (-item['overall_delta'], -item['job_fit_delta'], -item['quality_delta'], item['action']))
    return {
        'version': 1, 'base_score': current, 'items': items[:MAX_ITEMS], 'note': NOTE,
        'scope_note': ('The job-fit score came from the AI provider and cannot be re-run, so only resume-quality '
                       'changes are estimated (with the AI job fit held constant).') if ai_main else None,
    }
