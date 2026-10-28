"""Bounded single-process, user-owned recruiter resources. No raw file retention."""
import hashlib
import secrets
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool
from evaluator.analyzer import analyze_resume_for_job
from utils.candidate_processing import process_resume
from utils.upload import read_upload
from utils import limits
from utils.text import clean_note, clean_tag, valid_tag

MAX_FILES = 5
BATCH_BYTES = 10 * 1024**2  # Existing request middleware remains at its lower configured cap.
MAX_GROUPS = 5
MAX_CANDIDATES = 20  # Per user, across groups.
MAX_OWNERS = 100  # Global ceiling; process restart clears all recruiter data.
MAX_BATCHES = 5  # Per workspace; each holds at most MAX_FILES outcomes.
MAX_COMPARE = 4
MAX_ACTIVE = 2  # Global expensive operations, one per authenticated user; no queue.
workspaces = {}
active_users = set()
Status = Literal['Not Reviewed', 'Under Review', 'Shortlisted', 'Not Selected']


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Job(StrictModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=limits.TEXT_CHARS)


class JobUpdate(Job):
    version: int = Field(ge=1, strict=True)


class AnalysisRequest(StrictModel):
    version: int = Field(ge=1, strict=True)
    use_ai: bool = False


class Review(StrictModel):
    status: Status
    revision: int = Field(ge=0, strict=True)


class Comparison(StrictModel):
    candidate_ids: list[str] = Field(min_length=1, max_length=MAX_COMPARE)
    version: int = Field(ge=1, strict=True)


class NoteBody(StrictModel):
    # Raw bound only; the cleaned text is checked against NOTE_CHARS.
    text: str = Field(min_length=1, max_length=limits.NOTE_CHARS * 2)


class TagBody(StrictModel):
    tag: str = Field(min_length=1, max_length=limits.TAG_CHARS * 4)


def now():
    return datetime.now(timezone.utc).isoformat()


def group_for(user, group_id):
    group = workspaces.get(user, {}).get(group_id)
    if group is None:
        raise HTTPException(404, 'Workspace not found.')
    return group


def candidate_for(group, candidate_id):
    candidate = group['candidates'].get(candidate_id)
    if candidate is None:
        raise HTTPException(404, 'Candidate not found.')
    return candidate


def note_text(value):
    text = clean_note(value)
    if not text:
        raise HTTPException(422, 'Note text is required.')
    if len(text) > limits.NOTE_CHARS:
        raise HTTPException(422, f'Notes are limited to {limits.NOTE_CHARS} characters.')
    return text


def tag_text(value):
    tag = clean_tag(value)
    if not 1 <= len(tag) <= limits.TAG_CHARS:
        raise HTTPException(422, f'Tags must be 1-{limits.TAG_CHARS} characters.')
    if not valid_tag(tag):
        raise HTTPException(422, "Tags may contain letters, numbers, spaces and + # . & ' - and must start with a letter or number.")
    return tag


def note_for(record, note_id):
    note = next((n for n in record.setdefault('notes', []) if n['id'] == note_id), None)
    if note is None:
        raise HTTPException(404, 'Note not found.')
    return note


def current(group, version):
    if group['version'] != version:
        raise HTTPException(409, 'Job description changed. Refresh and analyze the current version.')


@contextmanager
def processing(user):
    # Admission and release run on the event-loop thread, with no intervening await.
    if user in active_users or len(active_users) >= MAX_ACTIVE:
        raise HTTPException(409, 'Processing capacity is busy. Retry after the current operation.')
    active_users.add(user)
    try:
        yield
    finally:
        active_users.discard(user)


def summary(record, group):
    candidate = record['candidate']
    valid = record.get('analysis_version') == group['version']
    analysis = record.get('analysis') if valid else None
    return {key: record[key] for key in ('id', 'filename', 'status', 'revision', 'created_at')} | {
        'name': candidate.get('name'), 'skills': candidate.get('skills') or [],
        'education': candidate.get('education') or [],
        'employment_titles': [e.get('title') for e in candidate.get('experience') or [] if e.get('title')],
        'processing_status': record.get('processing_status', 'completed'),
        'analysis_state': 'completed' if analysis else 'outdated' if record.get('analysis_version') else 'pending',
        'analysis_error': record.get('analysis_error'),
        'overall_score': analysis.get('overall_score') if analysis else None,
        'score_source': analysis.get('job_fit_method') if analysis else None,
        'matched_skills': analysis.get('matched_skills', []) if analysis else [],
        'missing_skills': analysis.get('missing_skills', []) if analysis else [],
        # Private reviewer annotations: owner-only, never part of record['candidate'] (the AI payload source).
        'tags': list(record.get('tags') or []),
        'notes': [dict(note) for note in record.get('notes') or []],
    }


def user_data_summary(user):
    groups = workspaces.get(user, {})
    return {'workspaces': len(groups), 'candidates': sum(len(g['candidates']) for g in groups.values())}


def remove_user_data(user):
    """Erase every workspace the user owns. Refuses while an upload/analysis runs."""
    if user in active_users:
        raise HTTPException(409, 'Wait for processing to finish before deleting your data.')
    workspaces.pop(user, None)


def group_summary(group):
    return {k: group[k] for k in ('id', 'title', 'version', 'created_at', 'updated_at')} | {'candidate_count': len(group['candidates'])}


def create_router(require_user, on_change=None):
    router = APIRouter(prefix='/api/workspaces', dependencies=[Depends(require_user)])

    def changed(user):
        # Persistence hook (no-op unless storage is enabled).
        if on_change:
            on_change(user)

    @router.get('')
    async def list_groups(user: str = Depends(require_user)):
        return {'workspaces': [group_summary(g) for g in workspaces.get(user, {}).values()],
                'limits': {'files': MAX_FILES, 'batch_bytes': BATCH_BYTES, 'file_bytes': limits.RESUME_BYTES,
                           'candidates': MAX_CANDIDATES, 'groups': MAX_GROUPS, 'compare': MAX_COMPARE,
                           'note_chars': limits.NOTE_CHARS, 'notes': limits.NOTES_PER_CANDIDATE,
                           'tags': limits.TAGS_PER_CANDIDATE, 'tag_chars': limits.TAG_CHARS}}

    @router.post('')
    async def create_group(body: Job, user: str = Depends(require_user)):
        if not body.title.strip() or not body.description.strip():
            raise HTTPException(422, 'Job title and description are required.')
        if user not in workspaces and len(workspaces) >= MAX_OWNERS:
            raise HTTPException(409, 'Workspace storage capacity reached.')
        groups = workspaces.setdefault(user, {})
        if len(groups) >= MAX_GROUPS:
            raise HTTPException(409, 'Workspace limit reached. Remove an unused workspace first.')
        group = {'id': secrets.token_urlsafe(16), 'title': body.title.strip(), 'description': body.description.strip(),
                 'version': 1, 'created_at': now(), 'updated_at': now(), 'candidates': {}, 'batches': []}
        groups[group['id']] = group
        changed(user)
        return group_summary(group)

    @router.get('/{group_id}')
    async def get_group(group_id: str, user: str = Depends(require_user)):
        group = group_for(user, group_id)
        return group_summary(group) | {'description': group['description'], 'batches': group['batches'],
                                      'candidates': [summary(c, group) for c in group['candidates'].values()]}

    @router.patch('/{group_id}')
    async def update_group(group_id: str, body: JobUpdate, user: str = Depends(require_user)):
        group = group_for(user, group_id)
        current(group, body.version)
        if not body.title.strip() or not body.description.strip():
            raise HTTPException(422, 'Job title and description are required.')
        if body.description.strip() != group['description']:
            group['version'] += 1
            for record in group['candidates'].values():
                record['analysis'] = None  # Never serve old scores as current comparisons.
                record['analysis_error'] = None
        group.update(title=body.title.strip(), description=body.description.strip(), updated_at=now())
        changed(user)
        return group_summary(group)

    @router.delete('/{group_id}')
    async def delete_group(group_id: str, user: str = Depends(require_user)):
        group_for(user, group_id)
        if user in active_users:
            raise HTTPException(409, 'Wait for processing before removing a workspace.')
        del workspaces[user][group_id]
        if not workspaces[user]:
            del workspaces[user]
        changed(user)
        return {'message': 'Workspace removed.'}

    @router.post('/{group_id}/uploads')
    async def upload_batch(group_id: str, files: list[UploadFile] = File(...), user: str = Depends(require_user)):
        group = group_for(user, group_id)
        if not 1 <= len(files) <= MAX_FILES:
            raise HTTPException(422, f'Select between 1 and {MAX_FILES} files.')
        with processing(user):
            # Preflight actual parser-measured sizes, then bounded reads; no partial
            # commits when the aggregate batch budget is exceeded.
            if sum(file.size or 0 for file in files) > BATCH_BYTES:
                raise HTTPException(413, 'Batch exceeds the 10 MB aggregate limit.')
            payloads, outcomes, total = [], [], 0
            for index, file in enumerate(files):
                filename = (file.filename or 'Unnamed').replace('\\', '/').rsplit('/', 1)[-1]
                filename = ''.join(c for c in filename if c.isprintable())[:160] or 'Unnamed'
                outcome = {'index': index, 'filename': filename, 'state': 'failed', 'kind': 'validation'}
                outcomes.append(outcome)
                try:
                    content = await read_upload(file, ('pdf', 'docx'), limits.RESUME_BYTES)
                    total += len(content)
                    if total > BATCH_BYTES:
                        raise HTTPException(413, 'Batch exceeds the 10 MB aggregate limit.')
                    payloads.append((filename, content, outcome))
                except HTTPException as exc:
                    outcome['message'] = exc.detail
                finally:
                    await file.close()
            if total > BATCH_BYTES:
                raise HTTPException(413, 'Batch exceeds the 10 MB aggregate limit.')
            for filename, content, outcome in payloads:
                digest = hashlib.sha256(content).hexdigest()
                duplicate = next((c for c in group['candidates'].values() if c['digest'] == digest), None)
                if duplicate:
                    outcome.update(state='completed', kind='duplicate', candidate_id=duplicate['id'], message='Already present in this workspace; no duplicate created.')
                    continue
                count = sum(len(g['candidates']) for g in workspaces[user].values())
                if count >= MAX_CANDIDATES:
                    outcome.update(kind='capacity', message='Candidate limit reached. Remove an unused candidate first.')
                    continue
                try:
                    candidate = await run_in_threadpool(process_resume, filename, content)
                    record = {'id': secrets.token_urlsafe(16), 'filename': filename, 'digest': digest,
                              'candidate': candidate, 'status': 'Not Reviewed', 'revision': 0,
                              'created_at': now(), 'audit': [], 'analysis': None, 'notes': [], 'tags': []}
                    group['candidates'][record['id']] = record
                    outcome.update(state='completed', kind='success', candidate_id=record['id'], message='Extracted locally.')
                except HTTPException as exc:
                    outcome.update(kind='parsing', message=exc.detail)
                except Exception:
                    outcome.update(kind='processing', message='Could not process this resume. Retry with a readable document.')
            batch = {'id': secrets.token_urlsafe(16), 'created_at': now(), 'outcomes': outcomes,
                     'total': len(outcomes), 'completed': sum(o['state'] == 'completed' for o in outcomes),
                     'failed': sum(o['state'] == 'failed' for o in outcomes), 'pending': 0}
            group['batches'].insert(0, batch)
            del group['batches'][MAX_BATCHES:]
            group['updated_at'] = now()
            changed(user)
            return batch

    @router.get('/{group_id}/candidates/{candidate_id}')
    async def get_candidate(group_id: str, candidate_id: str, user: str = Depends(require_user)):
        group = group_for(user, group_id)
        record = candidate_for(group, candidate_id)
        return summary(record, group) | {'candidate': record['candidate'], 'analysis': record.get('analysis'),
                                         'audit': record['audit'], 'analysis_version': record.get('analysis_version')}

    @router.delete('/{group_id}/candidates/{candidate_id}')
    async def delete_candidate(group_id: str, candidate_id: str, user: str = Depends(require_user)):
        group = group_for(user, group_id)
        candidate_for(group, candidate_id)
        if user in active_users:
            raise HTTPException(409, 'Wait for processing before removing a candidate.')
        del group['candidates'][candidate_id]
        group['updated_at'] = now()
        changed(user)
        return {'message': 'Candidate removed.'}

    @router.post('/{group_id}/candidates/{candidate_id}/analyze')
    async def analyze_candidate(group_id: str, candidate_id: str, body: AnalysisRequest, user: str = Depends(require_user)):
        group = group_for(user, group_id)
        record = candidate_for(group, candidate_id)
        current(group, body.version)
        if record.get('analysis') and record.get('analysis_version') == body.version and record.get('use_ai') == body.use_ai:
            return {'analysis': record['analysis'], 'version': body.version}
        with processing(user):
            record['processing_status'] = 'processing'
            try:
                result = await run_in_threadpool(analyze_resume_for_job, record['candidate'], group['description'], use_ai=body.use_ai)
                current(group, body.version)
                record.update(analysis=result, analysis_version=body.version, use_ai=body.use_ai, analysis_error=None)
                return {'analysis': result, 'version': body.version}
            except HTTPException:
                raise
            except Exception as exc:
                record['analysis_error'] = 'Analysis unavailable. Retry this candidate.'
                raise HTTPException(503, record['analysis_error']) from exc
            finally:
                record['processing_status'] = 'completed'
                group['updated_at'] = now()
                changed(user)

    @router.patch('/{group_id}/candidates/{candidate_id}/review')
    async def review_candidate(group_id: str, candidate_id: str, body: Review, user: str = Depends(require_user)):
        group = group_for(user, group_id)
        record = candidate_for(group, candidate_id)
        if body.revision != record['revision']:
            raise HTTPException(409, 'Review status changed. Refresh before updating.')
        if body.status != record['status']:
            record['audit'].append({'previous': record['status'], 'status': body.status, 'at': now(), 'actor': user})
            del record['audit'][:-10]
            record.update(status=body.status, revision=record['revision'] + 1)
            group['updated_at'] = now()
            changed(user)
        return summary(record, group)

    @router.post('/{group_id}/candidates/{candidate_id}/notes', status_code=201)
    async def add_note(group_id: str, candidate_id: str, body: NoteBody, user: str = Depends(require_user)):
        group = group_for(user, group_id)
        record = candidate_for(group, candidate_id)
        notes = record.setdefault('notes', [])
        if len(notes) >= limits.NOTES_PER_CANDIDATE:
            raise HTTPException(409, f'Note limit reached ({limits.NOTES_PER_CANDIDATE}). Delete a note first.')
        note = {'id': secrets.token_urlsafe(12), 'text': note_text(body.text), 'created_at': now(), 'updated_at': None}
        notes.append(note)
        group['updated_at'] = now()
        changed(user)
        return dict(note)

    @router.patch('/{group_id}/candidates/{candidate_id}/notes/{note_id}')
    async def edit_note(group_id: str, candidate_id: str, note_id: str, body: NoteBody, user: str = Depends(require_user)):
        group = group_for(user, group_id)
        note = note_for(candidate_for(group, candidate_id), note_id)
        note.update(text=note_text(body.text), updated_at=now())
        group['updated_at'] = now()
        changed(user)
        return dict(note)

    @router.delete('/{group_id}/candidates/{candidate_id}/notes/{note_id}')
    async def delete_note(group_id: str, candidate_id: str, note_id: str, user: str = Depends(require_user)):
        group = group_for(user, group_id)
        record = candidate_for(group, candidate_id)
        note = note_for(record, note_id)
        record['notes'] = [n for n in record['notes'] if n is not note]
        group['updated_at'] = now()
        changed(user)
        return {'message': 'Note deleted.'}

    @router.post('/{group_id}/candidates/{candidate_id}/tags')
    async def add_tag(group_id: str, candidate_id: str, body: TagBody, user: str = Depends(require_user)):
        group = group_for(user, group_id)
        record = candidate_for(group, candidate_id)
        tags = record.setdefault('tags', [])
        tag = tag_text(body.tag)
        # Case-insensitive unique: re-adding an existing tag is a no-op that keeps its first spelling.
        if tag.casefold() not in {t.casefold() for t in tags}:
            if len(tags) >= limits.TAGS_PER_CANDIDATE:
                raise HTTPException(409, f'Tag limit reached ({limits.TAGS_PER_CANDIDATE}). Remove a tag first.')
            tags.append(tag)
            group['updated_at'] = now()
            changed(user)
        return {'tags': list(tags)}

    @router.delete('/{group_id}/candidates/{candidate_id}/tags/{tag}')
    async def remove_tag(group_id: str, candidate_id: str, tag: str, user: str = Depends(require_user)):
        group = group_for(user, group_id)
        record = candidate_for(group, candidate_id)
        tags = record.setdefault('tags', [])
        key = clean_tag(tag).casefold()
        if key not in {t.casefold() for t in tags}:
            raise HTTPException(404, 'Tag not found.')
        record['tags'] = [t for t in tags if t.casefold() != key]
        group['updated_at'] = now()
        changed(user)
        return {'tags': list(record['tags'])}

    @router.post('/{group_id}/comparison')
    async def compare(group_id: str, body: Comparison, user: str = Depends(require_user)):
        group = group_for(user, group_id)
        current(group, body.version)
        if len(set(body.candidate_ids)) != len(body.candidate_ids):
            raise HTTPException(422, 'Select distinct candidates.')
        rows = []
        for candidate_id in body.candidate_ids:
            record = candidate_for(group, candidate_id)
            if record.get('analysis_version') != group['version'] or not record.get('analysis'):
                raise HTTPException(409, 'Analyze every selected candidate against the current job description first.')
            rows.append(summary(record, group) | {'candidate': record['candidate'], 'analysis': record['analysis']})
        return {'version': group['version'], 'candidates': rows,
                'notice': 'Human review only. No automatic ranking or decisions. AI and local scores are not equally calibrated; provider judgments are not locally verified.'}

    return router
