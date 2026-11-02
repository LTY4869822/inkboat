import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import nitter_setup as n
import x_fetch as x


class NitterConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.html = (x.VENDOR / 'tests/fixtures/nitter_timeline.html').read_text(encoding='utf-8')

    def tearDown(self):
        self.temp.cleanup()

    def test_real_fixture_has_readable_ids_text_and_links(self):
        result = n.inspect_html(self.html)
        self.assertEqual(result['status'], 'passed')
        self.assertGreater(result['count'], 0)
        self.assertTrue(all('/status/' in url for url in result['sample_urls']))

    def test_http_200_challenge_and_homepage_are_not_success(self):
        self.assertEqual(n.inspect_html('<script id="anubis_challenge">{}</script>')['error_code'], 'browser_challenge')
        self.assertEqual(n.inspect_html('<h1>Welcome to Nitter</h1>')['error_code'], 'no_readable_tweets')

    def test_configuration_requires_both_real_search_and_timeline(self):
        with patch.object(x.http, 'get_text', return_value=self.html) as request:
            result = n.configure(self.root, 'https://nitter.example')
        self.assertEqual(result['status'], 'configured')
        self.assertEqual(request.call_count, 2)
        self.assertTrue(all(call.kwargs['retries'] == 0 and call.kwargs['timeout'] == 8 for call in request.call_args_list))
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(x.nitter_config(workspace=self.root), ['https://nitter.example'])
            doctor = x.doctor(self.root)
        self.assertEqual(doctor['last_local_validation']['search'], 'passed')
        self.assertEqual(doctor['last_local_validation']['replies'], 'not_tested')

    def test_failed_probe_preserves_existing_working_configuration(self):
        target = self.root / '.wechat-tools/x-nitter.json'
        x.save(target, {'schema': 1, 'instances': ['https://previous.example']})
        original = target.read_bytes()
        with patch.object(x.http, 'get_text', return_value='<h1>No items found</h1>'):
            result = n.configure(self.root, 'https://unusable.example')
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(target.read_bytes(), original)

    def test_only_fully_usable_endpoint_is_enabled(self):
        def response(url, **kwargs):
            return self.html if 'good.example' in url else '<script id="anubis_challenge">{}</script>'
        with patch.object(x.http, 'get_text', side_effect=response):
            result = n.configure(self.root, 'https://bad.example,https://good.example')
        self.assertEqual(result['instances_enabled'], ['https://good.example'])

    def test_explicit_then_env_then_workspace_precedence(self):
        x.save(self.root / '.wechat-tools/x-nitter.json', {'schema': 1, 'instances': ['https://local.example']})
        with patch.dict(os.environ, {'XTF_NITTER': 'https://env.example'}, clear=True):
            self.assertEqual(x.nitter_config('https://explicit.example', self.root), ['https://explicit.example'])
            self.assertEqual(x.nitter_config(workspace=self.root), ['https://env.example'])

    def test_invalid_local_config_fails_without_echoing_secrets(self):
        path = self.root / '.wechat-tools/x-nitter.json'
        path.parent.mkdir()
        path.write_text('{SECRET-TEXT', encoding='utf-8')
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError) as error:x.nitter_config(workspace=self.root)
        self.assertNotIn('SECRET-TEXT', str(error.exception))

    def test_zero_results_are_not_reported_as_successful_coverage(self):
        process = subprocess.CompletedProcess([], 0, '{"tweets":[], "count":0}', '')
        with patch.object(x.subprocess, 'run', return_value=process):
            result = x.nitter_query('search', self.root, query='AI', nitter='https://nitter.example')
        self.assertEqual(result['status'], 'empty_unverified')
        self.assertIn('challenge', result['next'])


if __name__ == '__main__':
    unittest.main()
