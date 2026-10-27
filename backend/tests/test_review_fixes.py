"""Regression tests for the review fixes: account file durability, required-years
detection, preferred-skill weighting, local-only improvements and opt-in AI matching."""
import builtins
import importlib
import json
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from evaluator.analyzer import analyze_resume_for_job
from matcher.matcher import extract_required_years, match_resume_to_job, PREFERRED_SKILL_WEIGHT
from network_guard import OfflineAsyncTestCase, OfflineTestCase, network_guard


def setUpModule():
    global api, auth
    original = builtins.open
    account_path = Path(__file__).resolve().parents[1] / 'data' / 'users.json'
    def isolated(file, mode='r', *args, **kwargs):
        if isinstance(file, (str, Path)) and Path(file).resolve() == account_path:
            if mode != 'r':
                raise AssertionError('Account writes forbidden')
            return StringIO('{}')
        return original(file, mode, *args, **kwargs)
    with network_guard(), patch('builtins.open', side_effect=isolated):
        auth = importlib.import_module('auth.auth')
        api = importlib.import_module('main')


class AccountFileTests(OfflineTestCase):
    def setUp(self):
        super().setUp()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.path = self.directory / 'users.json'
        self.enterContext(patch.object(auth, 'DATA_FILE', self.path))
        self.enterContext(patch.dict(auth.users, {}, clear=True))

    def test_round_trip_leaves_no_temp_files(self):
        auth.create_user('one@example.invalid', 'synthetic-password')
        self.assertEqual(set(auth._load_users()), {'one@example.invalid'})
        self.assertEqual([p.name for p in self.directory.iterdir()], ['users.json'])

    def test_failed_write_keeps_previous_file(self):
        auth.create_user('one@example.invalid', 'synthetic-password')
        before = self.path.read_text(encoding='utf-8')
        with patch('auth.auth.json.dump', side_effect=OSError('disk full')), self.assertRaises(OSError):
            auth.create_user('two@example.invalid', 'synthetic-password')
        self.assertEqual(self.path.read_text(encoding='utf-8'), before)
        self.assertEqual([p.name for p in self.directory.iterdir()], ['users.json'])

    def test_corrupt_file_fails_loudly_instead_of_returning_empty(self):
        for content in ('{"one@example.invalid": {"salt"', '["not", "a", "dict"]'):
            with self.subTest(content=content):
                self.path.write_text(content, encoding='utf-8')
                with self.assertRaises(RuntimeError):
                    auth._load_users()

    def test_missing_file_is_empty(self):
        self.assertEqual(auth._load_users(), {})


class RequiredYearsTests(OfflineTestCase):
    def test_company_and_benefit_durations_are_ignored(self):
        for text, expected in [
            ('Founded 25 years ago. Requires 3+ years of Python.', 3),
            ('Over the past 20 years we have grown. 5+ years of experience required.', 5),
            ('We have served clients for over 30 years. Minimum 4 years experience.', 4),
            ('A 50 years old company with 10 years in business. 2 years of SQL.', 2),
            ('Sabbatical after 7 years of service. At least 6 years in data roles.', 6),
            ('Founded 12 years ago.', None),
        ]:
            with self.subTest(text=text):
                self.assertEqual(extract_required_years(text), expected)

    def test_explicit_requirement_beats_earlier_plain_mention(self):
        self.assertEqual(extract_required_years('Team of 2 years tenure on average. 6 years of experience needed.'), 6)

    def test_bare_requirements_still_supported(self):
        for text, expected in (('3+ years', 3), ('3-5 years', 3), ('1 year', 1), ('', None)):
            with self.subTest(text=text):
                self.assertEqual(extract_required_years(text), expected)


class SkillWeightingTests(OfflineTestCase):
    JD = 'Required Skills:\nPython, Kubernetes\nNice to have:\nExcel, Tableau'

    def test_preferred_only_skills_count_half(self):
        self.assertEqual(PREFERRED_SKILL_WEIGHT, 0.5)
        # Required: 2 x 1.0, preferred: 2 x 0.5 -> total weight 3.
        self.assertEqual(match_resume_to_job({'skills': ['Python']}, self.JD)['skills_score'], 33)
        self.assertEqual(match_resume_to_job({'skills': ['Excel']}, self.JD)['skills_score'], 17)
        self.assertEqual(match_resume_to_job({'skills': ['Excel', 'Tableau']}, self.JD)['skills_score'], 33)
        self.assertEqual(match_resume_to_job({'skills': ['Python', 'Kubernetes']}, self.JD)['skills_score'], 67)

    def test_skill_in_both_required_and_preferred_counts_in_full(self):
        jd = 'Requirements:\nPython\nPreferred Qualifications:\nPython, Docker'
        result = match_resume_to_job({'skills': ['Python']}, jd)
        self.assertEqual(result['match_inputs']['skill_weights'], {'python': 1.0, 'docker': 0.5})
        self.assertEqual(result['skills_score'], 67)

    def test_unlabelled_jd_keeps_equal_weights(self):
        self.assertEqual(match_resume_to_job({'skills': ['Python']}, 'Python and Java')['skills_score'], 50)

    def test_explanation_reports_weights_for_local_scoring(self):
        with patch('evaluator.analyzer.match_resume_to_job_ai', side_effect=AssertionError('No AI')):
            analysis = analyze_resume_for_job({'skills': ['Python']}, self.JD, use_ai=False)
        weights = {row['skill']: row['weight'] for row in analysis['explanation']['requirements']}
        self.assertEqual(weights, {'python': 1.0, 'kubernetes': 1.0, 'excel': 0.5, 'tableau': 0.5})


class OptInAITests(OfflineAsyncTestCase):
    def setUp(self):
        super().setUp()
        self.record = {'resume_id': 'resume-one', 'candidate': {'skills': ['Python'], 'experience': [], 'education': []}}
        self.enterContext(patch.dict(api.validated_resumes, {'one@example.invalid': self.record}, clear=True))
        self.enterContext(patch.dict(api.evaluation_histories, {}, clear=True))

        async def inline(function, *args, **kwargs):
            return function(*args, **kwargs)
        self.enterContext(patch.object(api, 'run_in_threadpool', inline))

    async def test_analyze_defaults_to_local_matching(self):
        with patch('evaluator.analyzer.match_resume_to_job_ai', side_effect=AssertionError('No AI')) as provider:
            result = await api.analyze_resume('Python', 'resume-one', None, 'one@example.invalid', use_ai=False)
        provider.assert_not_called()
        self.assertEqual(result['analysis']['job_fit_method'], 'rule-based')

    async def test_analyze_uses_ai_only_when_requested(self):
        with patch('evaluator.analyzer.match_resume_to_job_ai', side_effect=TimeoutError) as provider:
            result = await api.analyze_resume('Python', 'resume-one', None, 'one@example.invalid', use_ai=True)
        provider.assert_called_once()
        self.assertEqual(result['analysis']['job_fit_method'], 'rule-based')
        self.assertIn('AI unavailable', result['analysis']['processing_note'])

    async def test_http_default_is_local(self):
        sent = []
        async def receive():
            return {'type': 'http.request', 'body': b'resume_id=resume-one&job_description=Python', 'more_body': False}
        async def send(message):
            sent.append(message)
        scope = {'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1', 'method': 'POST', 'scheme': 'http',
                 'path': '/api/analyze', 'raw_path': b'/api/analyze', 'query_string': b'', 'root_path': '',
                 'server': ('test', 80), 'client': ('synthetic', 1234),
                 'headers': [(b'content-type', b'application/x-www-form-urlencoded'), (b'authorization', b'Bearer synthetic')]}
        with patch('main.get_email_from_token', return_value='one@example.invalid'), \
                patch('evaluator.analyzer.match_resume_to_job_ai', side_effect=AssertionError('No AI')) as provider:
            await api.app(scope, receive, send)
        provider.assert_not_called()
        self.assertEqual(sent[0]['status'], 200)
        body = json.loads(b''.join(m.get('body', b'') for m in sent if m['type'] == 'http.response.body'))
        self.assertEqual(body['analysis']['job_fit_method'], 'rule-based')

    async def test_improvements_endpoint_has_no_ai_mode(self):
        self.assertNotIn('use_ai', api.improve_resume.__code__.co_varnames)
