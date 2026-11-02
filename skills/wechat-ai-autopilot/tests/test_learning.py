"""Reading-record invariants; synthetic fixtures do not count as article study."""
import copy
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import learning as learn


class LearningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        self.run = self.workspace / 'study'
        learn.init_study(self.workspace, {'request': '学习两篇模拟文章用于记录验证', 'targets': [{'account': '模拟账号', 'count': 2}]}, self.run)

    def tearDown(self):
        self.temp.cleanup()

    def article(self, ident='A01'):
        body = self.run / f'{ident}.txt'
        body.write_text(f'这是{ident}的模拟完整正文，包含不同的案例条件与结果。结尾。', encoding='utf-8')
        return {'id': ident, 'account': '模拟账号', 'author': '测试作者', 'title': f'模拟文章{ident}',
                'read_url': f'https://example.com/{ident}', 'original_url': None,
                'published_at': None, 'date_kind': 'unknown', 'status': 'read_complete',
                'full_text_file': body.name, 'hash': hashlib.sha256(body.read_bytes()).hexdigest(),
                'completion_basis': '测试用短正文读至结尾；不是生产阅读记录',
                'notes': {key: '测试用具体观察字段' for key in learn.NOTE_FIELDS} | {'short_anchor': '包含不同的案例条件与结果'}}

    def test_download_or_lead_does_not_satisfy_reading_target(self):
        article = self.article()
        article['status'] = 'lead_only'
        report = learn.record_articles(self.run, [article])
        self.assertTrue(report['saved'])
        self.assertEqual(report['valid_read_complete'], 0)
        self.assertFalse(report['passed'])

    def test_resume_updates_same_id_without_counting_twice(self):
        first = self.article()
        learn.record_articles(self.run, first)
        self.assertEqual(learn.record_articles(self.run, first)['valid_read_complete'], 1)
        self.assertTrue(learn.record_articles(self.run, self.article('A02'))['passed'])

    def test_changed_body_invalidates_previous_read_record(self):
        learn.record_articles(self.run, [self.article(), self.article('A02')])
        (self.run / 'A01.txt').write_text('正文已改变，但仍包含不同的案例条件与结果。', encoding='utf-8')
        report = learn.audit(self.run)
        self.assertFalse(report['passed'])
        self.assertEqual(report['valid_read_complete'], 1)
        self.assertTrue(any('body hash changed or missing' in error.get('issues', []) for error in report['errors']))

    def test_reprint_with_new_title_cannot_count_same_body_twice(self):
        first = self.article()
        second = copy.deepcopy(first)
        second.update(id='A02', title='另一个转载标题', read_url='https://example.com/reprint')
        report = learn.record_articles(self.run, [first, second])
        self.assertFalse(report['saved'])
        self.assertTrue(any(any('duplicate body' in issue for issue in error.get('issues', [])) for error in report['errors']))

    def test_unsupported_lesson_evidence_is_rejected(self):
        learn.record_articles(self.run, [self.article(), self.article('A02')])
        learn.save(self.run / 'lessons.json', [{'id': 'L01', 'rule': '模拟可迁移规则', 'why': '模拟帮助理由',
                   'applicability': '测试场景', 'limits': '模拟范围', 'proposed_location': 'references/content-craft.md',
                   'evidence_ids': ['NOT_READ']}])
        report = learn.audit(self.run)
        self.assertTrue(report['reading_complete'])
        self.assertFalse(report['passed'])

    def test_wechat_tracking_variants_are_the_same_source(self):
        first = self.article()
        second = self.article('A02')
        first['original_url'] = 'https://mp.weixin.qq.com/s?__biz=public&mid=123&idx=1&sn=abc&scene=1#rd'
        second['original_url'] = 'https://mp.weixin.qq.com/s?sn=abc&idx=1&mid=123&__biz=public&scene=9'
        report = learn.record_articles(self.run, [first, second])
        self.assertFalse(report['saved'])
        self.assertTrue(any(any('duplicate article link' in issue for issue in error.get('issues', [])) for error in report['errors']))

    def test_missing_anchor_and_account_replacement_do_not_overwrite_valid_record(self):
        first = self.article()
        learn.record_articles(self.run, first)
        broken = copy.deepcopy(first)
        broken['notes']['short_anchor'] = '不存在的观察位置'
        self.assertFalse(learn.record_articles(self.run, broken)['saved'])
        changed = copy.deepcopy(first)
        changed['account'] = '另一个账号'
        with self.assertRaises(ValueError):
            learn.record_articles(self.run, changed)
        self.assertEqual(learn.audit(self.run)['valid_read_complete'], 1)


if __name__ == '__main__':
    unittest.main()
