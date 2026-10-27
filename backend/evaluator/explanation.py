"""Read-only explanations of existing evaluations, never replacement scores."""
from evaluator.scorer import calculate_score_components
from extractor.evidence import safe_excerpt
from matcher.requirements import skill_requirements
from utils.employment_dates import interval
from utils.skills import canonical_skill, matching_skills

ADVISORY = 'Advisory document review for human consideration; not an ATS acceptance probability or a hiring decision.'
QUALITY_RULES = {
    'contact': 'Presence only: name 4, email 3, phone 3 points; identity is not assessed.',
    'skills': '5 points per extracted skill, capped at 25; not a proficiency assessment.',
    'education': '20 points for any education text; degree type and completion are not verified.',
    'experience': '25 points for any employment entry plus 2 per description item, capped at 45; projects excluded.',
}


def explain(candidate, description, analysis, job_match=None, blend=None):
    quality = [{'component': key, 'points': points, 'maximum': maximum, 'rule': QUALITY_RULES[key]}
               for key, (points, maximum) in calculate_score_components(candidate).items()]
    local = (job_match or {}).get('match_inputs')
    requirements = local['requirements'] if local else skill_requirements(description, candidate.get('skills') or [])
    weights = (local or {}).get('skill_weights') or {}
    candidate_skills = {canonical_skill(s) for s in candidate.get('skills') or []}
    records = candidate.get('skill_evidence') or {}
    rows = []
    for requirement in requirements:
        skill = requirement['skill']
        matched = skill in candidate_skills
        evidence = []
        for record in records.get(skill, [])[:2]:
            excerpt = record.get('excerpt')
            section = record.get('section')
            if section not in ('skills', 'experience', 'projects') or not safe_excerpt(excerpt, candidate):
                continue
            if skill not in matching_skills(excerpt):
                continue
            # Recheck entry ownership against this candidate at analysis time.
            if section != 'skills':
                index = record.get('entry_index')
                entries = candidate.get(section) or []
                if not isinstance(index, int) or index < 0 or index >= len(entries):
                    continue
                if not any(excerpt in detail for detail in entries[index].get('details') or []):
                    continue
            if matched:
                evidence.append(record)
        rows.append({**requirement, 'status': 'matched' if matched else 'not_evidenced', 'weight': weights.get(skill),
                     'evidence': evidence, 'basis': 'Canonical extracted skill list' if matched else 'Not evidenced in resume',
                     'evidence_note': None if evidence else 'Source quotation unavailable' if matched else 'No supporting resume evidence found'})

    suggestions = []
    for row in rows:
        if row['status'] == 'not_evidenced':
            suggestions.append(f"If you have used {row['skill']}, describe that work in your resume with its context. Do not add skills you have not used.")
    if any(r['status'] == 'matched' and not r['evidence'] for r in rows):
        suggestions.append('For listed skills, add a clear example of your own work if you have one; source quotations were unavailable for some matches.')
    for section, label in (('experience', 'employment'), ('projects', 'project')):
        if any(not entry.get('details') for entry in candidate.get(section) or []):
            suggestions.append(f'Add factual descriptions of your contributions to {label} entries that currently have no details.')
    uncertain = sum(interval(entry.get('duration'))[0] is None for entry in candidate.get('experience') or [])
    if uncertain:
        suggestions.append('Clarify incomplete or invalid employment dates if known; do not estimate missing months or years.')
    if not candidate.get('education'):
        suggestions.append('If relevant, add your actual education and completion status; do not imply a qualification you have not earned.')

    result = {
        'version': 1, 'overall_score': analysis['overall_score'], 'scale': 100,
        'score_source': analysis.get('job_fit_method') or 'resume-quality',
        'advisory': ADVISORY, 'quality_components': quality,
        'requirements': rows, 'recommendations': suggestions,
        'experience': {'years': analysis['total_experience_years'], 'uncertain_entries': uncertain,
                       'rule': 'Union of compatible employment date ranges; gaps and overlap excluded. Seasons, mixed precision and invalid dates contribute no duration. Year-only ranges are approximate. Projects are not employment.'},
        'education': {'text_present': bool(candidate.get('education')), 'completion_verified': False,
                      'rule': 'The existing rule checks education text presence only, not degree equivalence, graduation or institution quality.'},
        'limitations': ['Vocabulary matching cannot establish proficiency or prove that an unlisted skill is absent.',
                        'In local scoring, skills mentioned only under preferred/nice-to-have headings count half; all other job-description skills count in full.',
                        'Evidence quotes are limited to short, attributable extracted passages; formatting quality is not scored.'],
        'blend': blend, 'job_components': [],
    }
    if not description:
        result['summary'] = 'No job description supplied. Overall score equals the existing resume completeness score; no job compatibility was assessed.'
    elif local:
        result['summary'] = (f"{len(analysis['matched_skills'])} of {len(analysis['matched_skills']) + len(analysis['missing_skills'])} recognized JD skills matched the extracted skill list. "
                             f"{len(analysis['missing_skills'])} recognized skills are not evidenced in the resume; this does not establish that the candidate lacks them.")
        result['job_components'] = job_match['score_components']
        result['experience'].update({'required_years': local['required_years'], 'score': job_match['experience_score'], 'note': job_match['experience_note']})
        result['education'].update({'degree_required': local['degree_required'], 'score': job_match['education_score'], 'note': job_match['education_note']})
        result['job_rule'] = 'Rounded weighted sum: skills 60%, experience 25%, education 15%. Within skills, preferred-only skills count half.' if local['skills_detected'] else 'No recognized JD skills: the existing fallback sets job fit to 35, overriding the component blend.'
    else:
        result['summary'] = 'The existing AI path supplied the job-fit score. The local requirement checks below verify explicit skill mentions; they do not explain or reproduce the provider judgment.'
        result['job_rule'] = 'Provider component judgments have no verifiable aggregation formula. No numeric component attribution is presented.'
        result['limitations'].append('AI scores, skill claims and narrative are unverified provider judgments. Local evidence checks may disagree; the original score is preserved.')
        verified = {row['skill'] for row in rows if row['status'] == 'matched'}
        result['unverified_provider_matches'] = list(dict.fromkeys(canonical_skill(s) for s in analysis.get('matched_skills') or [] if canonical_skill(s) not in verified))
    return result
