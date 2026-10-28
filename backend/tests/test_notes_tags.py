"""Recruiter notes and tags: validation limits, ownership, privacy and the
human-review policy (no endpoint reorders or auto-decides candidates)."""
import builtins
import importlib
import json
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError

import recruiter as r
from ai.privacy import candidate_payload
from network_guard import OfflineAsyncTestCase, network_guard
from test_recruiter import document, upload
from utils import limits


class NotesTagsTests(OfflineAsyncTestCase):
    def setUp(self):
        super().setUp()
        self.enterContext(patch.dict(r.workspaces, {}, clear=True))
        self.enterContext(patch.object(r, 'active_users', set()))
        self.changes = []
        async def user(): return 'one@example.invalid'
        self.routes = {route.name: route.endpoint for route in r.create_router(user, on_change=self.changes.append).routes}
        self.user = 'one@example.invalid'

    async def call(self, name, **kwargs):
        return await self.routes[name](user=kwargs.pop('user', self.user), **kwargs)

    async def setup_candidates(self, names=('Synthetic Candidate',), user=None):
        group = await self.call('create_group', body=r.Job(title='Developer', description='Required skills: Python, Docker'),
                                **({'user': user} if user else {}))
        files = [upload(document(name), name=f'{i}.docx') for i, name in enumerate(names)]
        batch = await self.call('upload_batch', group_id=group['id'], files=files, **({'user': user} if user else {}))
        return group, [o['candidate_id'] for o in batch['outcomes']]

    async def note(self, group, cid, text, **kwargs):
        return await self.call('add_note', group_id=group['id'], candidate_id=cid, body=r.NoteBody(text=text), **kwargs)

    async def tag(self, group, cid, tag, **kwargs):
        return await self.call('add_tag', group_id=group['id'], candidate_id=cid, body=r.TagBody(tag=tag), **kwargs)

    async def expect(self, status, coro):
        with self.assertRaises(HTTPException) as error:
            await coro
        self.assertEqual(error.exception.status_code, status)
        return error.exception

    # Notes ------------------------------------------------------------------
    async def test_note_create_edit_delete_in_creation_order(self):
        group, [cid] = await self.setup_candidates()
        first = await self.note(group, cid, 'Strong payments background.')
        second = await self.note(group, cid, 'Ask about Kubernetes.')
        self.assertNotEqual(first['id'], second['id'])
        self.assertIsNone(first['updated_at'])
        edited = await self.call('edit_note', group_id=group['id'], candidate_id=cid, note_id=first['id'], body=r.NoteBody(text='Edited note'))
        self.assertEqual(edited['text'], 'Edited note')
        self.assertTrue(edited['updated_at'])
        detail = await self.call('get_candidate', group_id=group['id'], candidate_id=cid)
        self.assertEqual([n['text'] for n in detail['notes']], ['Edited note', 'Ask about Kubernetes.'])
        await self.call('delete_note', group_id=group['id'], candidate_id=cid, note_id=first['id'])
        detail = await self.call('get_candidate', group_id=group['id'], candidate_id=cid)
        self.assertEqual([n['id'] for n in detail['notes']], [second['id']])
        await self.expect(404, self.call('delete_note', group_id=group['id'], candidate_id=cid, note_id=first['id']))

    async def test_note_text_is_cleaned_and_length_checked_after_cleaning(self):
        group, [cid] = await self.setup_candidates()
        note = await self.note(group, cid, '  Hello‮\x00 world \r\n\r\n\r\n\r\nSecond\tline  ')
        self.assertEqual(note['text'], 'Hello world\n\nSecond line')
        self.assertEqual(len((await self.note(group, cid, 'x' * limits.NOTE_CHARS))['text']), limits.NOTE_CHARS)
        await self.expect(422, self.note(group, cid, 'x' * (limits.NOTE_CHARS + 1)))
        await self.expect(422, self.note(group, cid, ' ​\n\t '))
        # Invisible characters cannot pad past the limit, and raw input is bounded by the schema.
        self.assertEqual(len((await self.note(group, cid, 'y' * limits.NOTE_CHARS + '​' * 50))['text']), limits.NOTE_CHARS)
        for raw in ('', 'z' * (limits.NOTE_CHARS * 2 + 1)):
            with self.subTest(length=len(raw)), self.assertRaises(ValidationError):
                r.NoteBody(text=raw)
        with self.assertRaises(ValidationError):
            r.NoteBody(text='ok', extra=True)

    async def test_note_count_limit(self):
        group, [cid] = await self.setup_candidates()
        with patch.object(limits, 'NOTES_PER_CANDIDATE', 3):
            for i in range(3):
                await self.note(group, cid, f'Note {i}')
            error = await self.expect(409, self.note(group, cid, 'One too many'))
            self.assertIn('limit', error.detail)
        self.assertEqual(limits.NOTES_PER_CANDIDATE, 100)

    async def test_note_html_is_stored_as_plain_text(self):
        group, [cid] = await self.setup_candidates()
        note = await self.note(group, cid, '<img src=x onerror=alert(1)> & "quotes"')
        self.assertEqual(note['text'], '<img src=x onerror=alert(1)> & "quotes"')  # Escaped on render, never interpreted.

    # Tags -------------------------------------------------------------------
    async def test_tags_are_case_insensitively_unique_and_keep_first_spelling(self):
        group, [cid] = await self.setup_candidates()
        await self.tag(group, cid, 'Team Lead')
        result = await self.tag(group, cid, '  team   lead ')
        self.assertEqual(result['tags'], ['Team Lead'])
        result = await self.tag(group, cid, 'C++')
        self.assertEqual(result['tags'], ['Team Lead', 'C++'])
        removed = await self.call('remove_tag', group_id=group['id'], candidate_id=cid, tag='TEAM LEAD')
        self.assertEqual(removed['tags'], ['C++'])
        await self.expect(404, self.call('remove_tag', group_id=group['id'], candidate_id=cid, tag='missing'))

    async def test_tag_length_charset_and_count_limits(self):
        group, [cid] = await self.setup_candidates()
        self.assertEqual((await self.tag(group, cid, 'x' * limits.TAG_CHARS))['tags'], ['x' * limits.TAG_CHARS])
        await self.expect(422, self.tag(group, cid, 'y' * (limits.TAG_CHARS + 1)))
        await self.expect(422, self.tag(group, cid, ' ​ '))
        for bad in ('=SUM(A1)', '+cmd', '-1', '@user', 'a/b', '<b>', '_hidden'):
            with self.subTest(tag=bad):
                await self.expect(422, self.tag(group, cid, bad))
        with self.assertRaises(ValidationError):
            r.TagBody(tag='')
        for i in range(limits.TAGS_PER_CANDIDATE - 1):
            await self.tag(group, cid, f'tag {i}')
        error = await self.expect(409, self.tag(group, cid, 'eleventh'))
        self.assertIn('limit', error.detail)
        # Re-adding an existing tag at the limit is still a harmless no-op.
        self.assertEqual(len((await self.tag(group, cid, 'TAG 0'))['tags']), limits.TAGS_PER_CANDIDATE)

    # Ownership ----------------------------------------------------------------
    async def test_other_users_and_mismatched_ids_get_404(self):
        group, [cid] = await self.setup_candidates()
        other_group, [other_cid] = await self.setup_candidates(user='two@example.invalid')
        note = await self.note(group, cid, 'Private note')
        await self.tag(group, cid, 'private')
        cases = [
            ('add_note', dict(group_id=group['id'], candidate_id=cid, body=r.NoteBody(text='x')), 'two@example.invalid'),
            ('edit_note', dict(group_id=group['id'], candidate_id=cid, note_id=note['id'], body=r.NoteBody(text='x')), 'two@example.invalid'),
            ('delete_note', dict(group_id=group['id'], candidate_id=cid, note_id=note['id']), 'two@example.invalid'),
            ('add_tag', dict(group_id=group['id'], candidate_id=cid, body=r.TagBody(tag='x')), 'two@example.invalid'),
            ('remove_tag', dict(group_id=group['id'], candidate_id=cid, tag='private'), 'two@example.invalid'),
            # A real candidate ID used under the wrong workspace, and a note ID under the wrong candidate.
            ('add_note', dict(group_id=group['id'], candidate_id=other_cid, body=r.NoteBody(text='x')), self.user),
            ('edit_note', dict(group_id=other_group['id'], candidate_id=other_cid, note_id=note['id'], body=r.NoteBody(text='x')), 'two@example.invalid'),
        ]
        for name, kwargs, user in cases:
            with self.subTest(endpoint=name, user=user):
                await self.expect(404, self.call(name, user=user, **kwargs))
        detail = await self.call('get_candidate', group_id=group['id'], candidate_id=cid)
        self.assertEqual(([n['text'] for n in detail['notes']], detail['tags']), (['Private note'], ['private']))

    # Privacy ------------------------------------------------------------------
    async def test_notes_and_tags_never_reach_the_ai_payload(self):
        group, [cid] = await self.setup_candidates()
        await self.note(group, cid, 'SECRET-NOTE-TEXT')
        await self.tag(group, cid, 'SECRET-TAG')
        seen = []
        def analyze(candidate, description, use_ai=False):
            seen.append(json.dumps(candidate_payload(candidate)) + json.dumps(candidate, default=str))
            return {'overall_score': 50, 'job_fit_method': 'rule-based', 'matched_skills': [], 'missing_skills': []}
        with patch.object(r, 'analyze_resume_for_job', side_effect=analyze):
            await self.call('analyze_candidate', group_id=group['id'], candidate_id=cid, body=r.AnalysisRequest(version=group['version'], use_ai=True))
        self.assertTrue(seen)
        for secret in ('SECRET-NOTE-TEXT', 'SECRET-TAG'):
            self.assertNotIn(secret, seen[0])

    async def test_mutations_trigger_persistence_hook(self):
        group, [cid] = await self.setup_candidates()
        before = len(self.changes)
        note = await self.note(group, cid, 'a')
        await self.call('edit_note', group_id=group['id'], candidate_id=cid, note_id=note['id'], body=r.NoteBody(text='b'))
        await self.call('delete_note', group_id=group['id'], candidate_id=cid, note_id=note['id'])
        await self.tag(group, cid, 'x')
        await self.tag(group, cid, 'X')  # No-op: nothing changed, nothing persisted.
        await self.call('remove_tag', group_id=group['id'], candidate_id=cid, tag='x')
        self.assertEqual(len(self.changes) - before, 5)

    # Human-review policy --------------------------------------------------------
    async def test_no_endpoint_reorders_or_decides_candidates(self):
        names = ('Zoe Zed', 'Amy Able', 'Max Middle')
        group, cids = await self.setup_candidates(names)
        for cid in cids:
            await self.note(group, cid, 'note')
            await self.tag(group, cid, 'reviewed')
            await self.call('analyze_candidate', group_id=group['id'], candidate_id=cid, body=r.AnalysisRequest(version=group['version']))
        detail = await self.call('get_group', group_id=group['id'])
        self.assertEqual([row['id'] for row in detail['candidates']], cids)  # Upload order, not score or name.
        self.assertEqual({row['status'] for row in detail['candidates']}, {'Not Reviewed'})
        self.assertEqual({row['revision'] for row in detail['candidates']}, {0})
        comparison = await self.call('compare', group_id=group['id'], body=r.Comparison(candidate_ids=list(reversed(cids)), version=group['version']))
        self.assertEqual([row['id'] for row in comparison['candidates']], list(reversed(cids)))  # The user's chosen order.


class NotesHTTPTests(OfflineAsyncTestCase):
    """Unauthenticated access is rejected before any workspace lookup."""
    @classmethod
    def setUpClass(cls):
        original = builtins.open
        account_path = Path(__file__).resolve().parents[1] / 'data' / 'users.json'
        def isolated(file, mode='r', *args, **kwargs):
            if isinstance(file, (str, Path)) and Path(file).resolve() == account_path:
                if mode != 'r':
                    raise AssertionError('Account writes forbidden')
                return StringIO('{}')
            return original(file, mode, *args, **kwargs)
        with network_guard(), patch('builtins.open', side_effect=isolated):
            cls.api = importlib.import_module('main')

    async def request(self, method, path, body=b'{}', token=''):
        sent = []
        async def receive():
            return {'type': 'http.request', 'body': body, 'more_body': False}
        async def send(message):
            sent.append(message)
        headers = [(b'content-type', b'application/json')] + ([(b'authorization', f'Bearer {token}'.encode())] if token else [])
        scope = {'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1', 'method': method, 'scheme': 'http',
                 'path': path, 'raw_path': path.encode(), 'query_string': b'', 'root_path': '', 'server': ('test', 80),
                 'client': ('synthetic', 1234), 'headers': headers}
        await self.api.app(scope, receive, send)
        return sent[0]['status']

    async def test_unauthenticated_requests_are_401(self):
        base = '/api/workspaces/g/candidates/c'
        for method, path in (('POST', f'{base}/notes'), ('PATCH', f'{base}/notes/n'), ('DELETE', f'{base}/notes/n'),
                             ('POST', f'{base}/tags'), ('DELETE', f'{base}/tags/x')):
            with self.subTest(method=method, path=path):
                self.assertEqual(await self.request(method, path, b'{"text":"x","tag":"x"}'), 401)

    async def test_signed_in_user_gets_404_for_unknown_workspace(self):
        with patch('main.get_email_from_token', return_value='one@example.invalid'), patch.dict(r.workspaces, {}, clear=True):
            self.assertEqual(await self.request('POST', '/api/workspaces/missing/candidates/c/notes', b'{"text":"x"}', 'synthetic'), 404)
