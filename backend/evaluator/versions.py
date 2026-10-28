"""Resume version snapshots and comparison against the same job description.

Snapshots keep only what is needed to compare evaluations (scores, skills and
requirement statuses), not the resume text. Score differences are estimates
from the same rules, not evidence of better hiring outcomes.
"""
import hashlib
import secrets

from utils.skills import canonical_skill

MAX_VERSIONS = 3
NOTE = ('Version comparison shows how the same rules scored each resume. A higher score is an estimate, '
        'not evidence of a better hiring outcome.')


def jd_fingerprint(job_description):
    text = ' '.join((job_description or '').casefold().split())
    return hashlib.sha256(text.encode()).hexdigest()[:16] if text else None


def version_snapshot(resume, analysis, job_description, analyzed_at):
    candidate = resume.get('candidate') or {}
    lines = ((analysis.get('explanation') or {}).get('requirement_lines') or {})
    first_line = next((line.strip() for line in (job_description or '').splitlines() if line.strip()), '')
    return {
        'version_id': secrets.token_urlsafe(8),
        'resume_id': resume.get('resume_id'),
        'filename': resume.get('filename'),
        'analyzed_at': analyzed_at,
        'jd_fingerprint': jd_fingerprint(job_description),
        'jd_title': first_line[:80] or None,
        'overall_score': analysis.get('overall_score'),
        'resume_quality_score': analysis.get('resume_quality_score'),
        'job_fit_score': analysis.get('job_fit_score'),
        'job_fit_method': analysis.get('job_fit_method'),
        'recommendation': analysis.get('recommendation'),
        'experience_years': analysis.get('total_experience_years'),
        'skills': list(candidate.get('skills') or []),
        'requirements': [{'text': row.get('text'), 'status': row.get('status')} for row in lines.get('rows') or []],
        'requirement_counts': lines.get('counts'),
    }


def record_version(versions, snapshot):
    """Newest first; re-analyzing the same resume against the same JD replaces its entry."""
    versions[:] = [v for v in versions if not (v['resume_id'] == snapshot['resume_id']
                                                and v['jd_fingerprint'] == snapshot['jd_fingerprint'])]
    versions.insert(0, snapshot)
    del versions[MAX_VERSIONS:]
    return versions


def compare_versions(newer, older):
    if not newer or not older:
        return None

    def delta(key):
        a, b = newer.get(key), older.get(key)
        return a - b if isinstance(a, (int, float)) and isinstance(b, (int, float)) else None

    new_skills = {canonical_skill(s): s for s in newer.get('skills') or []}
    old_skills = {canonical_skill(s): s for s in older.get('skills') or []}
    old_status = {row['text']: row['status'] for row in older.get('requirements') or []}
    changes = [{'text': row['text'], 'from': old_status[row['text']], 'to': row['status']}
               for row in newer.get('requirements') or []
               if row['text'] in old_status and old_status[row['text']] != row['status']]
    same_job = bool(newer.get('jd_fingerprint')) and newer.get('jd_fingerprint') == older.get('jd_fingerprint')
    notes = [NOTE]
    if not same_job:
        notes.insert(0, 'These versions were evaluated against different job descriptions (or none), so the scores are not directly comparable.')
    if newer.get('job_fit_method') != older.get('job_fit_method'):
        notes.insert(0, 'One version used AI job matching and the other used local rules; their job-fit scores are not equally calibrated.')
    return {
        'newer': newer['version_id'], 'older': older['version_id'], 'same_job': same_job,
        'deltas': {key: delta(key) for key in ('overall_score', 'resume_quality_score', 'job_fit_score', 'experience_years')},
        'skills_added': [new_skills[k] for k in new_skills if k not in old_skills],
        'skills_removed': [old_skills[k] for k in old_skills if k not in new_skills],
        'requirement_changes': changes,
        'notes': notes,
    }
