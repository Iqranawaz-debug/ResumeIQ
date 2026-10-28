"""Comparison CSV export: formula-injection neutralization, wording, ownership,
notes opt-in, and the user's own candidate order (no ranking)."""
import csv
import io
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError

import recruiter as r
from network_guard import OfflineAsyncTestCase, OfflineTestCase
from test_recruiter import document, upload


def parse(content):
    return list(csv.reader(io.StringIO(content)))


class CsvHelperTests(OfflineTestCase):
    def test_formula_prefixes_are_neutralized(self):
        for value in ('=1+1', '+SUM(A1)', '-2+3', '@cmd', '\tTAB', '\rCR', '=HYPERLINK("http://x","click")'):
            with self.subTest(value=value):
                self.assertEqual(r.safe_cell(value), "'" + value)
        for value, expected in (('Plain text', 'Plain text'), ('a=b', 'a=b'), ('C++', 'C++'), (8.25, '8.25'), (None, '')):
            with self.subTest(value=value):
                self.assertEqual(r.safe_cell(value), expected)

    def test_score_wording_matches_the_ui(self):
        self.assertEqual(r.score_label({'overall_score': 80, 'job_fit_method': 'rule-based'}), '80 / 100 (Local score)')
        self.assertEqual(r.score_label({'overall_score': 75, 'job_fit_method': 'ai'}), '75 / 100 (AI score)')
        self.assertEqual(r.score_label({'overall_score': 61, 'job_fit_method': None}), '61 / 100 (Local score)')
        self.assertEqual(r.score_label(None), 'Not scored yet')

    def test_every_cell_is_neutralized_and_quoted(self):
        row = {'name': '=EVIL()', 'status': 'Shortlisted', 'tags': ['C++', 'Team lead'], 'notes': [{'text': '+cmd'}, {'text': 'second'}],
               'analysis': {'overall_score': 80, 'job_fit_method': 'rule-based', 'matched_skills': ['python', 'aws'],
                            'missing_skills': ['golang'], 'total_experience_years': 8.25}}
        content = r.comparison_csv([row], include_notes=True)
        header, data = parse(content)
        self.assertEqual(header, r.CSV_COLUMNS + ['Notes'])
        self.assertEqual(data, ["'=EVIL()", 'Shortlisted', 'C++; Team lead', 'Python; AWS', 'Go', '8.25', '80 / 100 (Local score)', "'+cmd | second"])
        self.assertTrue(all(line.startswith('"') for line in content.strip().split('\r\n')))

    def test_notes_column_only_when_requested(self):
        row = {'name': 'A', 'status': 'Not Reviewed', 'notes': [{'text': 'PRIVATE'}], 'analysis': {}}
        content = r.comparison_csv([row], include_notes=False)
        self.assertNotIn('PRIVATE', content)
        self.assertEqual(parse(content)[0], r.CSV_COLUMNS)

    def test_filename_is_safe(self):
        name = r.export_filename('../../Senior Engineer / "Payments"!', 'csv')
        self.assertRegex(name, r'^resumeiq-comparison-senior-engineer-payments-\d{4}-\d{2}-\d{2}\.csv$')
        self.assertTrue(r.export_filename('!!!', 'csv').startswith('resumeiq-comparison-workspace-'))


class CsvEndpointTests(OfflineAsyncTestCase):
    def setUp(self):
        super().setUp()
        self.enterContext(patch.dict(r.workspaces, {}, clear=True))
        self.enterContext(patch.object(r, 'active_users', set()))
        async def user(): return 'one@example.invalid'
        self.routes = {route.name: route.endpoint for route in r.create_router(user).routes}
        self.user = 'one@example.invalid'

    async def call(self, name, **kwargs):
        return await self.routes[name](user=kwargs.pop('user', self.user), **kwargs)

    async def workspace(self, names=('=Formula Person', 'Amy Able')):
        group = await self.call('create_group', body=r.Job(title='Developer', description='Required skills: Python, Docker'))
        files = [upload(document(name), name=f'{i}.docx') for i, name in enumerate(names)]
        batch = await self.call('upload_batch', group_id=group['id'], files=files)
        ids = [o['candidate_id'] for o in batch['outcomes']]
        for cid in ids:
            await self.call('analyze_candidate', group_id=group['id'], candidate_id=cid, body=r.AnalysisRequest(version=group['version']))
        return group, ids

    async def export(self, group, ids, **kwargs):
        body = r.ComparisonExport(candidate_ids=ids, version=group['version'], **{k: v for k, v in kwargs.items() if k == 'include_notes'})
        return await self.call('export_comparison_csv', group_id=group['id'], body=body, **{k: v for k, v in kwargs.items() if k == 'user'})

    async def test_export_matches_comparison_in_the_users_order_and_excludes_notes_by_default(self):
        group, ids = await self.workspace()
        # Any stored value can be formula-like (here the name); set it directly rather than relying on extraction.
        r.workspaces[self.user][group['id']]['candidates'][ids[0]]['candidate']['name'] = '=Formula Person'
        await self.call('add_note', group_id=group['id'], candidate_id=ids[0], body=r.NoteBody(text='PRIVATE NOTE'))
        await self.call('add_tag', group_id=group['id'], candidate_id=ids[0], body=r.TagBody(tag='Phone screen'))
        reversed_ids = list(reversed(ids))
        result = await self.export(group, reversed_ids)
        rows = parse(result['content'])
        self.assertFalse(result['include_notes'])
        self.assertNotIn('PRIVATE NOTE', result['content'])
        self.assertEqual([row[0] for row in rows[1:]], ['Amy Able', "'=Formula Person"])  # Selection order, neutralized.
        self.assertEqual(rows[2][2], 'Phone screen')
        self.assertRegex(rows[1][6], r'^\d+ / 100 \(Local score\)$')
        self.assertTrue(result['filename'].endswith('.csv'))
        with_notes = await self.export(group, ids, include_notes=True)
        self.assertIn('PRIVATE NOTE', with_notes['content'])

    async def test_export_does_not_change_statuses_or_candidate_order(self):
        group, ids = await self.workspace(('Zed', 'Able', 'Mid'))
        before = await self.call('get_group', group_id=group['id'])
        await self.export(group, ids)
        after = await self.call('get_group', group_id=group['id'])
        self.assertEqual([(c['id'], c['status'], c['revision']) for c in after['candidates']],
                         [(c['id'], c['status'], c['revision']) for c in before['candidates']])
        self.assertEqual([c['id'] for c in after['candidates']], ids)

    async def test_export_requires_ownership_current_version_and_analysis(self):
        group, ids = await self.workspace()
        with self.assertRaises(HTTPException) as error:
            await self.export(group, ids, user='two@example.invalid')
        self.assertEqual(error.exception.status_code, 404)
        with self.assertRaises(HTTPException) as error:
            await self.call('export_comparison_csv', group_id=group['id'], body=r.ComparisonExport(candidate_ids=ids, version=group['version'] + 1))
        self.assertEqual(error.exception.status_code, 409)
        with self.assertRaises(HTTPException) as error:
            await self.call('export_comparison_csv', group_id=group['id'], body=r.ComparisonExport(candidate_ids=[ids[0], ids[0]], version=group['version']))
        self.assertEqual(error.exception.status_code, 422)
        with self.assertRaises(HTTPException) as error:
            await self.call('export_comparison_csv', group_id=group['id'], body=r.ComparisonExport(candidate_ids=['missing'], version=group['version']))
        self.assertEqual(error.exception.status_code, 404)

    async def test_unanalyzed_candidates_are_not_exported(self):
        group = await self.call('create_group', body=r.Job(title='Developer', description='Python'))
        batch = await self.call('upload_batch', group_id=group['id'], files=[upload(document('A'))])
        with self.assertRaises(HTTPException) as error:
            await self.export(group, [batch['outcomes'][0]['candidate_id']])
        self.assertEqual(error.exception.status_code, 409)

    async def test_request_schema(self):
        with self.assertRaises(ValidationError):
            r.ComparisonExport(candidate_ids=[], version=1)
        with self.assertRaises(ValidationError):
            r.ComparisonExport(candidate_ids=['a'] * (r.MAX_COMPARE + 1), version=1)
        with self.assertRaises(ValidationError):
            r.ComparisonExport(candidate_ids=['a'], version=1, format='xlsx')
        self.assertFalse(r.ComparisonExport(candidate_ids=['a'], version=1).include_notes)
