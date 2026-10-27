"""Offline, synthetic recruiter ownership, limits, races and policy regressions."""
import asyncio
import builtins
import copy
import importlib
import json
from io import BytesIO, StringIO
from pathlib import Path
from unittest.mock import patch
from docx import Document
from fastapi import HTTPException, UploadFile
from pydantic import ValidationError
import recruiter as r
from evaluator.analyzer import analyze_resume_for_job
from network_guard import OfflineAsyncTestCase
from test_baseline import candidate


def document(name='Synthetic Candidate'):
    doc = Document()
    for line in [name, 'person@example.invalid', 'Skills', 'Python, SQL', 'Experience',
                 'Developer | Fictional Ltd.', '2020-2023', 'Built Python services.', 'Education', 'BSc, Example University']:
        doc.add_paragraph(line)
    buf = BytesIO(); doc.save(buf)
    return buf.getvalue()


def upload(data=None, name='resume.docx', size=True):
    data = document() if data is None else data
    return UploadFile(file=BytesIO(data), filename=name, size=len(data) if size else None)


class RecruiterTests(OfflineAsyncTestCase):
    def setUp(self):
        super().setUp()
        self.enterContext(patch.dict(r.workspaces, {}, clear=True))
        self.enterContext(patch.object(r, 'active_users', set()))
        async def user(): return 'one@example.invalid'
        self.routes = {route.name: route.endpoint for route in r.create_router(user).routes}
        self.user = 'one@example.invalid'

    async def call(self, name, **kwargs):
        return await self.routes[name](user=kwargs.pop('user', self.user), **kwargs)

    async def group(self, **kwargs):
        return await self.call('create_group', body=r.Job(title='Developer', description='Required skills: Python, Docker'), **kwargs)

    async def add(self, group=None, data=None):
        group = group or await self.group()
        batch = await self.call('upload_batch', group_id=group['id'], files=[upload(data)])
        return group, batch['outcomes'][0]['candidate_id']

    async def analyze(self, group, cid, **kwargs):
        return await self.call('analyze_candidate', group_id=group['id'], candidate_id=cid,
                               body=r.AnalysisRequest(version=group['version'], **kwargs))

    async def test_create_list_ownership_and_unpredictable_ids(self):
        group = await self.group()
        self.assertGreaterEqual(len(group['id']), 20)
        self.assertEqual(len((await self.call('list_groups'))['workspaces']), 1)
        self.assertEqual((await self.call('list_groups', user='two'))['workspaces'], [])
        with self.assertRaises(HTTPException) as exc:
            await self.call('get_group', group_id=group['id'], user='two')
        self.assertEqual(exc.exception.status_code, 404)

    async def test_empty_fields_and_schema_bounds(self):
        with self.assertRaises(HTTPException):
            await self.call('create_group', body=r.Job(title=' ', description=' '))
        for fields in ({'title':'', 'description':'x'}, {'title':'x'*121,'description':'x'}, {'title':'x','description':'x','extra':True}):
            with self.subTest(fields=fields), self.assertRaises(ValidationError): r.Job(**fields)

    async def test_workspace_and_global_owner_caps(self):
        with patch.object(r, 'MAX_GROUPS', 1), patch.object(r, 'MAX_OWNERS', 1):
            await self.group()
            for user in (self.user, 'two'):
                with self.assertRaises(HTTPException): await self.group(user=user)

    async def test_single_real_docx_extracts_without_provider(self):
        with patch('ai.matcher.get_client', side_effect=AssertionError('No AI')) as provider:
            group, cid = await self.add()
        provider.assert_not_called()
        detail = await self.call('get_candidate', group_id=group['id'], candidate_id=cid)
        self.assertEqual(detail['candidate']['name'], 'Synthetic Candidate')
        self.assertEqual(detail['status'], 'Not Reviewed')
        self.assertNotIn('digest', detail)
        self.assertNotIn('content', r.group_for(self.user, group['id'])['candidates'][cid])

    async def test_partial_failure_and_retry_preserve_success(self):
        group = await self.group()
        batch = await self.call('upload_batch', group_id=group['id'], files=[upload(), upload(b'bad', 'bad.pdf'), upload(b'text', 'bad.txt')])
        self.assertEqual((batch['completed'], batch['failed']), (1, 2))
        retry = await self.call('upload_batch', group_id=group['id'], files=[upload(document('Second Candidate'))])
        self.assertEqual(retry['failed'], 0)
        self.assertEqual(len(r.group_for(self.user, group['id'])['candidates']), 2)

    async def test_empty_corrupt_and_unsupported_files(self):
        group = await self.group()
        files = [upload(b'', 'empty.pdf'), upload(b'bad', 'corrupt.docx'), upload(b'notpdf', 'fake.pdf'), upload(b'text', 'file.txt')]
        result = await self.call('upload_batch', group_id=group['id'], files=files)
        self.assertEqual(result['failed'], 4)
        self.assertEqual(result['completed'], 0)
        self.assertNotIn('Traceback', json.dumps(result))

    async def test_duplicate_hash_different_names_and_repeat(self):
        group = await self.group(); data = document()
        result = await self.call('upload_batch', group_id=group['id'], files=[upload(data,'a.docx'),upload(data,'b.docx')])
        self.assertEqual([o['kind'] for o in result['outcomes']], ['success','duplicate'])
        repeat = await self.call('upload_batch', group_id=group['id'], files=[upload(data)])
        self.assertEqual(repeat['outcomes'][0]['candidate_id'], result['outcomes'][0]['candidate_id'])

    async def test_same_name_different_content_not_merged(self):
        group = await self.group()
        result = await self.call('upload_batch', group_id=group['id'], files=[upload(document()), upload(document()+b'\n')])
        self.assertEqual([o['kind'] for o in result['outcomes']], ['success','success'])

    async def test_duplicates_scoped_to_workspace_and_user(self):
        data = document()
        for user in (self.user, 'two'):
            for _ in range(2):
                group = await self.group(user=user)
                result = await self.call('upload_batch', group_id=group['id'], files=[upload(data)], user=user)
                self.assertEqual(result['outcomes'][0]['kind'], 'success')

    async def test_batch_count_and_aggregate_limits(self):
        group = await self.group()
        for files in ([], [upload(b'x') for _ in range(6)]):
            with self.assertRaises(HTTPException): await self.call('upload_batch', group_id=group['id'], files=files)
        with patch.object(r, 'BATCH_BYTES', 5):
            for sized in (True, False):
                with self.assertRaises(HTTPException) as exc:
                    await self.call('upload_batch', group_id=group['id'], files=[upload(b'1234',size=sized),upload(b'5678',size=sized)])
                self.assertEqual(exc.exception.status_code, 413)
        self.assertFalse(r.group_for(self.user, group['id'])['candidates'])

    async def test_individual_size_limit(self):
        group = await self.group()
        with patch('utils.limits.RESUME_BYTES', 3):
            result = await self.call('upload_batch', group_id=group['id'], files=[upload(b'1234')])
        self.assertEqual(result['failed'], 1)

    async def test_safe_unicode_filename_no_path_retained(self):
        group = await self.group()
        result = await self.call('upload_batch', group_id=group['id'], files=[upload(name='../../private/候補者.docx')])
        self.assertEqual(result['outcomes'][0]['filename'], '候補者.docx')

    async def test_candidate_cap_across_workspaces(self):
        with patch.object(r, 'MAX_CANDIDATES', 1):
            await self.add()
            group = await self.group()
            result = await self.call('upload_batch', group_id=group['id'], files=[upload()])
            self.assertEqual(result['outcomes'][0]['kind'], 'capacity')

    async def test_batch_metadata_is_bounded(self):
        group = await self.group(); data = document()
        for _ in range(7): await self.call('upload_batch', group_id=group['id'], files=[upload(data)])
        self.assertEqual(len(r.group_for(self.user, group['id'])['batches']), 5)

    async def test_global_and_user_concurrency_admission(self):
        with r.processing(self.user):
            with self.assertRaises(HTTPException):
                with r.processing(self.user): pass
            with r.processing('two'):
                with self.assertRaises(HTTPException):
                    with r.processing('three'): pass
        self.assertEqual(r.active_users, set())

    async def test_local_analysis_reuses_existing_scores_without_ai(self):
        group, cid = await self.add()
        record = r.group_for(self.user, group['id'])['candidates'][cid]
        with patch('evaluator.analyzer.match_resume_to_job_ai', side_effect=TimeoutError):
            expected = analyze_resume_for_job(record['candidate'], 'Required skills: Python, Docker')
        with patch('evaluator.analyzer.match_resume_to_job_ai', side_effect=AssertionError('Must not call')) as provider:
            actual = await self.analyze(group,cid)
        provider.assert_not_called()
        for key in ('overall_score','resume_quality_score','job_fit_score','matched_skills','missing_skills','total_experience_years'):
            self.assertEqual(actual['analysis'][key], expected[key])

    async def test_explicit_ai_and_fallback_cached(self):
        group,cid = await self.add()
        with patch('evaluator.analyzer.match_resume_to_job_ai', side_effect=TimeoutError) as provider:
            first = await self.analyze(group,cid,use_ai=True)
            second = await self.analyze(group,cid,use_ai=True)
        provider.assert_called_once(); self.assertEqual(first,second)
        self.assertEqual(first['analysis']['job_fit_method'],'rule-based')

    async def test_job_change_invalidates_scores_and_stale_write(self):
        group,cid = await self.add(); await self.analyze(group,cid)
        await self.call('update_group', group_id=group['id'], body=r.JobUpdate(title='New',description='SQL',version=1))
        detail = await self.call('get_candidate', group_id=group['id'], candidate_id=cid)
        self.assertEqual(detail['analysis_state'],'outdated'); self.assertIsNone(detail['analysis'])
        with self.assertRaises(HTTPException): await self.analyze(group,cid)
        with self.assertRaises(HTTPException): await self.call('update_group',group_id=group['id'],body=r.JobUpdate(title='Old',description='Old',version=1))

    async def test_title_change_does_not_invalidate_same_job(self):
        group,cid = await self.add(); await self.analyze(group,cid)
        result = await self.call('update_group',group_id=group['id'],body=r.JobUpdate(title='Renamed',description='Required skills: Python, Docker',version=1))
        self.assertEqual(result['version'],1)
        self.assertIsNotNone((await self.call('get_candidate',group_id=group['id'],candidate_id=cid))['analysis'])

    async def test_job_change_during_analysis_discards_result(self):
        group,cid = await self.add()
        async def changed(function,*args,**kwargs):
            result = function(*args,**kwargs)
            r.group_for(self.user,group['id'])['version'] += 1
            return result
        with patch('recruiter.run_in_threadpool',changed), self.assertRaises(HTTPException): await self.analyze(group,cid)
        self.assertIsNone(r.group_for(self.user,group['id'])['candidates'][cid]['analysis'])
        self.assertFalse(r.active_users)

    async def test_analysis_failure_retry_and_partial_results(self):
        group,first = await self.add(); _,second = await self.add(group,document('Other Person'))
        await self.analyze(group,first)
        with patch('recruiter.analyze_resume_for_job',side_effect=ValueError('secret failure')), self.assertRaises(HTTPException) as exc:
            await self.analyze(group,second)
        self.assertNotIn('secret',str(exc.exception.detail))
        self.assertIsNotNone(r.group_for(self.user,group['id'])['candidates'][first]['analysis'])
        await self.analyze(group,second)

    async def test_comparison_current_two_candidates_and_mixed_source_notice(self):
        group,first = await self.add(); _,second = await self.add(group,document('Other Person'))
        await self.analyze(group,first); await self.analyze(group,second)
        r.group_for(self.user,group['id'])['candidates'][second]['analysis']['job_fit_method'] = 'ai'
        result = await self.call('compare',group_id=group['id'],body=r.Comparison(candidate_ids=[first,second],version=1))
        self.assertEqual([row['id'] for row in result['candidates']],[first,second])
        self.assertIn('not equally calibrated',result['notice'])

    async def test_comparison_bounds_missing_and_no_analysis(self):
        group,cid = await self.add()
        for ids in ([], ['x']*5):
            with self.assertRaises(ValidationError): r.Comparison(candidate_ids=ids,version=1)
        for ids in ([cid],[cid,cid],['missing']):
            with self.assertRaises(HTTPException): await self.call('compare',group_id=group['id'],body=r.Comparison(candidate_ids=ids,version=1))

    async def test_manual_status_reversible_and_scores_immutable(self):
        group,cid = await self.add(); await self.analyze(group,cid)
        record = r.group_for(self.user,group['id'])['candidates'][cid]
        before = copy.deepcopy(record['analysis'])
        for index,status in enumerate(['Under Review','Shortlisted','Not Selected','Not Reviewed']):
            await self.call('review_candidate',group_id=group['id'],candidate_id=cid,body=r.Review(status=status,revision=index))
        self.assertEqual(record['analysis'],before); self.assertEqual(record['status'],'Not Reviewed')
        self.assertEqual(record['audit'][-1]['actor'],self.user)

    async def test_review_revision_conflict_and_bounded_audit(self):
        group,cid = await self.add()
        for revision in range(12):
            await self.call('review_candidate',group_id=group['id'],candidate_id=cid,body=r.Review(status='Shortlisted' if revision%2==0 else 'Under Review',revision=revision))
        self.assertEqual(len(r.group_for(self.user,group['id'])['candidates'][cid]['audit']),10)
        with self.assertRaises(HTTPException): await self.call('review_candidate',group_id=group['id'],candidate_id=cid,body=r.Review(status='Not Selected',revision=0))
        with self.assertRaises(ValidationError): r.Review(status='Automatic reject',revision=12)

    async def test_cross_user_candidate_review_and_comparison_denied(self):
        group,cid = await self.add()
        calls = [('get_candidate',{'candidate_id':cid}),('review_candidate',{'candidate_id':cid,'body':r.Review(status='Shortlisted',revision=0)}),('compare',{'body':r.Comparison(candidate_ids=[cid],version=1)})]
        for name,kwargs in calls:
            with self.subTest(name=name), self.assertRaises(HTTPException) as exc: await self.call(name,group_id=group['id'],user='other',**kwargs)
            self.assertEqual(exc.exception.status_code,404)

    async def test_removal_busy_and_freed_capacity(self):
        group,cid = await self.add()
        with r.processing(self.user), self.assertRaises(HTTPException): await self.call('delete_candidate',group_id=group['id'],candidate_id=cid)
        await self.call('delete_candidate',group_id=group['id'],candidate_id=cid)
        with self.assertRaises(HTTPException): await self.call('get_candidate',group_id=group['id'],candidate_id=cid)
        await self.call('delete_group',group_id=group['id']); self.assertNotIn(self.user,r.workspaces)

    async def test_missing_candidate_fields_safe_summary(self):
        group,cid = await self.add()
        record = r.group_for(self.user,group['id'])['candidates'][cid]; record['candidate'] = {}
        detail = await self.call('get_candidate',group_id=group['id'],candidate_id=cid)
        self.assertIsNone(detail['name']); self.assertEqual(detail['skills'],[])

    async def test_actual_twenty_candidate_limit(self):
        group = await self.group(); data = document()
        for batch in range(4):
            result = await self.call('upload_batch',group_id=group['id'],files=[upload(data+b' '*n) for n in range(batch*5,batch*5+5)])
            self.assertEqual(result['completed'],5)
        result = await self.call('upload_batch',group_id=group['id'],files=[upload(data+b' '*21)])
        self.assertEqual(result['outcomes'][0]['kind'],'capacity')
        self.assertEqual(len(r.group_for(self.user,group['id'])['candidates']),20)

    async def test_simultaneous_upload_duplicate_admission(self):
        group = await self.group(); started, release = asyncio.Event(), asyncio.Event()
        async def slow(function,*args,**kwargs):
            started.set(); await release.wait(); return function(*args,**kwargs)
        with patch('recruiter.run_in_threadpool',slow):
            task = asyncio.create_task(self.call('upload_batch',group_id=group['id'],files=[upload()]))
            await started.wait()
            try:
                with self.assertRaises(HTTPException) as exc: await self.call('upload_batch',group_id=group['id'],files=[upload()])
                self.assertEqual(exc.exception.status_code,409)
            finally:
                release.set(); await task
        self.assertEqual(len(r.group_for(self.user,group['id'])['candidates']),1)

    async def test_concurrent_review_has_one_winner(self):
        group,cid=await self.add()
        results=await asyncio.gather(*(self.call('review_candidate',group_id=group['id'],candidate_id=cid,body=r.Review(status=status,revision=0)) for status in ('Shortlisted','Not Selected')),return_exceptions=True)
        self.assertEqual(sum(isinstance(value,HTTPException) for value in results),1)
        self.assertEqual(r.group_for(self.user,group['id'])['candidates'][cid]['revision'],1)

    async def test_foreign_candidate_in_own_workspace_rejected(self):
        first,cid=await self.add(); second=await self.group()
        with self.assertRaises(HTTPException) as exc: await self.call('get_candidate',group_id=second['id'],candidate_id=cid)
        self.assertEqual(exc.exception.status_code,404)

    async def test_recruiter_ai_reuses_original_privacy_adapter(self):
        from test_baseline import completion_client
        group,cid=await self.add()
        record=r.group_for(self.user,group['id'])['candidates'][cid]
        record['candidate'].update(projects=[{'title':'Private project','details':['Secret project quote']}],skill_evidence={'python':[{'excerpt':'Secret evidence quote'}]})
        client=completion_client('{}')
        with patch('ai.matcher.get_client',return_value=client): await self.analyze(group,cid,use_ai=True)
        sent=client.chat.completions.create.call_args.kwargs['messages'][1]['content']
        for private in ('person@example.invalid','Synthetic Candidate','Fictional Ltd.','Private project','Secret project quote','Secret evidence quote'):
            self.assertNotIn(private,sent)

    async def test_individual_store_and_history_unchanged(self):
        original=builtins.open
        account_path=Path(__file__).resolve().parents[1]/'data'/'users.json'
        def isolated(file,mode='r',*args,**kwargs):
            if isinstance(file,(str,Path)) and Path(file).resolve()==account_path: return StringIO('{}')
            return original(file,mode,*args,**kwargs)
        with patch('builtins.open',side_effect=isolated): api=importlib.import_module('main')
        with patch.dict(api.validated_resumes,{self.user:{'resume_id':'individual','candidate':candidate()}},clear=True), patch.dict(api.evaluation_histories,{self.user:[{'score':42}]},clear=True):
            before=copy.deepcopy((api.validated_resumes,api.evaluation_histories))
            group,cid=await self.add();await self.analyze(group,cid)
            self.assertEqual((api.validated_resumes,api.evaluation_histories),before)

    async def test_real_asgi_requires_auth_and_validates_body(self):
        original = builtins.open
        account_path = Path(__file__).resolve().parents[1]/'data'/'users.json'
        def isolated(file,mode='r',*args,**kwargs):
            if isinstance(file,(str,Path)) and Path(file).resolve()==account_path:
                if mode!='r': raise AssertionError('Account writes forbidden')
                return StringIO('{}')
            return original(file,mode,*args,**kwargs)
        with patch('builtins.open',side_effect=isolated): api=importlib.import_module('main')
        async def request(method,path,body=b'{}'):
            sent=[]
            async def receive(): return {'type':'http.request','body':body,'more_body':False}
            async def send(message): sent.append(message)
            scope={'type':'http','asgi':{'version':'3.0'},'http_version':'1.1','method':method,'scheme':'http','path':path,'raw_path':path.encode(),'query_string':b'','root_path':'','server':('test',80),'client':('synthetic',1234),'headers':[(b'content-type',b'application/json')]}
            await api.app(scope,receive,send)
            return sent[0]['status']
        with patch('main.get_email_from_token',return_value=None):
            for method,path in [('GET','/api/workspaces'),('POST','/api/workspaces'),('POST','/api/workspaces/x/uploads'),('PATCH','/api/workspaces/x/candidates/y/review'),('POST','/api/workspaces/x/comparison')]:
                self.assertEqual(await request(method,path),401)
        with patch.dict(api.app.dependency_overrides,{api.require_user:lambda:self.user}):
            self.assertEqual(await request('POST','/api/workspaces'),422)
