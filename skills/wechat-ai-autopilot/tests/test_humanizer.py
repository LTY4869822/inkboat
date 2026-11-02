from pathlib import Path
import json, tempfile, unittest, sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import humanize as h
import workflow as w

class HumanizerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.run=Path(self.temp.name)
        self.before='这不是下载，而是工作流的入口。\n\n打开 `https://github.com/signup`。\n\n```sh\necho "$HOME"\n```\n\n![注册](assets/a.png)\n'
        (self.run/'body.md').write_text(self.before,encoding='utf8')
        h.save(self.run/'brief.json',{'writing_style':'khazix','humanizer_policy':h.POLICY})
        h.prepare(self.run)
        self.after=self.before.replace('这不是下载，而是工作流的入口。','先下载完整文件，再安装。')
        self.review()
    def tearDown(self):self.temp.cleanup()
    def review(self):
        (self.run/'body.md').write_text(self.after,encoding='utf8')
        h.save(self.run/'humanizer-review.json',{'status':'pass','source_draft_sha256':h.sha(self.run/'writing-draft.md'),
          'body_sha256':h.sha(self.run/'body.md'),'prose_sha256':h.prose_sha(self.after),'writing_style':'khazix',
          'findings':[{'pattern':'staging','before':'这不是下载，而是工作流的入口。','after':'先下载完整文件，再安装。','reason':'教程说明先下载再安装，删去故作重要的抽象对比。'}],
          'checks':{key:{'status':'pass','reason':'测试夹具记录完整的事实、文风与读者检查，不代表真实文章审阅。'} for key in h.CHECKS}})
    def test_review_pass_then_new_prose_rejected(self):
        self.assertEqual(h.errors(self.run),[])
        (self.run/'body.md').write_text(self.after+'编造的新结果。',encoding='utf8')
        self.assertTrue(h.errors(self.run))
    def test_code_edits_rejected_even_with_updated_review_hash(self):
        self.after=self.after.replace('echo "$HOME"','rm "$HOME"'); self.review()
        self.assertTrue(any('code_blocks' in x for x in h.errors(self.run)))
    def test_link_and_inline_code_edits_rejected(self):
        self.after=self.after.replace('github.com/signup','github.com/login');self.review()
        self.assertTrue(any('inline_code' in x for x in h.errors(self.run)))
    def test_subsequent_illustration_does_not_invalidate_prose(self):
        (self.run/'body.md').write_text(self.after+'\n![概念](assets/b.png)\n',encoding='utf8')
        self.assertEqual(h.errors(self.run),[])
    def test_existing_image_substitution_rejected(self):
        self.after=self.after.replace('assets/a.png','assets/fake.png');self.review()
        self.assertTrue(any('image_tokens' in x for x in h.errors(self.run)))
    def test_selected_voice_change_rejected(self):
        h.save(self.run/'brief.json',{'writing_style':'another','humanizer_policy':h.POLICY})
        self.assertTrue(h.errors(self.run))
    def test_tutorial_requires_handholding_review(self):
        h.save(self.run/'reader-intent.json',{'article_type':'tutorial'})
        self.assertTrue(any('handholding' in x for x in h.errors(self.run)))
    def test_missing_review_rejected_for_new_policy_only(self):
        (self.run/'humanizer-review.json').unlink();self.assertTrue(h.errors(self.run))
        h.save(self.run/'brief.json',{'writing_style':'khazix'})
        self.assertEqual(h.errors(self.run),[])
    def test_audit_gate_and_fingerprint_bind_review(self):
        first=w.fingerprint(self.run)['fingerprint']
        record=h.load(self.run/'humanizer-review.json');record['checks']['voice_preserved']['reason']='审阅重新核对，原定口语风格仍然保留，脚本不替代人工内容判断。'
        h.save(self.run/'humanizer-review.json',record)
        self.assertNotEqual(first,w.fingerprint(self.run)['fingerprint'])
        (self.run/'humanizer-review.json').unlink()
        report=w.audit(self.run)
        self.assertTrue(any('Humanizer review absent' in x for x in report['errors']))

if __name__=='__main__':unittest.main()
