"""Synthetic fixtures test registration/use contracts, not real author learning."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import intake
import learning
import style_library as styles
import workflow as w


def make_study(workspace, count=20, policy='explicit_delegation', language='zh'):
    study = workspace / 'study'
    learning.init_study(workspace, {'request': '模拟自编语料验证系统，不是阅读真实博主文章',
        'mode': 'writing-style', 'targets': [{'account': '测试自编文章', 'count': count}],
        'approval_policy': policy}, study)
    styles.seed(study, 'fixture-voice', '测试用自编文风', language)
    records, metadata = [], []
    for number in range(count):
        ident = f'A{number:02d}'
        text = f'这篇自编测试文章讨论项目{number}，仅用来验证文件与记录。\n\n' + (
            f'项目{number}的输入条件、验证过程与失败边界均为模拟。先解释需求为何不清楚，再比较两个不同选择，'
            '最后指出哪些条件变化会让判断失效。这些文字不是实际平台案例，也不证明阅读或文风效果。\n\n')*3
        path = study / f'{ident}.md'; path.write_text(text, encoding='utf-8')
        record = {'id': ident, 'account': '测试自编文章', 'author': 'fixture-author', 'title': f'自编测试篇{number}',
            'source_kind': 'user-file', 'input_label': path.name, 'read_url': None, 'published_at': None,
            'date_kind': 'unknown', 'status': 'read_complete', 'full_text_file': path.name, 'hash': styles.sha(path),
            'completion_basis': '模拟阅读标记，仅测试记录契约',
            'notes': {key: '模拟具体记录，不代表真实编辑审阅' for key in learning.NOTE_FIELDS} | {'short_anchor': f'这篇自编测试文章讨论项目{number}'}}
        records.append(record)
        metadata.append({'id': ident, 'title': record['title'], 'author': record['author'], 'date': None,
            'date_kind': 'unknown', 'article_type': '评测' if number % 2 == 0 else '教程', 'column': '',
            'topic_tags': ['编程'] if number % 2 == 0 else ['文档'], 'hook_type': '场景式',
            'structure_pattern': '任务与对照', 'source_types': ['自编模拟材料'], 'word_count': len(text), 'notable': '测试'})
    assert learning.record_articles(study, records)['saved']
    styles.save(study / 'article-metadata.json', metadata)
    styles.language_stats(study)
    for name in styles.DOCS[language]:
        text = '# 自编测试规则\n\n' + ('先以具体场景讲清输入限制，比较实际选择，承认反例。将证据与推断分开，'
            '术语解释紧跟具体任务，结尾回到读者下一次决定。仅分析图片解释与证据作用，字体和排版不在学习范围。\n\n')*4
        (study / 'dna' / name).write_text(text, encoding='utf-8')
    (study / 'style-sample.md').write_text('自编的新选题样稿，仅验证接口，不表示实际文风审阅。\n\n' +
        ('这次讨论新项目的决策边界。读者先了解约束，再看不同选择如何改变结果，最后保留反例和下一步条件。\n\n')*10, encoding='utf-8')
    seal_review(study)
    return study


def seal_review(study):
    observations = [{'dimension': dim, 'rule': f'测试{dim}层的具体规则{n}', 'evidence_ids': ['A00', 'A01'],
        'applicability': '模拟测试语料', 'exceptions': '不泛化到真实作者'}
        for n, dim in enumerate(['language', 'structure', 'topics', 'sources', 'cognition', 'cognition', 'cognition', 'media'])]
    styles.save(study / 'style-review.json', {'reviewed_by': 'unit-test fixture, not a host editorial review',
        'originality_note': '模拟字段；未开展真实作者研究', 'scope_notes': '接口测试',
        'genre_scope': ['评测', '教程'], 'scores': {key: 8 for key in styles.SCORES},
        'observations': observations, 'input_hashes': styles.input_hashes(study)})


def draft(workspace):
    run = Path(w.init(workspace, 'practical', '测试写作契约')['run'])
    intake.apply(run, {'topic_mode': 'own', 'topic': '测试写作契约', 'length_preset': 'deep', 'font': 'kai',
        'writing_style': 'fixture-voice', 'answer_origin': 'user', 'user_instruction': '测试夹具答复，不能视为实际发布批准'})
    return run


def calibrate(run):
    styles.save(run / 'style-calibration.json', {'context_sha256': styles.sha(run / 'style-context.json'),
        'read_complete': True, 'reviewed_by': 'test fixture only', 'common_features': '测试共同表达记录',
        'genre_adaptation': '测试体裁适配', 'avoid_copying': '测试记录，不复制经历与原句'})


class StyleLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.workspace = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_full_registration_dynamic_choice_context_and_article_assembly(self):
        study = make_study(self.workspace)
        self.assertTrue(styles.check(study)['passed'])
        registered = styles.register(study)
        options = intake.questions(workspace=self.workspace)['questions'][-1]['options']
        self.assertEqual(options, ['卡兹克写作风格', '测试用自编文风'])
        self.assertEqual(len(w.preferences(self.workspace)['themes']), 10)
        self.assertIn('fixture-voice', w.preferences(self.workspace)['writing_styles'])
        run = draft(self.workspace)
        with self.assertRaisesRegex(ValueError, 'context'): styles.context_ready(run)
        context = styles.prepare(run, '评测', ['编程'])
        self.assertEqual(len(context['documents']), 5)
        self.assertEqual(len(context['samples']), 5)
        self.assertTrue(all(x['metadata']['article_type'] == '评测' for x in context['samples']))
        with self.assertRaisesRegex(ValueError, 'host must read'): styles.context_ready(run)
        calibrate(run); styles.context_ready(run)
        body = '这是独立的新稿内容，不能把模拟记录当作真实学习证明。'
        (run / 'body.md').write_text(body, encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'review style'): w.assemble(run)
        styles.save(run / 'style-writing-review.json', {'body_sha256': styles.sha(run / 'body.md'),
            'context_sha256': styles.sha(run / 'style-context.json'), 'reviewed_by': 'test fixture only',
            'style_application': '模拟实际段落与规则绑定', 'originality_check': '模拟检查', 'cleanup_check': '模拟白名单检查'})
        w.save(run / 'topic.json', {'working_title': '测试新标题'})
        w.assemble(run)
        self.assertIn(body, (run / 'article.md').read_text(encoding='utf-8'))
        self.assertEqual(w.read(run / 'brief.json')['font'], 'kai')
        self.assertEqual(w.read(run / 'brief.json')['writing_style_version'], registered['version'])
        self.assertIn('style-context.json', w.fingerprint(run)['hashes'])
        self.assertIn('style-context/sample-1.md', w.fingerprint(run)['hashes'])
        (run / 'body.md').write_text(body+'新改动', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'review style'): w.assemble(run)

    def test_small_corpus_stays_provisional_and_unlisted(self):
        study = make_study(self.workspace, 19)
        self.assertFalse(styles.check(study)['passed'])
        with self.assertRaisesRegex(ValueError, '20 unique'): styles.register(study)
        self.assertEqual(list(styles.catalog(self.workspace)['writing_styles']), ['khazix'])

    def test_user_file_records_do_not_need_a_fabricated_web_url(self):
        study = make_study(self.workspace)
        self.assertEqual(learning.audit(study)['valid_read_complete'], 20)
        record = copy.deepcopy(learning.read(study / 'articles.json')[0])
        record['read_url'] = 'https://example.com/fake'
        self.assertFalse(learning.record_articles(study, record)['saved'])

    def test_downloaded_or_changed_text_cannot_register(self):
        study = make_study(self.workspace)
        records = learning.read(study / 'articles.json'); records[0]['status'] = 'lead_only'
        learning.save(study / 'articles.json', records)
        with self.assertRaises(ValueError): styles.register(study)

    def test_unfinished_or_changed_dna_invalidates_review(self):
        study = make_study(self.workspace)
        (study / 'dna' / 'Writing-DNA.md').write_text('待填写。', encoding='utf-8')
        result = styles.check(study)
        self.assertFalse(result['passed'])
        self.assertTrue(any('unfinished' in x for x in result['errors']))
        self.assertTrue(any('stale' in x for x in result['errors']))

    def test_review_first_honors_user_confirmation_and_current_input_hashes(self):
        study = make_study(self.workspace, policy='review_first')
        with self.assertRaisesRegex(ValueError, 'actual current user approval'): styles.register(study)
        styles.save(study / 'style-approval.json', {'origin': 'user', 'instruction': '模拟批准，非实际用户操作',
            'input_hashes': styles.input_hashes(study)})
        self.assertEqual(styles.register(study)['status'], 'registered')

    def test_broken_profile_is_not_an_option_or_a_silent_fallback(self):
        study = make_study(self.workspace); receipt = styles.register(study)
        root = Path(receipt['path']); (root / '语言DNA.md').write_text('被改动的配置', encoding='utf-8')
        catalog = styles.catalog(self.workspace)
        self.assertNotIn('fixture-voice', catalog['writing_styles'])
        self.assertEqual(catalog['unavailable'][0]['id'], 'fixture-voice')
        with self.assertRaisesRegex(ValueError, 'unavailable'): styles.resolve(self.workspace, 'fixture-voice')

    def test_style_update_preserves_the_version_of_existing_drafts(self):
        study = make_study(self.workspace); first = styles.register(study)
        run = draft(self.workspace)
        path = study / 'dna' / '语言DNA.md'; path.write_text(path.read_text(encoding='utf-8')+'\n新的测试语言规则。', encoding='utf-8')
        seal_review(study); second = styles.register(study)
        self.assertNotEqual(first['version'], second['version'])
        self.assertEqual(styles.catalog(self.workspace)['writing_styles']['fixture-voice']['version'], second['version'])
        intake.ready(run)
        self.assertEqual(styles.prepare(run, '评测', ['编程'])['version'], first['version'])

    def test_content_study_does_not_implicitly_add_a_style(self):
        study = self.workspace / 'content-study'
        learning.init_study(self.workspace, {'request': '只学内容', 'targets': [{'account': '测试', 'count': 2}]}, study)
        with self.assertRaisesRegex(ValueError, 'content study'): styles.seed(study, 'new-style', '未授权新增风格')

    def test_metadata_must_preserve_dates_and_cognitive_evidence(self):
        study = make_study(self.workspace)
        metadata = styles.read(study / 'article-metadata.json'); metadata[0]['date'] = '2026-10-05'
        styles.save(study / 'article-metadata.json', metadata); seal_review(study)
        self.assertTrue(any('real date' in x for x in styles.check(study)['errors']))
        review = styles.read(study / 'style-review.json'); review['observations'][0]['evidence_ids'] = ['NOT_READ']
        styles.save(study / 'style-review.json', review)
        self.assertTrue(any('two read article' in x for x in styles.check(study)['errors']))

    def test_builtin_and_path_escape_cannot_be_overwritten(self):
        for ident in ('khazix', '../account', 'x/../../secret'):
            with self.assertRaises(ValueError): styles.validate_id(ident)
        with self.assertRaises(ValueError): styles.inside(self.workspace, '../outside')

    def test_english_artifacts_use_the_real_upstream_templates(self):
        study = make_study(self.workspace, language='en')
        self.assertTrue(styles.check(study)['passed'])
        receipt = styles.register(study)
        self.assertTrue((Path(receipt['path']) / 'language-dna.md').is_file())
        self.assertFalse((Path(receipt['path']) / '语言DNA.md').exists())


if __name__ == '__main__':
    unittest.main()
