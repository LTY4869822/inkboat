import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import workflow as w
import onboard
import operations
import reader_value
import screenshot_plan
import release_check


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / '新用户 空白工作目录'
        self.root.mkdir()

    def test_new_user_without_accounts_can_continue_research(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(w, 'skill_paths', return_value={}):
            result = onboard.doctor(self.root, {'observed_at': '2026-10-06', 'tools': ['web__run']}, probe=False)
        self.assertEqual(result['status'], 'research_only')
        self.assertFalse(result['network_attempted'])
        self.assertFalse(result['checks']['wechat']['api_credentials_present'])
        self.assertFalse(result['checks']['x']['nitter_configured'])
        self.assertNotIn('research', sum([x['blocks'] for x in result['next_actions']], []))

    def test_builtin_image_presence_is_not_generation_success(self):
        result = onboard.doctor(self.root, {'observed_at': 'now', 'tools': ['image_gen__imagegen']}, probe=False)
        self.assertEqual(result['checks']['image_generation'], 'declared_available_not_called')
        self.assertNotIn('image_choice', [x['id'] for x in result['next_actions']])

    def test_personal_preferences_survive_setup_and_apply_to_new_run(self):
        w.save(self.root / '.wechat-ai/profile.json', {'font': 'kai', 'author': '作者', 'length_preset': 'deep'})
        onboard.setup(self.root, output_mode='local')
        created = w.init(self.root, 'practical', '案例')
        brief = w.read(Path(created['run']) / 'brief.json')
        self.assertEqual(brief['font'], 'kai')
        self.assertEqual(brief['min_chars'], 5000)
        self.assertEqual(brief['profile']['author'], '作者')
        self.assertEqual(brief['reader_value_policy'], 'reader-value-v1')
        self.assertEqual(brief['profile']['output_mode'], 'local')

    def test_configuration_does_not_grant_upload_and_optout_needs_answer(self):
        with self.assertRaises(ValueError):
            onboard.setup(self.root, image_choice='declined')
        result = onboard.setup(self.root, image_choice='declined', decision='本次及后续不配置')
        self.assertFalse(result['grants_upload_authorization'])
        self.assertFalse(result['credentials_saved'])

    def test_invalid_runtime_cannot_modify_profile(self):
        with self.assertRaises(ValueError):
            onboard.setup(self.root, output_mode='local', runtime={'secret': 'private'})
        self.assertFalse((self.root / '.wechat-ai/profile.json').exists())

    def test_two_capture_failures_stop_and_success_reuses(self):
        self.assertEqual(operations.retry(self.root, 'post-01', 'failed')['next'], 'targeted_repair')
        second = operations.retry(self.root, 'post-01', 'failed')
        self.assertEqual(second['next'], 'fallback_or_report_missing')
        self.assertEqual(operations.retry(self.root, 'post-01', 'failed')['attempts'], 2)
        self.assertEqual(operations.retry(self.root, 'post-02', 'success')['next'], 'reuse')
        self.assertEqual(operations.retry(self.root, 'post-02', 'failed')['attempts'], 1)
        self.assertEqual(operations.retry(self.root, 'post-03', 'login_required')['next'], 'fallback_or_report_missing')

    def test_timer_failure_is_preserved_and_cannot_finish_twice(self):
        token = operations.start(self.root, 'screenshots')
        start = w.read(self.root / 'timings.json')['events'][0]['started_epoch']
        operations.stop(self.root, token, status='failed', clock=start + 5)
        self.assertEqual(operations.summary(self.root)['stage_seconds']['screenshots'], 5)
        with self.assertRaises(ValueError):
            operations.stop(self.root, token)
        with self.assertRaises(ValueError):
            operations.retry(self.root, 'https://x.com/?token=private', 'failed')

    def test_reader_value_review_is_bound_to_passages_and_changes(self):
        body = '打开入口后填写邮箱地址。完成邮件确认后看到个人主页。遇到验证错误先检查邮箱拼写。'
        (self.root / 'body.md').write_text(body, encoding='utf8')
        review = reader_value.template(self.root, 'tutorial')
        self.assertTrue(reader_value.errors(self.root))
        review.update(reader='第一次注册的普通人', reader_outcome='读者能够从入口完成邮箱确认并判断注册是否成功')
        for item in review['checks'].values():
            item.update(status='pass', body_quote=body, reason='示例包含入口、输入、确认结果和错误恢复，实际核对相应段落')
        w.save(self.root / 'reader-value.json', review)
        self.assertEqual(reader_value.errors(self.root), [])
        (self.root / 'body.md').write_text(body + '更新了说明。', encoding='utf8')
        self.assertIn('Reader-value review missing or stale against current body', reader_value.errors(self.root))

    def test_agent_review_is_not_reader_testing(self):
        (self.root / 'body.md').write_text('这是待核验的具体内容段落。', encoding='utf8')
        review = reader_value.template(self.root, 'analysis')
        review['reader_tested'] = True
        w.save(self.root / 'reader-value.json', review)
        self.assertIn('Do not claim reader testing without actual reader feedback', reader_value.errors(self.root))

    def test_scene_selection_overrides_one_screen_preference_for_full_posts(self):
        self.assertEqual(screenshot_plan.choose('x-post', 'screen-frame', True)['extent'], 'complete-post')
        self.assertEqual(screenshot_plan.choose('tutorial')['extent'], 'screen-with-operation-frame')
        self.assertEqual(screenshot_plan.choose('chart')['extent'], 'complete-chart-with-conditions')

    def test_post_capture_rejects_english_and_incomplete_context(self):
        (self.root / 'original.jpg').write_bytes(b'original fixture pixels')
        record = {'id': 'post-1', 'kind': 'x-post', 'status': 'captured', 'original_file': 'original.jpg',
                  'original_sha256': w.file_hash(self.root / 'original.jpg'), 'chinese_required': True,
                  'translation': 'english', 'visible': {'author': True, 'all_body': True}}
        result = screenshot_plan.check(self.root, [record])
        self.assertFalse(result['passed'])
        self.assertEqual(len(result['errors']), 2)

    def test_whole_chinese_post_and_stitch_fragments_are_hash_checked(self):
        (self.root / 'original.jpg').write_bytes(b'original fixture pixels')
        record = {'id': 'post-1', 'kind': 'x-post', 'status': 'captured', 'original_file': 'original.jpg',
                  'original_sha256': w.file_hash(self.root / 'original.jpg'), 'chinese_required': True,
                  'translation': 'platform-native', 'visible': {k: True for k in ('author', 'all_body', 'media', 'absolute_date', 'metrics')}}
        self.assertTrue(screenshot_plan.check(self.root, [record])['passed'])
        record.update(capture_method='scroll-stitch', assembly_file='assembly.json')
        w.save(self.root / 'assembly.json', {'seams_reviewed': True, 'media_kept_in_single_fragment': True,
               'fragments': [{'path': 'missing-1.jpg'}, {'path': 'missing-2.jpg'}]})
        self.assertFalse(screenshot_plan.check(self.root, [record])['passed'])

    def test_missing_image_report_must_be_specific(self):
        result = screenshot_plan.check(self.root, [{'id': 'step-4', 'status': 'manual_needed'}])
        self.assertIn('precise handoff', result['errors'][0])

    def test_distribution_rejects_private_state_and_external_symlinks(self):
        (self.root / 'SKILL.md').write_text('local')
        self.assertEqual(len(release_check.files(self.root)), 1)
        target = self.root / '.wechat-ai'
        target.mkdir()
        (target / 'account.json').write_text('{"account":"fixture"}')
        with self.assertRaises(ValueError):
            release_check.files(self.root)

    def test_distribution_rejects_unknown_top_level_files(self):
        (self.root / 'personal-notes.md').write_text('private notes')
        with self.assertRaises(ValueError):
            release_check.files(self.root)


if __name__ == '__main__':
    unittest.main()
