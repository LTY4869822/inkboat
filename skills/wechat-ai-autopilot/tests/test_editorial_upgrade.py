"""Contract regression fixtures; these synthetic examples are not publishing/traffic tests."""
import io
import json
from pathlib import Path
import socket
import sys
import tempfile
import unittest
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import workflow as w
import research as r
from aihot_client import AIhotError


class Response:
    status = 200
    headers = {'ETag': 'fixture'}
    def __init__(self, value): self.raw = json.dumps(value).encode()
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, size): return self.raw[:size]


class UpgradeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.run = Path(self.temp.name)
    def tearDown(self): self.temp.cleanup()

    def fixture(self):
        w.save(self.run / 'brief.json', {'topic': '测试任务', 'length_preset': 'deep', 'editorial_policy': 'research-depth-v1'})
        body = '## 案例拆解\n\n测试案例把三份模拟输入合成一份对照表。\n\n## 同条件比较\n\n同一输入两种条件的结果不同，不能推广到所有任务。\n\n模拟输入仅适合验证流程，读者应先用自己的样本复核。'
        (self.run / 'body.md').write_text(body, encoding='utf-8')
        (self.run / 'reading.md').write_text('这是单元测试模拟的原始观察：测试案例把三份模拟输入合成一份对照表。', encoding='utf-8')
        w.save(self.run / 'sources.json', [{'id': 'S1', 'kind': 'primary', 'verified': True,
               'read_record': {'access': 'artifact', 'artifact_path': 'reading.md', 'artifact_sha256': w.file_hash(self.run / 'reading.md')}}])
        r.plan(self.run, platforms=['web', 'x'])
        plan = w.read(self.run / 'research-plan.json')
        w.save(self.run / 'research-log.json', {'queries': [
            {'id': q['id'], 'platform': q['platform'], 'status': 'read' if q['platform'] == 'web' else 'login_required',
             'method': 'host_search', 'observed_at': w.now(), 'observation': '单元测试模拟原始材料读取。' if q['platform'] == 'web' else '单元测试模拟的站内登录要求。',
             'source_ids': ['S1'] if q['platform'] == 'web' else []} for q in plan['queries']]})
        w.save(self.run / 'cases.json', [{'id': 'K1', 'origin': 'synthetic_demo', 'actor': '单元测试中的模拟作者',
            'task': '把三份模拟输入生成对照表', 'input': '单元测试生成的三份模拟输入', 'process': '按同一规则分类并输出对照结果',
            'outcome': '模拟输出包含三份输入的对照结果', 'limitations': '仅为单元测试夹具并非真实业务效果',
            'application': '验证案例来源字段与保存摘记对应', 'body_quote': '测试案例把三份模拟输入合成一份对照表。',
            'evidence': [{'source_id': 'S1', 'locator': '模拟观察段落', 'observation_quote': '测试案例把三份模拟输入合成一份对照表。'}]}])
        w.save(self.run / 'claims.json', [{'id': 'C1', 'body_quote': '同一输入两种条件的结果不同，不能推广到所有任务。'}])
        quote = '同一输入两种条件的结果不同，不能推广到所有任务。'
        candidates = [{'id': f'T{i}', 'title': f'测试工具的具体任务：三份输入怎样整理成对照结果，读者该检查哪些条件{i}',
                      'method': f'角度{i % 6}', 'reader': '需要核对任务产出的测试读者', 'hook': '模拟数据出现同条件比较的差异',
                      'promise': '帮助读者判断何时使用这套输入方法', 'opening_reason': '读者可以知道具体输出与适用限制', 'body_quote': quote,
                      'length_reason': '模拟标题为测试生成，长度可适当包含任务条件'} for i in range(12)]
        w.save(self.run / 'titles.json', {'body_sha256': w.file_hash(self.run / 'body.md'), 'selected': 'T0',
               'shortlist': ['T0', 'T1', 'T2'], 'candidates': candidates})
        w.save(self.run / 'depth-review.json', {'input_hashes': {name: w.file_hash(self.run / name) for name in r.FILES},
            'sections': [{'section': '案例拆解', 'question': '模拟案例具体得到什么可核验结果', 'reader_gain': '知道输入如何对应生成的对照表',
                          'kind': 'case', 'body_quote': '测试案例把三份模拟输入合成一份对照表。', 'supporting_ids': ['K1']},
                         {'section': '同条件比较', 'question': '模拟比较为什么不能扩大到所有任务', 'reader_gain': '知道对照样本和迁移限制的关系',
                          'kind': 'comparison', 'body_quote': quote, 'supporting_ids': ['C1']}],
            'checks': {key: {'status': 'pass', 'reason': '这是模拟夹具对照与适用范围的单元测试审阅记录', 'body_quote': quote}
                       for key in ('counterevidence', 'transferability', 'non_generic')}})

    def test_plan_does_not_claim_search_execution(self):
        result = r.plan(self.run, '测试任务', ['web', 'douyin'])
        self.assertTrue(all(q['status'] == 'planned' for q in result['queries']))
        self.assertFalse(r.check(self.run, 'research')['passed'])

    def test_evidence_backed_fixture_with_honest_login_gap_passes(self):
        self.fixture()
        report = r.check(self.run)
        self.assertTrue(report['passed'], report['errors'])
        self.assertTrue(any('login_required' in warn for warn in report['warnings']))

    def test_search_snippet_cannot_prove_case(self):
        self.fixture()
        sources = w.read(self.run / 'sources.json')
        sources[0].update(kind='lead', verified=False)
        w.save(self.run / 'sources.json', sources)
        self.assertTrue(any('cannot prove a case' in e for e in r.research_errors(self.run)[0]))

    def test_changed_reading_record_is_rejected(self):
        self.fixture()
        (self.run / 'reading.md').write_text('旧观察被改掉，仍保留测试案例把三份模拟输入合成一份对照表。', encoding='utf-8')
        self.assertTrue(any('record changed' in e for e in r.research_errors(self.run)[0]))

    def test_human_case_keeps_voices_without_fake_technical_input(self):
        self.fixture()
        case = w.read(self.run / 'cases.json')[0]
        for field in ('task', 'input', 'process'):
            case.pop(field)
        case.update(case_type='human_or_organization', goal='模拟角色希望保持创作兴趣',
                    context='模拟受访者受到时间与预算约束', choices='模拟案例选择人工审核并保留协作',
                    perspectives='模拟甲乙角色对目标的判断不同')
        w.save(self.run / 'cases.json', [case])
        self.assertEqual(r.research_errors(self.run)[0], [])
        case.pop('perspectives')
        w.save(self.run / 'cases.json', [case])
        self.assertTrue(any('perspectives missing' in error for error in r.research_errors(self.run)[0]))

    def test_human_case_still_rejects_summary_in_place_of_original_reading(self):
        self.fixture()
        case = w.read(self.run / 'cases.json')[0]
        case.update(case_type='human_or_organization', goal='模拟角色希望保持创作兴趣',
                    context='模拟受访者受到时间与预算约束', choices='模拟案例选择人工审核并保留协作',
                    perspectives='模拟甲乙角色对目标的判断不同')
        w.save(self.run / 'cases.json', [case])
        sources = w.read(self.run / 'sources.json')
        sources[0]['read_record']['access'] = 'search_snippet'
        w.save(self.run / 'sources.json', sources)
        self.assertTrue(any('cannot prove a case' in error for error in r.research_errors(self.run)[0]))

    def test_fake_own_experiment_is_rejected(self):
        self.fixture()
        cases = w.read(self.run / 'cases.json')
        cases[0]['origin'] = 'own_experiment'
        w.save(self.run / 'cases.json', cases)
        self.assertTrue(any('not actually recorded' in e for e in r.research_errors(self.run)[0]))

    def test_same_angle_titles_are_rejected(self):
        self.fixture()
        titles = w.read(self.run / 'titles.json')
        for item in titles['candidates']: item['method'] = '换词'
        w.save(self.run / 'titles.json', titles)
        self.assertTrue(any('different angles' in e for e in r.title_errors(self.run)[0]))

    def test_explicit_fixed_title_is_respected_but_still_needs_body_support(self):
        self.fixture()
        titles = w.read(self.run / 'titles.json')
        titles['candidates'] = titles['candidates'][:1]
        titles['shortlist'] = []
        titles['user_fixed'] = {'origin': 'user', 'instruction': '单元测试中的用户明确要求固定标题', 'title': titles['candidates'][0]['title']}
        w.save(self.run / 'titles.json', titles)
        self.assertEqual(r.title_errors(self.run)[0], [])
        titles['candidates'][0]['body_quote'] = '这个承诺未出现在当前正文。'
        w.save(self.run / 'titles.json', titles)
        self.assertTrue(r.title_errors(self.run)[0])

    def test_reading_record_changes_invalidate_workflow_fingerprint(self):
        self.fixture()
        before = w.fingerprint(self.run)['fingerprint']
        (self.run / 'reading.md').write_text('原始观察已变动。', encoding='utf-8')
        self.assertNotEqual(before, w.fingerprint(self.run)['fingerprint'])

    def test_stale_title_promise_and_false_first_person_are_rejected(self):
        self.fixture()
        titles = w.read(self.run / 'titles.json')
        titles['candidates'][0].update(title='我亲测这个新工具，三份输入整理成完整对照表，原来失败就卡在这里', body_quote='不存在的旧稿中的段落')
        w.save(self.run / 'titles.json', titles)
        errors = r.title_errors(self.run)[0]
        self.assertTrue(any('unsupported' in e for e in errors))
        self.assertTrue(any('first-person' in e for e in errors))

    def test_long_generic_advice_is_rejected(self):
        self.fixture()
        review = w.read(self.run / 'depth-review.json')
        for section in review['sections']: section['kind'] = 'synthesis'
        w.save(self.run / 'depth-review.json', review)
        self.assertTrue(any('length alone' in e for e in r.depth_errors(self.run)[0]))

    def test_evidence_in_another_section_cannot_prove_depth(self):
        self.fixture()
        review = w.read(self.run / 'depth-review.json')
        review['sections'][0]['supporting_ids'] = ['C1']
        w.save(self.run / 'depth-review.json', review)
        self.assertTrue(any('another section' in e for e in r.depth_errors(self.run)[0]))

    def test_evidence_changes_invalidate_depth_review_and_workflow_fingerprint(self):
        self.fixture()
        before = w.fingerprint(self.run)['fingerprint']
        w.save(self.run / 'research-log.json', {})
        self.assertNotEqual(before, w.fingerprint(self.run)['fingerprint'])
        self.assertTrue(any('stale' in e for e in r.depth_errors(self.run)[0]))

    def test_connection_refused_stops_once_without_trying_second_endpoint(self):
        w.save(self.run / 'brief.json', {'topic': 'AI'})
        calls = []
        def rejected(req, **kwargs):
            calls.append(req.full_url)
            raise urllib.error.URLError(ConnectionRefusedError(10061, 'fixture'))
        result = w.discover(self.run, opener=rejected)
        self.assertEqual(len(calls), 1)
        self.assertEqual(result['error_details'][0]['errno'], 10061)
        self.assertEqual(result['next'], 'check-host-approved-network')
        self.assertEqual(w.read(self.run / 'discovery.json')['responses'], [])

    def test_dns_failure_is_not_http_server_failure(self):
        def rejected(*args, **kwargs): raise urllib.error.URLError(socket.gaierror(11001, 'fixture'))
        report = w.diagnose_aihot(self.run, opener=rejected)
        self.assertEqual(report['error']['code'], 'transport_dns_failure')
        self.assertIsNone(report['error']['http_status'])

    def test_timeout_has_bounded_retries(self):
        calls, delays = [], []
        def timeout(*args, **kwargs):
            calls.append(1)
            raise TimeoutError()
        with self.assertRaises(AIhotError) as caught:
            w.fetch('https://aihot.virxact.com/api/v1/hot-topics', self.run, opener=timeout, sleeper=delays.append)
        self.assertEqual(len(calls), 3)
        self.assertEqual(delays, [1, 2])
        self.assertEqual(caught.exception.detail['code'], 'transport_timeout')

    def test_rate_limit_retains_problem_details_without_long_sleep(self):
        url = 'https://aihot.virxact.com/api/v1/hot-topics'
        def limited(*args, **kwargs):
            raise urllib.error.HTTPError(url, 429, '', {'Retry-After': '90'}, io.BytesIO(b'{"requestId":"fixture-id","help":"contact support"}'))
        delays = []
        with self.assertRaises(AIhotError) as caught: w.fetch(url, self.run, opener=limited, sleeper=delays.append)
        self.assertEqual(delays, [])
        self.assertEqual(caught.exception.detail['requestId'], 'fixture-id')
        self.assertEqual(caught.exception.detail['retry_after_seconds'], 90)

    def test_566_stops_after_one_retry(self):
        calls = []
        def rejected(req, **kwargs):
            calls.append(1)
            raise urllib.error.HTTPError(req.full_url, 566, '', {}, io.BytesIO(b'{}'))
        with self.assertRaises(AIhotError): w.fetch('https://aihot.virxact.com/api/v1/hot-topics', self.run, opener=rejected, sleeper=lambda _: None)
        self.assertEqual(len(calls), 2)

    def test_invalid_success_payload_not_cached_as_hot_topics(self):
        with self.assertRaises(ValueError):
            w.fetch('https://aihot.virxact.com/api/v1/hot-topics', self.run, opener=lambda *a, **k: Response({'error': 'fixture'}))
        self.assertEqual(list(self.run.glob('*.json')), [])

    def test_cache_filesystem_error_does_not_repeat_network_request(self):
        cache = self.run / 'not-a-directory'
        cache.write_text('fixture', encoding='utf-8')
        calls = []
        def request(*args, **kwargs):
            calls.append(1)
            return Response({'items': []})
        with self.assertRaises(AIhotError) as caught:
            w.fetch('https://aihot.virxact.com/api/v1/hot-topics', cache, opener=request, sleeper=lambda _: None)
        self.assertEqual(len(calls), 1)
        self.assertEqual(caught.exception.detail['code'], 'local_filesystem_error')


if __name__ == '__main__': unittest.main()
