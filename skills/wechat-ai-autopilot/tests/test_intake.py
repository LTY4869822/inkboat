import copy
import datetime as dt
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import intake as i
import workflow as w
import draft_bridge as d


class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        self.run = Path(w.init(self.workspace, 'news', 'AI')['run'])
        self.answers = {'topic_mode':'own', 'topic':'我指定的具体选题', 'length_preset':'deep',
                        'font':'kai', 'writing_style':'khazix', 'answer_origin':'user',
                        'user_instruction':'测试用户输入：按照我的选题写长篇，楷体，卡兹克文风。'}

    def tearDown(self): self.temp.cleanup()

    def candidates(self):
        timestamp = w.now()
        return {'searched_at':timestamp, 'candidates':[
            {'id':str(n), 'title':'测试选题'+str(n), 'angle':'解释用途', 'reader_benefit':'能照做',
             'published_at':timestamp, 'retrieved_at':timestamp, 'primary_url':'https://example.org/'+str(n),
             'hot_signal':{'platform':'测试夹具，不是真实热度', 'observed_at':timestamp, 'description':'仅验证数据合同'}} for n in range(5)]}

    def preview_set(self):
        i.apply(self.run, self.answers)
        (self.run/'body.md').write_text('测试正文内容', encoding='utf-8')
        (self.run/'article.md').write_text('# 测试标题\n\n测试正文内容', encoding='utf-8')
        variants=[]
        for theme in w.read(w.ROOT/'assets/preferences.json')['themes']:
            p=self.run/(theme+'.html'); p.write_text('测试预览'+theme, encoding='utf-8')
            variants.append({'theme':theme, 'preview':p.name, 'preview_sha256':w.file_hash(p)})
        w.save(self.run/'layout-variants.json', {'article_sha256':w.file_hash(self.run/'article.md'),
               'body_sha256':w.file_hash(self.run/'body.md'), 'font':w.font_choice('kai'), 'variants':variants})

    def test_questions_skip_known_and_offer_only_current_voice(self):
        result=i.questions({'topic_mode':'own', 'font':'song'})
        self.assertEqual([q['key'] for q in result['questions']], ['length_preset','writing_style'])
        self.assertEqual(result['questions'][-1]['options'], ['卡兹克写作风格'])

    def test_missing_intake_blocks_assembly(self):
        with self.assertRaisesRegex(ValueError,'Pre-writing'): w.assemble(self.run)

    def test_own_topic_length_font_and_style_are_applied(self):
        i.apply(self.run,self.answers)
        brief=w.read(self.run/'brief.json')
        self.assertEqual((brief['topic'],brief['min_chars'],brief['max_chars'],brief['font']), ('我指定的具体选题',5000,7000,'kai'))
        i.ready(self.run)

    def test_silence_missing_answer_and_unavailable_style_fail(self):
        for update in ({'answer_origin':'inferred'}, {'font':None}, {'writing_style':'not-installed'}):
            with self.assertRaises(ValueError): i.apply(self.run,{**self.answers,**update})
        incomplete=copy.deepcopy(self.answers); del incomplete['length_preset']
        with self.assertRaisesRegex(ValueError,'Missing'): i.apply(self.run,incomplete)

    def test_free_length_and_custom_font(self):
        i.apply(self.run,{**self.answers,'length_preset':'auto','font':'custom','custom_font':'思源宋体 CN'})
        self.assertEqual(w.read(self.run/'brief.json')['length_preset'],'auto')
        self.assertIn('思源宋体 CN',w.font_choice('custom','思源宋体 CN')['stack'])
        self.assertIn('free length needs a content-specific outline length_reason',w.audit(self.run)['errors'])

    def test_custom_font_rejects_css_and_url(self):
        for font in ('serif; color:red', 'https://example.org/font', '</script>', 'x";background:url(x)'):
            with self.assertRaises(ValueError): w.font_choice('custom',font)

    def test_font_and_length_changes_require_new_user_record(self):
        i.apply(self.run,self.answers); w.configure(self.run,font='song')
        with self.assertRaisesRegex(ValueError,'changed'): i.ready(self.run)

    def test_five_recent_candidates_are_required(self):
        data=self.candidates(); i.validate_candidates(data)
        for mutate in ('four','duplicate','old','missing_signal'):
            bad=copy.deepcopy(data)
            if mutate=='four': bad['candidates'].pop()
            if mutate=='duplicate': bad['candidates'][1]['id']='0'
            if mutate=='old': bad['candidates'][0]['published_at']=(w.date(data['searched_at'])-dt.timedelta(days=8)).isoformat()
            if mutate=='missing_signal': bad['candidates'][0]['hot_signal']={}
            with self.assertRaises(ValueError): i.validate_candidates(bad)

    def test_candidate_selection_waits_and_preserves_chosen_title(self):
        w.save(self.run/'topic-candidates.json',self.candidates())
        answer={**self.answers,'topic_mode':'candidates'}
        with self.assertRaisesRegex(ValueError,'Wait'): i.apply(self.run,answer)
        i.apply(self.run,{**answer,'selected_candidate':'2'})
        self.assertEqual(w.read(self.run/'brief.json')['topic'],'测试选题2')

    def test_selected_preview_pending_revision_blocks_draft(self):
        self.preview_set(); i.select_layout(self.run,'green-white-clean','测试用户选择绿白，但正文还要修改')
        with self.assertRaisesRegex(ValueError,'pending'): i.selection_current(self.run)

    def test_changed_preview_or_article_invalidates_selection(self):
        self.preview_set(); i.select_layout(self.run,'green-white-clean','测试用户选绿白，没有修改',True)
        i.selection_current(self.run)
        (self.run/'green-white-clean.html').write_text('已变化',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'changed'): i.selection_current(self.run)
        with self.assertRaisesRegex(ValueError,'changed'): i.select_layout(self.run,'green-white-clean','选择',True)

    def test_changed_title_invalidates_selection(self):
        self.preview_set(); i.select_layout(self.run,'green-white-clean','测试用户选绿白，没有修改',True)
        (self.run/'article.md').write_text('# 改过标题\n\n测试正文内容',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'stale'): i.selection_current(self.run)

    def test_account_memory_and_wrong_account_gate(self):
        self.preview_set(); i.select_layout(self.run,'green-white-clean','测试用户选绿白，没有修改',True)
        i.bind_account(self.workspace,'测试号','gh_test1234','测试授权：选排版后自动存草稿','测试账号详情页')
        self.assertEqual(i.draft_authorization(self.run,'测试号','gh_test1234'),'测试授权：选排版后自动存草稿')
        with self.assertRaisesRegex(ValueError,'differs'): i.draft_authorization(self.run,'其他号','gh_test1234')
        with self.assertRaisesRegex(ValueError,'differs'): i.draft_authorization(self.run,'测试号','gh_other123')
        data=w.read(i.account_path(self.workspace))
        self.assertFalse({'token','password','cookie','AppSecret'} & set(data))

    def test_no_account_secret_can_be_used_as_public_id(self):
        with self.assertRaises(ValueError): i.bind_account(self.workspace,'测试号','access_token=secret','授权','观察')

    def test_automatic_draft_prepare_uses_remembered_instruction(self):
        self.preview_set(); i.select_layout(self.run,'green-white-clean','测试用户选绿白，没有修改',True)
        i.bind_account(self.workspace,'测试号','gh_test1234','选定后自动存草稿','测试观察')
        w.save(self.run/'article-meta.json',{'title':'测试标题','digest':'测试摘要'})
        (self.run/'article.html').write_text('<p style="color:green">测试HTML</p>',encoding='utf-8')
        (self.run/'cover.png').write_bytes(b'test-cover')
        w.save(self.run/'images.json',[{'role':'cover','path':'cover.png'}])
        with patch.object(d,'current',return_value='fixture-fingerprint'),patch.object(w,'html_check',return_value=[]):
            result=d.prepare(self.run,'测试号',account_id='gh_test1234')
        self.assertEqual(result['authorization'],'选定后自动存草稿')
        self.assertEqual(result['account_id'],'gh_test1234')

    def test_font_missing_in_export_is_rejected(self):
        i.apply(self.run,self.answers)
        (self.run/'article.md').write_text('# 标题\n\n正文',encoding='utf-8')
        errors=w.html_check(self.run,'<h1 style="color:black">标题</h1><p style="color:black">正文</p>')
        self.assertIn('exported paragraph/heading font differs from user choice', errors)
        stack=w.font_choice('kai')['stack'].replace('"','&quot;')
        good=f'<h1 style="font-family:{stack}">标题</h1><p style="font-family:{stack}">正文</p>'
        self.assertEqual(w.html_check(self.run,good),[])

    def test_original_image_change_invalidates_preview_approval(self):
        self.preview_set()
        image=self.run/'original.png'; image.write_bytes(b'first-image')
        manifest=w.read(self.run/'layout-variants.json'); manifest['asset_hashes']={'original.png':w.file_hash(image)}
        w.save(self.run/'layout-variants.json',manifest)
        i.select_layout(self.run,'green-white-clean','测试用户选择绿白且无修改',True)
        image.write_bytes(b'changed-image')
        with self.assertRaisesRegex(ValueError,'image changed'): i.selection_current(self.run)

    def test_new_theme_selection_requires_complete_current_previews(self):
        self.preview_set()
        manifest=w.read(self.run/'layout-variants.json')
        manifest.update(schema_version=2,theme_ids=list(w.read(w.ROOT/'assets/preferences.json')['themes']))
        complete=copy.deepcopy(manifest)
        manifest['variants'].pop()
        w.save(self.run/'layout-variants.json',manifest)
        with self.assertRaisesRegex(ValueError,'complete'): i.select_layout(self.run,'moonwhite-literary','测试选择月白',True)
        w.save(self.run/'layout-variants.json',complete)
        i.select_layout(self.run,'moonwhite-literary','测试用户选择新增月白，暂无修改',True)
        self.assertEqual(i.selection_current(self.run)['theme'],'moonwhite-literary')

    def test_unchanged_legacy_preview_set_remains_selectable(self):
        self.preview_set()
        manifest=w.read(self.run/'layout-variants.json')
        legacy={'green-white-clean','ink-blue-editorial','graphite-dossier','sand-gold-journal','mist-purple-story'}
        manifest['schema_version']=1
        manifest['variants']=[v for v in manifest['variants'] if v['theme'] in legacy]
        w.save(self.run/'layout-variants.json',manifest)
        i.select_layout(self.run,'green-white-clean','测试旧稿选择原五套之一，无修改',True)
        self.assertEqual(i.selection_current(self.run)['theme'],'green-white-clean')

    def test_status_reports_questions_and_own_topic_skips_discovery(self):
        self.assertEqual(w.status(self.run)['next'],'pre-writing-questions')
        i.apply(self.run,self.answers)
        self.assertEqual(w.status(self.run)['next'],'evidence')


if __name__ == '__main__': unittest.main()
