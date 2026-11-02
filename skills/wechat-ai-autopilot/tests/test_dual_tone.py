from pathlib import Path
import sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import humanize as h
import lieflat_review as l
import workflow as w

class DualToneTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.run=Path(self.temp.name)
        self.before='说白了，团队完成了对流程的优化。\n\n运行 `tool check`。\n\n```sh\necho ok\n```\n'
        (self.run/'body.md').write_text(self.before,encoding='utf8')
        h.save(self.run/'brief.json',{'writing_style':'khazix','humanizer_policy':h.POLICY,'tone_policy':l.POLICY})
        h.prepare(self.run)
        self.middle=self.before.replace('说白了，','')
        (self.run/'body.md').write_text(self.middle,encoding='utf8')
        h.save(self.run/'humanizer-review.json',{'status':'pass','source_draft_sha256':h.sha(self.run/'writing-draft.md'),
            'prose_sha256':h.prose_sha(self.middle),'writing_style':'khazix',
            'findings':[{'before':'说白了，','after':'','pattern':'filler','reason':'测试夹具中删除空转起手式，不宣称真实编辑审阅。'}],
            'checks':{k:{'status':'pass','reason':'测试夹具的编辑审阅记录，只验证版本和链路约束。'} for k in h.CHECKS}})
        l.prepare(self.run)
        self.after=self.middle.replace('团队完成了对流程的优化。','团队优化了流程。')
        self.review()
    def tearDown(self):self.temp.cleanup()
    def review(self):
        (self.run/'body.md').write_text(self.after,encoding='utf8')
        h.save(self.run/'lieflat-review.json',{'status':'pass','input_sha256':h.sha(self.run/'humanizer-output.md'),
            'prose_sha256':h.prose_sha(self.after),'writing_style':'khazix',
            'findings':[{'rule':8,'before':'团队完成了对流程的优化。','after':'团队优化了流程。','reason':'测试夹具还原原动作动词，没有新增数据或改动结论。'}],
            'checks':{k:{'status':'pass','reason':'测试夹具的二道审阅记录，不声称做过读者实验。'} for k in l.CHECKS}})
    def test_first_and_second_bound_to_different_actual_outputs(self):
        self.assertEqual(h.errors(self.run),[])
        self.assertEqual((self.run/'humanizer-output.md').read_text(encoding='utf8'),self.middle)
    def test_missing_second_review_blocks_combined_gate(self):
        (self.run/'lieflat-review.json').unlink();self.assertTrue(h.errors(self.run))
    def test_final_prose_change_even_with_updated_hash_requires_findings(self):
        self.after+='\n自称跑分翻倍。';self.review()
        self.assertTrue(any('outside' in e for e in l.errors(self.run)))
    def test_changed_code_rejected(self):
        self.after=self.after.replace('echo ok','delete everything');self.review()
        self.assertTrue(any('code_blocks' in e for e in l.errors(self.run)))
    def test_paragraph_split_rejected_even_if_declared(self):
        self.after=self.after.replace('团队优化了流程。','团队\n\n优化了流程。');self.review()
        record=h.load(self.run/'lieflat-review.json');record['findings'][0]['after']='团队\n\n优化了流程。'
        h.save(self.run/'lieflat-review.json',record)
        self.assertTrue(any('structure' in e for e in l.errors(self.run)))
    def test_first_review_change_invalidates_second_context(self):
        record=h.load(self.run/'humanizer-review.json');record['checks']['voice_preserved']['reason']='改变第一道实际文风判断，第二道输入审阅已经失效，需要重新核对。'
        h.save(self.run/'humanizer-review.json',record)
        self.assertTrue(any('context' in e for e in l.errors(self.run)))
    def test_new_images_do_not_invalidate_prose_chain(self):
        (self.run/'body.md').write_text(self.after+'\n![示意](assets/new.png)\n',encoding='utf8')
        self.assertEqual(h.errors(self.run),[])
    def test_second_review_is_in_fingerprint(self):
        old=w.fingerprint(self.run)['fingerprint']
        record=h.load(self.run/'lieflat-review.json');record['checks']['voice_preserved']['reason']='新的一次实际文风复核说明，更新审阅也应更新整篇签名。'
        h.save(self.run/'lieflat-review.json',record)
        self.assertNotEqual(old,w.fingerprint(self.run)['fingerprint'])

if __name__=='__main__':unittest.main()
