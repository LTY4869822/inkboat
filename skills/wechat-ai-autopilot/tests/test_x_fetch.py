import copy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import x_fetch as x


class XMaterialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.payload = json.loads((x.VENDOR / 'tests/fixtures/fxtwitter_tweet.json').read_text(encoding='utf-8'))

    def tearDown(self):
        self.temp.cleanup()

    def fetch(self, payload=None, **kwargs):
        with patch.object(x.http, 'get_json', return_value=payload or self.payload):
            return x.collect(['https://x.com/alice/status/1234567890'], self.root / 'run', self.root / 'cache', **kwargs)

    def test_url_auth_and_spoofed_domains_rejected(self):
        for url in ['https://x.com.evil.example/alice/status/123', 'https://secret@x.com/alice/status/123', 'file:///x.com/alice/status/123']:
            with self.assertRaises(ValueError):x.tweet_url(url)
        self.assertEqual(x.tweet_url('https://twitter.com/alice/status/123/photo/2?tracking=abc')[0], 'https://x.com/alice/status/123')

    def test_original_material_and_candidates_keep_distinct_verification(self):
        result = self.fetch()
        record = result['records'][0]
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(record['published_at'], '2026-07-04T12:00:00+00:00')
        original = self.root / 'run' / record['raw_path']
        self.assertEqual(json.loads(original.read_text(encoding='utf-8')), self.payload)
        self.assertEqual(x.sha(original), record['raw_sha256'])
        reading = self.root / 'run' / record['read_record']['artifact_path']
        self.assertIn(self.payload['tweet']['text'], reading.read_text(encoding='utf-8'))
        candidates = json.loads((self.root / 'run/readings/x/source-candidates.json').read_text(encoding='utf-8'))
        self.assertFalse(candidates[0]['verified'])
        screenshots = json.loads((self.root / 'run/readings/x/screenshot-candidates.json').read_text(encoding='utf-8'))
        self.assertEqual(screenshots[0]['capture_state'], 'not_captured')

    def test_missing_metrics_remain_unknown(self):
        payload = copy.deepcopy(self.payload)
        payload['tweet'].pop('views', None)
        self.assertIsNone(self.fetch(payload)['records'][0]['metrics']['views'])

    def test_dedup_by_id_does_not_repeat_calls(self):
        with patch.object(x.http, 'get_json', return_value=self.payload) as request:
            result = x.collect(['https://x.com/alice/status/123', 'https://twitter.com/alice/status/123/photo/1'], self.root)
        self.assertEqual(len(result['records']), 1)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(request.call_args.kwargs['retries'], 0)

    def test_cache_reuse_keeps_original_observation_date(self):
        first = self.fetch()['records'][0]
        with patch.object(x.http, 'get_json', side_effect=AssertionError('Network should not run')):
            second = x.collect(['https://x.com/alice/status/1234567890'], self.root / 'run', self.root / 'cache')['records'][0]
        self.assertTrue(second['cache_hit'])
        self.assertEqual(second['fetched_at'], first['fetched_at'])
        self.assertIsNotNone(second['reused_at'])
        self.assertEqual(second['raw_sha256'], first['raw_sha256'])

    def test_stale_cache_and_failed_refresh_are_not_success(self):
        self.fetch()
        cache = self.root / 'cache/1234567890.json'
        data = json.loads(cache.read_text(encoding='utf-8'))
        data['fetched_at'] = (datetime.now(timezone.utc)-timedelta(hours=2)).isoformat()
        x.save(cache, data)
        with patch.object(x.http, 'get_json', side_effect=x.UpstreamDown('unreachable')):
            result = x.collect(['https://x.com/alice/status/1234567890'], self.root / 'run', self.root / 'cache')
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['records'][0]['error_code'], 'upstream_down')

    def test_wrong_tweet_and_blank_text_are_not_cached(self):
        for raw in [dict(self.payload['tweet'], id='999'), dict(self.payload['tweet'], text='', article=None)]:
            payload = dict(self.payload, tweet=raw)
            result = self.fetch(payload)
            self.assertEqual(result['status'], 'failed')
            self.assertFalse((self.root / 'cache/1234567890.json').exists())

    def test_partial_article_is_explicit(self):
        payload = copy.deepcopy(self.payload)
        payload['tweet']['article'] = {'title': 'Some title', 'preview_text': 'Only the preview'}
        record = self.fetch(payload)['records'][0]
        self.assertTrue(record['article_partial'])
        self.assertEqual(record['read_record']['access'], 'author_caption')

    def test_article_fixture_is_saved_as_returned_not_synthesized(self):
        payload = json.loads((x.VENDOR / 'tests/fixtures/fxtwitter_article.json').read_text(encoding='utf-8'))
        record = self.fetch(payload)['records'][0]
        self.assertFalse(record['article_partial'])
        self.assertTrue(record['tweet']['article']['full_text'])

    def test_rate_limit_is_one_attempt(self):
        with patch.object(x.http, 'get_json', return_value={'code': 429}) as request:
            result = x.collect(['https://x.com/alice/status/123'], self.root)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(result['records'][0]['error_code'], 'rate_limited')

    def test_nitter_missing_config_never_launches_child(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(x.subprocess, 'run') as child:
            result = x.nitter_query('search', self.root, query='AI', workspace=self.root)
        self.assertEqual(result['status'], 'unconfigured')
        child.assert_not_called()

    def test_nitter_timeout_is_reported(self):
        with patch.object(x.subprocess, 'run', side_effect=subprocess.TimeoutExpired('fetch', 25)) as child:
            result = x.nitter_query('search', self.root, query='AI', nitter='https://nitter.example')
        self.assertEqual(result['error_code'], 'timeout')
        self.assertEqual(child.call_args.kwargs['timeout'], 25)

    def test_timeline_uses_query_without_per_tweet_view_requests(self):
        response = subprocess.CompletedProcess([], 0, '{"tweets": [{"text": "A real returned lead"}], "count": 1}', '')
        with patch.object(x.subprocess, 'run', return_value=response) as child:
            result = x.nitter_query('timeline', self.root, user='alice', nitter='https://nitter.example')
        flags = child.call_args.args[0]
        self.assertIn('--search', flags)
        self.assertIn('from:alice', flags)
        self.assertNotIn('--user', flags)
        self.assertEqual(result['status'], 'leads')

    def test_credentials_are_not_accepted_as_nitter_configuration(self):
        with self.assertRaises(ValueError):x.nitter_config('https://user:secret@nitter.example')

    def test_doctor_does_not_probe_connectivity(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(x.http, 'get_json', side_effect=AssertionError('no probe')):
            result = x.doctor(self.root)
        self.assertEqual(result['single_tweet'], 'available_not_probed')


if __name__ == '__main__':unittest.main()
