"""Certification extraction, sample demo, resume versions, opt-in SQLite
persistence and the health endpoint. Synthetic data only; no provider calls."""
import builtins
import importlib
import json
import sqlite3
import tempfile
import time
from contextlib import closing
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import samples
from evaluator.analyzer import analyze_resume_for_job
from evaluator.versions import compare_versions, jd_fingerprint, record_version, version_snapshot
from extractor.extractor import extract_candidate_info
from matcher.requirement_lines import evaluate_requirement_lines
from network_guard import OfflineAsyncTestCase, OfflineTestCase, network_guard
from utils.candidate_processing import process_resume
from utils.persistence import Store

RESUME = ('Jordan Example\njordan@example.invalid\nSkills\nPython\nExperience\nEngineer\n2019 - 2023\nBuilt Python services.\n'
          'Certifications\n- AWS Certified Solutions Architect – Associate (2022)\n• CompTIA Security+\nEducation\nBSc 2018')


def setUpModule():
    global api, recruiter
    original = builtins.open
    account_path = Path(__file__).resolve().parents[1] / 'data' / 'users.json'
    def isolated(file, mode='r', *args, **kwargs):
        if isinstance(file, (str, Path)) and Path(file).resolve() == account_path:
            if mode != 'r':
                raise AssertionError('Account writes forbidden')
            return StringIO('{}')
        return original(file, mode, *args, **kwargs)
    with network_guard(), patch('builtins.open', side_effect=isolated):
        api = importlib.import_module('main')
        recruiter = importlib.import_module('recruiter')


class CertificationTests(OfflineTestCase):
    def test_entries_are_extracted_verbatim_without_bullets(self):
        self.assertEqual(extract_candidate_info(RESUME)['certifications'],
                         ['AWS Certified Solutions Architect – Associate (2022)', 'CompTIA Security+'])
        self.assertEqual(extract_candidate_info('Experience\nEngineer')['certifications'], [])

    def test_requirements_match_listed_certifications(self):
        rows = evaluate_requirement_lines(extract_candidate_info(RESUME),
                                          'Requirements:\n- AWS certification\n- Security+ certification\n- CISSP certification required')['rows']
        self.assertEqual([r['status'] for r in rows], ['matched', 'matched', 'not_evidenced'])
        self.assertEqual(rows[0]['evidence'][0]['section'], 'certifications')
        self.assertIn('not verified', rows[0]['reason'])
        self.assertIn('none mention', rows[2]['reason'])

    def test_heading_without_entries_is_unclear(self):
        candidate = extract_candidate_info('Experience\nEngineer\n2019 - 2023\nCertifications\nEducation\nBSc 2018')
        row = evaluate_requirement_lines(candidate, 'Requirements:\n- PMP certification')['rows'][0]
        self.assertEqual(row['status'], 'unclear')


class SampleTests(OfflineAsyncTestCase):
    def setUp(self):
        super().setUp()
        for target in (api.validated_resumes, api.upload_versions, api.evaluation_histories, api.resume_versions):
            self.enterContext(patch.dict(target, {}, clear=True))

        async def inline(function, *args, **kwargs):
            return function(*args, **kwargs)
        self.enterContext(patch.object(api, 'run_in_threadpool', inline))

    def test_sample_is_fictional_and_exercises_every_view(self):
        candidate = process_resume(samples.SAMPLE_FILENAME, samples.SAMPLE_RESUME.encode(),
                                   lambda name, content, stats: content.decode())
        self.assertIn('example.invalid', candidate['email'])
        with patch('evaluator.analyzer.match_resume_to_job_ai', side_effect=AssertionError('No AI')):
            analysis = analyze_resume_for_job(candidate, samples.SAMPLE_JOB_DESCRIPTION, use_ai=False)
        counts = analysis['explanation']['requirement_lines']['counts']
        self.assertTrue(all(counts[status] for status in ('matched', 'partial', 'not_evidenced')))
        self.assertTrue(analysis['impacts']['items'])
        self.assertTrue(candidate['certifications'])

    async def test_sample_endpoint_stores_resume_and_returns_job_description(self):
        result = await api.upload_sample('one@example.invalid')
        self.assertEqual(result['sample_job_description'], samples.SAMPLE_JOB_DESCRIPTION)
        self.assertEqual(api.validated_resumes['one@example.invalid']['resume_id'], result['resume_id'])
        self.assertEqual(result['candidate']['name'], 'Alex Rivera')
        self.assertEqual(result['candidate']['document_checks']['format'], 'sample')
        analysis = await api.analyze_resume(samples.SAMPLE_JOB_DESCRIPTION, result['resume_id'], None, 'one@example.invalid', use_ai=False)
        self.assertEqual(len(analysis['versions']), 1)
        self.assertIsNone(analysis['version_comparison'])


class VersionTests(OfflineTestCase):
    def snap(self, resume_id, skills, jd, score, rows=()):
        analysis = {'overall_score': score, 'resume_quality_score': score, 'job_fit_score': score, 'job_fit_method': 'rule-based',
                    'recommendation': 'Consider', 'total_experience_years': 3,
                    'explanation': {'requirement_lines': {'rows': [{'text': t, 'status': s} for t, s in rows], 'counts': {}}}}
        return version_snapshot({'resume_id': resume_id, 'filename': f'{resume_id}.pdf', 'candidate': {'skills': skills}}, analysis, jd, 'now')

    def test_fingerprint_ignores_case_and_whitespace(self):
        self.assertEqual(jd_fingerprint('Python  Engineer\n'), jd_fingerprint('python engineer'))
        self.assertIsNone(jd_fingerprint('  '))

    def test_record_keeps_three_newest_and_replaces_reanalysis(self):
        versions = []
        for i in range(4):
            record_version(versions, self.snap(f'r{i}', [], 'JD', i))
        self.assertEqual([v['resume_id'] for v in versions], ['r3', 'r2', 'r1'])
        record_version(versions, self.snap('r3', [], 'JD', 99))
        self.assertEqual([(v['resume_id'], v['overall_score']) for v in versions], [('r3', 99), ('r2', 2), ('r1', 1)])

    def test_comparison_reports_deltas_skills_and_status_changes(self):
        old = self.snap('a', ['Python', 'jQuery'], 'JD', 50, [('Kubernetes', 'not_evidenced'), ('Python', 'matched')])
        new = self.snap('b', ['python', 'Kubernetes'], 'jd', 62, [('Kubernetes', 'matched'), ('Python', 'matched')])
        result = compare_versions(new, old)
        self.assertTrue(result['same_job'])
        self.assertEqual(result['deltas']['overall_score'], 12)
        self.assertEqual((result['skills_added'], result['skills_removed']), (['Kubernetes'], ['jQuery']))
        self.assertEqual(result['requirement_changes'], [{'text': 'Kubernetes', 'from': 'not_evidenced', 'to': 'matched'}])
        self.assertIn('not evidence of a better hiring outcome', ' '.join(result['notes']))

    def test_different_job_descriptions_are_flagged(self):
        result = compare_versions(self.snap('b', [], 'JD one', 60), self.snap('a', [], 'JD two', 50))
        self.assertFalse(result['same_job'])
        self.assertIn('different job descriptions', result['notes'][0])
        self.assertIsNone(compare_versions(None, None))

    def test_snapshot_keeps_no_resume_text(self):
        snap = self.snap('a', ['Python'], 'Senior Engineer\nRequirements', 50)
        self.assertEqual(snap['jd_title'], 'Senior Engineer')
        self.assertNotIn('candidate', snap)


class PersistenceTests(OfflineTestCase):
    def setUp(self):
        super().setUp()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / 'resumeiq.db'

    def test_disabled_store_is_a_no_op(self):
        store = Store(None)
        store.save_user('one', {'history': [1]})
        self.assertFalse(store.enabled)
        self.assertEqual(store.load_all(60), {})

    def test_round_trip_delete_and_empty_payloads(self):
        store = Store(self.path)
        store.save_user('one', {'history': [{'score': 70}], 'resume': None})
        loaded = store.load_all(3600)
        self.assertEqual(loaded['one'][0]['history'], [{'score': 70}])
        store.save_user('one', {'history': [], 'resume': None})
        self.assertEqual(store.load_all(3600), {})
        store.save_user('two', {'history': [1]}); store.delete_user('two')
        self.assertEqual(store.load_all(3600), {})

    def test_expired_and_damaged_rows_are_dropped(self):
        store = Store(self.path)
        store.save_user('old', {'history': [1]})
        store.save_user('bad', {'history': [1]})
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('UPDATE user_data SET updated_at = ? WHERE username = ?', (time.time() - 7200, 'old'))
            db.execute("UPDATE user_data SET payload = '{broken' WHERE username = 'bad'")
        self.assertEqual(store.load_all(3600), {})
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT username FROM user_data").fetchall(), [('bad',)])


class PersistenceIntegrationTests(OfflineAsyncTestCase):
    def setUp(self):
        super().setUp()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = Store(Path(directory.name) / 'resumeiq.db')
        self.enterContext(patch.object(api, 'store', self.store))
        for target in (api.validated_resumes, api.upload_versions, api.evaluation_histories, api.resume_versions,
                       api.last_activity, recruiter.workspaces):
            self.enterContext(patch.dict(target, {}, clear=True))

        async def inline(function, *args, **kwargs):
            return function(*args, **kwargs)
        self.enterContext(patch.object(api, 'run_in_threadpool', inline))

    async def test_analysis_survives_a_restart_and_deletion_removes_it(self):
        user = 'one@example.invalid'
        uploaded = await api.upload_sample(user)
        await api.analyze_resume(samples.SAMPLE_JOB_DESCRIPTION, uploaded['resume_id'], None, user, use_ai=False)
        api.validated_resumes['one@example.invalid']['improvement_pending'] = {'local'}
        api.store.save_user(user, api.snapshot(user))
        saved = json.dumps(self.store.load_all(3600)[user][0])
        self.assertNotIn('improvement_pending', saved)
        self.assertNotIn(samples.SAMPLE_RESUME[:40], saved)  # Extracted fields only, not the document text.

        for target in (api.validated_resumes, api.evaluation_histories, api.resume_versions, api.last_activity):
            target.clear()
        api.restore_persisted_data()
        self.assertEqual(api.validated_resumes[user]['resume_id'], uploaded['resume_id'])
        self.assertEqual(len(api.evaluation_histories[user]), 1)
        self.assertEqual(len(api.resume_versions[user]), 1)
        self.assertIn(user, api.last_activity)

        await api.delete_my_data(user)
        self.assertEqual(self.store.load_all(3600), {})

    async def test_recruiter_changes_are_persisted(self):
        router = recruiter.create_router(api.require_user, on_change=lambda user: self.store.save_user(user, api.snapshot(user)))
        create = next(r.endpoint for r in router.routes if r.path == '/api/workspaces' and 'POST' in r.methods)
        await create(recruiter.Job(title='Engineer', description='Python'), 'one@example.invalid')
        stored = self.store.load_all(3600)['one@example.invalid'][0]['workspaces']
        self.assertEqual([g['title'] for g in stored.values()], ['Engineer'])

    async def test_health_reports_storage_mode_only(self):
        self.assertEqual(await api.health(), {'status': 'ok', 'storage': 'sqlite'})
        summary = await api.get_my_data('one@example.invalid')
        self.assertEqual(summary['storage'], 'database')
